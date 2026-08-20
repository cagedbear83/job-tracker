# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403

router = APIRouter()


def _repair_adj034f_first_name_field(writer) -> None:
    """
    Works around a real defect in the state's own ADJ034F.pdf template: the
    "First Name" AcroForm field has TWO widget annotations sharing one field
    identity — the correct one at the top of page 1, and a second one on
    page 2 sitting exactly where "Results 4d" (the 4th contact row of the
    3rd week-block, the middle group on page 2) should be. "Results 4d" is
    missing entirely from the form's field list — confirmed by dumping every
    "Results *" field's page+rect and finding 4a/4b/4c/4e present but 4d
    absent, with the orphaned "First Name" widget's rect landing exactly in
    that gap.

    Because both widgets share one field name, whatever value is set for
    "First Name" is written to BOTH locations — this is standard PDF
    behavior for shared field names (e.g. the same SSN repeated on every
    page), not a bug in pypdf or our fill logic. It's how a claimant's first
    name ended up printed in the page-2 Results box, and (per pypdf's
    per-page appearance-stream handling for a field split across pages) why
    the real First Name box on page 1 could end up blank instead.

    Fix: detach the page-2 widget from the "First Name" field's /Kids array,
    rename it to "Results 4d", and register it as its own top-level
    AcroForm field. From that point on, "First Name" and "Results 4d" are
    two independent fields — the existing fill logic already tries to write
    `field_values["Results 4d"]`, it just had nowhere valid to land before.

    Safe to call unconditionally: if the template is ever fixed upstream (or
    already has a normal single-widget "First Name" field), this is a no-op.
    """
    from pypdf.generic import ArrayObject, NameObject, TextStringObject

    acro = writer.root_object.get("/AcroForm")
    if not acro:
        return
    fields = acro.get("/Fields")
    if not fields:
        return

    first_name_field = None
    for ref in fields:
        fo = ref.get_object()
        if fo.get("/T") == "First Name":
            first_name_field = fo
            break
    if first_name_field is None:
        return

    kids = first_name_field.get("/Kids")
    if not kids or len(kids) < 2:
        return  # already normal — nothing to repair

    # Map each kid's indirect-object id to the page it actually renders on.
    page_of = {}
    for pnum, page in enumerate(writer.pages):
        for a in page.get("/Annots") or []:
            page_of[a.indirect_reference.idnum] = pnum

    # The real First Name box is at the top of page 1 (index 0). Anything
    # else is the orphan — identified by page rather than a hardcoded rect,
    # so this still works if the template's coordinates ever shift slightly.
    orphan_ref = None
    for kref in kids:
        if page_of.get(kref.idnum) != 0:
            orphan_ref = kref
            break
    if orphan_ref is None:
        return

    orphan_obj = orphan_ref.get_object()
    if "/Parent" in orphan_obj:
        del orphan_obj["/Parent"]
    orphan_obj[NameObject("/T")] = TextStringObject("Results 4d")
    orphan_obj[NameObject("/FT")] = NameObject("/Tx")

    first_name_field[NameObject("/Kids")] = ArrayObject(
        [k for k in kids if k.idnum != orphan_ref.idnum]
    )
    fields.append(orphan_ref)


@router.get("/reports/benefit-week/{week_id}")
async def report_pdf(week_id: str, user=Depends(get_current_user)):
    import io
    from pypdf import PdfReader, PdfWriter
    from pypdf.annotations import FreeText
    from pypdf.generic import NameObject, NumberObject

    w = await db.benefit_weeks.find_one({"id": week_id, "user_id": user["id"]})
    if not w:
        raise HTTPException(status_code=404, detail="Week not found")

    # Tier enforcement: metered PDF exports (free = 3/month, paid = unlimited).
    # Gated after the week is confirmed so a 404 doesn't consume quota.
    await sub.gate_metered(db, user["id"], "pdf_exports_per_month")

    contacts = (
        await db.contacts.find({"benefit_week_id": week_id, "user_id": user["id"]})
        .sort("contact_date", 1)
        .to_list(30)
    )

    claimant = await db.profiles.find_one(
        {"id": w.get("claimant_id"), "user_id": user["id"]}
    )
    claimant_id = claimant.get("claimant_id", "") if claimant else ""

    # Profile.first_name/last_name/middle_initial are already stored as
    # distinct fields (see ProfileIn in core.py) — read them directly rather
    # than concatenating first+last into one string and re-splitting it.
    # The re-split approach was actively wrong two ways: (1) it never
    # included middle_initial in the string it split, so "Middle Initial"
    # could never populate no matter what was on file, and (2) for any
    # multi-word last name (e.g. "Van Der Berg") it silently misattributed
    # extra name parts as a middle initial and truncated the last name.
    first = claimant.get("first_name", "") if claimant else ""
    last = claimant.get("last_name", "") if claimant else ""
    mi = claimant.get("middle_initial", "") if claimant else ""

    def _to_mmddyyyy(value) -> str:
        """
        Dates on BenefitWeek/Contact are declared as plain `str` in the
        Pydantic models (ISO "YYYY-MM-DD", as sent by an HTML date input),
        so they're never actual datetime objects — the previous
        `hasattr(x, "strftime")` check was dead code that never fired, and
        every date landed on the printed state form as raw ISO text instead
        of the US-format IDES expects. Reformats when possible; falls back
        to the original string on anything unexpected rather than failing
        the whole report over a formatting nicety.
        """
        if hasattr(value, "strftime"):
            return value.strftime("%m/%d/%Y")
        if isinstance(value, str) and value:
            try:
                return datetime.strptime(value, "%Y-%m-%d").strftime("%m/%d/%Y")
            except ValueError:
                return value
        return value or ""

    week_end = _to_mmddyyyy(w.get("week_end", ""))

    # Map contacts to the REAL ADJ034F AcroForm field names. These were
    # previously guessed ("weekend1", "date1", "name1", "address1", ...) and
    # didn't match anything in the actual state PDF except by coincidence
    # ("Last Name" / "ID or SSN") — pypdf silently no-ops on an unmatched
    # field name rather than erroring, so the report always rendered with
    # almost everything blank. Confirmed the real names via
    # PdfReader(...).get_fields() against assets/ADJ034F.pdf: the form has 5
    # week-blocks ("Week Ending 1".."Week Ending 5"), each with 5
    # lettered contact rows (a-e) — 25 rows total, not 30 — and a single
    # combined "Name and Address" field per row rather than separate
    # name/address fields.
    field_values = {
        "Last Name": last,
        "First Name": first,
        "Middle Initial": mi,
        "ID or SSN": claimant_id,
    }

    SECTION_LETTERS = ["a", "b", "c", "d", "e"]
    MAX_CONTACTS = len(SECTION_LETTERS) * 5  # 25 — the form's real capacity

    if len(contacts) > MAX_CONTACTS:
        logging.warning(
            f"Week {week_id} has {len(contacts)} contacts — ADJ034F only has "
            f"{MAX_CONTACTS} rows; the last {len(contacts) - MAX_CONTACTS} "
            f"won't appear on the generated PDF."
        )

    # This report is for a single benefit week, so normally only week-block 1
    # is used. If a week has more than 5 contacts (uncommon — IDES only
    # requires 3+), the overflow spills into blocks 2-5, repeating this same
    # week's end date in each block's "Week Ending N" field so the extra
    # rows still carry a date.
    contacts_to_fill = contacts[:MAX_CONTACTS]
    sections_needed = max(1, -(-len(contacts_to_fill) // 5))  # ceiling division
    for s in range(1, sections_needed + 1):
        field_values[f"Week Ending {s}"] = week_end

    for i, c in enumerate(contacts_to_fill):
        section = i // 5 + 1
        letter = SECTION_LETTERS[i % 5]
        employer = c.get("employer_name", "")
        address = c.get("employer_address", "")
        person = c.get("person_contacted", "")
        method = c.get("contact_method", "")
        work_type = c.get("type_of_work", "")
        result = c.get("result", "")
        cdate = _to_mmddyyyy(c.get("contact_date", ""))

        name_and_address = employer
        if address:
            name_and_address = f"{employer}\n{address}" if employer else address

        field_values[f"Contact Date {section}{letter}"] = str(cdate)
        field_values[f"Name and Address {section}{letter}"] = name_and_address
        field_values[f"Person Contacted {section}{letter}"] = person
        field_values[f"Method of Contact {section}{letter}"] = method
        field_values[f"Type of Work {section}{letter}"] = work_type
        field_values[f"Results {section}{letter}"] = result

    # Fill the state PDF form
    try:
        template_path = ROOT_DIR / "assets" / "ADJ034F.pdf"
        if not template_path.exists():
            raise HTTPException(
                status_code=500,
                detail="State form template not found in assets/ADJ034F.pdf",
            )

        reader = PdfReader(str(template_path))
        writer = PdfWriter()
        writer.append(reader)
        _repair_adj034f_first_name_field(writer)
        for page in writer.pages:
            writer.update_page_form_field_values(page, field_values)

        # Stamp a generation timestamp along the very bottom of every page —
        # an audit trail for exactly when this specific PDF was produced,
        # since the same benefit week can be re-exported repeatedly as
        # contacts get added over the week. Uses a pypdf FreeText annotation
        # rather than reportlab (deliberately not a dependency here — see the
        # note in requirements.txt), so no library needed just for this. The
        # /F=4 flag marks the annotation printable so it survives being
        # printed/scanned to PDF again, not just on-screen viewing.
        # Shown in America/Chicago local time (not UTC, per Kyle's request) —
        # matches the timezone the rest of the app already runs on (see
        # core.py's scheduler/_current_week_bounds).
        generated_at = datetime.now(pytz.timezone("America/Chicago")).strftime("%m/%d/%Y %I:%M %p %Z")
        stamp_text = f"Generated by Illinois UI Job Tracker — {generated_at}"
        for i, page in enumerate(writer.pages):
            width = float(page.mediabox.width)
            stamp = FreeText(
                text=stamp_text,
                rect=(18, 6, width - 18, 18),
                font="Helvetica",
                font_size="6pt",
                font_color="808080",
                border_color=None,
                background_color=None,
            )
            stamp[NameObject("/F")] = NumberObject(4)
            writer.add_annotation(page_number=i, annotation=stamp)

        buf = io.BytesIO()
        writer.write(buf)
        buf.seek(0)

        filename = f"WorkSearch_{week_end}.pdf".replace("/", "-")
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename={filename}"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"PDF generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {e}")
