# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403

router = APIRouter()



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
        generated_at = datetime.now(timezone.utc).strftime("%m/%d/%Y %I:%M %p UTC")
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
