# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403

router = APIRouter()



# ============== Work Search Contacts ==============
@router.get("/contacts")
async def list_contacts(week_id: Optional[str] = None, user=Depends(get_current_user)):
    query = {"user_id": user["id"]}
    if week_id:
        query["benefit_week_id"] = week_id
    else:
        cid = await get_active_claimant_id(user["id"])
        if cid:
            query["$or"] = [{"claimant_id": cid}, {"claimant_id": {"$exists": False}}]
    items = (
        await db.contacts.find(query, {"_id": 0}).sort("contact_date", -1).to_list(5000)
    )
    return items



@router.post("/contacts")
async def create_contact(body: ContactIn, user=Depends(get_current_user)):
    w = await db.benefit_weeks.find_one(
        {"id": body.benefit_week_id, "user_id": user["id"]}, {"_id": 0}
    )
    if not w:
        raise HTTPException(status_code=404, detail="Benefit week not found")
    cid = str(uuid.uuid4())
    doc = {
        "id": cid,
        "user_id": user["id"],
        "claimant_id": w.get("claimant_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        **body.model_dump(),
    }
    await db.contacts.insert_one(doc)
    await log_audit(
        user["id"], "CREATE", "contact", cid, f"Contact: {body.employer_name}"
    )
    doc.pop("_id", None)
    return doc



@router.put("/contacts/{cid}")
async def update_contact(cid: str, body: ContactIn, user=Depends(get_current_user)):
    existing = await db.contacts.find_one(
        {"id": cid, "user_id": user["id"]}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    update = body.model_dump()

    # ── Auto-reassign to the correct benefit week when the date changes ──────
    # If the edited date no longer falls within the contact's stated week,
    # search for the benefit week whose Sun–Sat window contains the new date
    # and silently move the contact there.
    new_date = body.contact_date
    if new_date != existing.get("contact_date"):
        current_week = await db.benefit_weeks.find_one(
            {"id": body.benefit_week_id, "user_id": user["id"]}, {"_id": 0}
        )
        date_fits = (
            current_week
            and current_week["week_start"] <= new_date <= current_week["week_end"]
        )
        if not date_fits:
            correct_week = await db.benefit_weeks.find_one(
                {
                    "user_id": user["id"],
                    "week_start": {"$lte": new_date},
                    "week_end": {"$gte": new_date},
                }
            )
            if correct_week:
                update["benefit_week_id"] = correct_week["id"]

    await db.contacts.update_one({"id": cid, "user_id": user["id"]}, {"$set": update})
    keys = [
        "contact_date", "employer_name", "employer_address", "contact_method",
        "type_of_work", "position_applied", "person_contacted", "result", "source_url",
    ]
    diff = diff_dict(existing, update, keys)
    await log_audit(
        user["id"], "UPDATE", "contact", cid, f"{body.employer_name} — {diff}"
    )
    c = await db.contacts.find_one({"id": cid}, {"_id": 0})
    return c



@router.delete("/contacts/{cid}")
async def delete_contact(cid: str, user=Depends(get_current_user)):
    res = await db.contacts.delete_one({"id": cid, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await log_audit(user["id"], "DELETE", "contact", cid, "Contact deleted")
    return {"ok": True}



# ============== CSV Export ==============
@router.get("/contacts/export.csv")
async def export_contacts_csv(
    week_id: Optional[str] = None, user=Depends(get_current_user)
):
    q = {"user_id": user["id"]}
    if week_id:
        # Single-week export is available on every tier.
        q["benefit_week_id"] = week_id
    else:
        # Exporting the full history is a paid feature.
        await sub.gate_feature(db, user["id"], "csv_export_full_history")
        cid = await get_active_claimant_id(user["id"])
        if cid:
            q["$or"] = [{"claimant_id": cid}, {"claimant_id": {"$exists": False}}]
    contacts = (
        await db.contacts.find(q, {"_id": 0}).sort("contact_date", 1).to_list(10000)
    )
    buf = io.StringIO()
    fields = [
        "contact_date", "employer_name", "employer_address", "contact_method",
        "position_applied", "type_of_work", "person_contacted", "result", "source_url",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for c in contacts:
        writer.writerow(c)
    buf.seek(0)
    await log_audit(user["id"], "EXPORT_CSV", "contact", week_id, f"Exported {len(contacts)} contacts to CSV")
    fname = f"contacts_{week_id or 'all'}.csv"
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )
