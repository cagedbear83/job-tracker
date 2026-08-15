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
    claimant_name = (
        f"{claimant.get('first_name', '')} {claimant.get('last_name', '')}".strip()
        if claimant else ""
    )

    # Split name into first / last / MI
    name_parts = claimant_name.strip().split()
    first = name_parts[0] if len(name_parts) >= 1 else ""
    last = name_parts[-1] if len(name_parts) >= 2 else ""
    mi = name_parts[1][0] if len(name_parts) >= 3 else ""

    week_end = w.get("week_end", "")
    if hasattr(week_end, "strftime"):
        week_end = week_end.strftime("%m/%d/%Y")

    # Map contacts to form field slots (form holds 30 max across 6 sections of 5)
    field_values = {
        "Last Name": last,
        "First Name": first,
        "Middle Initial": mi,
        "ID or SSN": claimant_id,
    }

    # Fill week-end date into whichever sections we need
    sections_needed = max(1, -(-len(contacts) // 5))  # ceiling division
    for s in range(1, sections_needed + 1):
        field_values[f"weekend{s}"] = week_end

    # Fill contact rows
    for i, c in enumerate(contacts[:30], start=1):
        employer = c.get("employer_name", "")
        address = c.get("employer_address", "")
        person = c.get("person_contacted", "")
        method = c.get("contact_method", "")
        work_type = c.get("type_of_work", "")
        result = c.get("result", "")
        cdate = c.get("contact_date", "")
        if hasattr(cdate, "strftime"):
            cdate = cdate.strftime("%m/%d/%Y")

        field_values[f"date{i}"] = str(cdate)
        field_values[f"name{i}"] = employer
        field_values[f"address{i}"] = address
        field_values[f"personcontact{i}"] = person
        field_values[f"methodcontact{i}"] = method
        field_values[f"typework{i}"] = work_type
        field_values[f"result{i}"] = result

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
