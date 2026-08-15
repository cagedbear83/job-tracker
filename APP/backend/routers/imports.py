# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403

router = APIRouter()



# ============== Import: CSV ==============
@router.post("/import/csv")
async def import_csv(
    file: UploadFile = File(...),
    week_id: str = Form(...),
    user=Depends(get_current_user),
):
    w = await db.benefit_weeks.find_one({"id": week_id, "user_id": user["id"]})
    if not w:
        raise HTTPException(status_code=404, detail="Benefit week not found")
    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_CSV_IMPORT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"CSV file too large (max {MAX_CSV_IMPORT_BYTES // 1024} KB)",
        )
    raw = raw_bytes.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(raw))
    inserted = 0
    rows_out = []
    for row_num, row in enumerate(reader, start=1):
        if row_num > MAX_CSV_IMPORT_ROWS:
            break
        lc = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        contact = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "benefit_week_id": week_id,
            "claimant_id": w.get("claimant_id"),
            "contact_date": lc.get("date") or lc.get("contact_date") or lc.get("date applied") or w["week_start"],
            "employer_name": lc.get("employer") or lc.get("company") or lc.get("employer_name") or lc.get("company name") or "",
            "employer_address": lc.get("address") or lc.get("location") or "",
            "contact_method": (lc.get("method") or lc.get("contact_method") or "Online").title(),
            "type_of_work": lc.get("type_of_work") or lc.get("type") or "",
            "position_applied": lc.get("position") or lc.get("job_title") or lc.get("title") or "",
            "person_contacted": lc.get("contact") or lc.get("person_contacted") or "",
            "result": lc.get("result") or lc.get("status") or "Applied",
            "source_url": lc.get("url") or lc.get("link") or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if contact["contact_method"] not in ["In Person", "Phone", "Email", "Online", "Mail", "Other"]:
            contact["contact_method"] = "Online"
        if contact["employer_name"]:
            await db.contacts.insert_one(contact)
            contact.pop("_id", None)
            rows_out.append(contact)
            inserted += 1
    await log_audit(user["id"], "IMPORT_CSV", "contact", week_id, f"Imported {inserted} contacts via CSV")
    return {"inserted": inserted, "contacts": rows_out}



# ============== Import: Screenshot OCR (AI Vision) ==============
@router.post("/import/screenshot")
async def import_screenshot(
    file: UploadFile = File(...),
    week_id: str = Form(...),
    user=Depends(get_current_user),
):
    w = await db.benefit_weeks.find_one({"id": week_id, "user_id": user["id"]})
    if not w:
        raise HTTPException(status_code=404, detail="Benefit week not found")

    img_bytes = await file.read()
    if not img_bytes:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(img_bytes) > MAX_SCREENSHOT_IMPORT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large (max {MAX_SCREENSHOT_IMPORT_BYTES // (1024 * 1024)} MB)",
        )

    mime = (file.content_type or "").lower()
    if mime not in ALLOWED_SCREENSHOT_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image type. Upload a PNG, JPEG, or WEBP screenshot.",
        )

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    # Tier enforcement: metered AI import. Gated AFTER input validation so a
    # bad upload doesn't burn quota, and BEFORE the (paid) Gemini call.
    await sub.gate_metered(db, user["id"], "ai_screenshot_import")

    prompt = (
        "You extract job posting details from screenshots of job boards like Indeed, LinkedIn, "
        "ZipRecruiter, Glassdoor. Output STRICT JSON only, no prose, no markdown. "
        "Extract job(s) from this screenshot. Return JSON: "
        '{"jobs":[{"employer_name":"","position_applied":"","employer_address":"",'
        '"contact_method":"Online","type_of_work":"","contact_date":"YYYY-MM-DD","source_url":"","result":"Applied"}]}. '
        f"If date unclear use {w['week_start']}. If multiple jobs visible include each as an entry."
    )

    import io as _io
    import PIL.Image

    try:
        pil_image = PIL.Image.open(_io.BytesIO(img_bytes))
        pil_image.load()
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read image file")
    if pil_image.width * pil_image.height > MAX_SCREENSHOT_PIXELS:
        raise HTTPException(status_code=400, detail="Image resolution too large")

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: model.generate_content([prompt, pil_image])
        )
        response = response.text
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Vision extraction failed: {e}")

    import json
    import re

    text = str(response)
    m = re.search(r"\{[\s\S]*\}", text)
    json_str = m.group(0) if m else text
    try:
        data = json.loads(json_str)
    except Exception:
        data = {"jobs": []}

    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    inserted = []
    for j in jobs:
        if not isinstance(j, dict) or not j.get("employer_name"):
            continue
        method = (j.get("contact_method") or "Online").title()
        if method not in ["In Person", "Phone", "Email", "Online", "Mail", "Other"]:
            method = "Online"
        contact = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "benefit_week_id": week_id,
            "claimant_id": w.get("claimant_id"),
            "contact_date": j.get("contact_date") or w["week_start"],
            "employer_name": j.get("employer_name", ""),
            "employer_address": j.get("employer_address", "") or "",
            "contact_method": method,
            "type_of_work": j.get("type_of_work", "") or "",
            "position_applied": j.get("position_applied", "") or "",
            "person_contacted": j.get("person_contacted", "") or "",
            "result": j.get("result", "Applied") or "Applied",
            "source_url": j.get("source_url", "") or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.contacts.insert_one(contact)
        contact.pop("_id", None)
        inserted.append(contact)

    await log_audit(user["id"], "IMPORT_OCR", "contact", week_id, f"Imported {len(inserted)} contacts via screenshot OCR")
    return {"inserted": len(inserted), "contacts": inserted, "raw": text[:500]}
