# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403

router = APIRouter()



# ============== Benefit Weeks ==============
@router.get("/benefit-weeks")
async def list_weeks(user=Depends(get_current_user)):
    cid = await get_active_claimant_id(user["id"])
    q = {"user_id": user["id"]}
    if cid:
        q["$or"] = [{"claimant_id": cid}, {"claimant_id": {"$exists": False}}]
    weeks = (
        await db.benefit_weeks.find(q, {"_id": 0}).sort("week_start", -1).to_list(1000)
    )
    for w in weeks:
        w["contact_count"] = await db.contacts.count_documents(
            {"benefit_week_id": w["id"]}
        )
    return weeks



@router.post("/benefit-weeks")
async def create_week(body: BenefitWeekIn, user=Depends(get_current_user)):
    cid = await get_active_claimant_id(user["id"])
    wid = str(uuid.uuid4())
    doc = {
        "id": wid,
        "user_id": user["id"],
        "claimant_id": cid,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **body.model_dump(),
    }
    await db.benefit_weeks.insert_one(doc)
    await log_audit(
        user["id"],
        "CREATE",
        "benefit_week",
        wid,
        f"Week {body.week_start} – {body.week_end}",
    )
    doc.pop("_id", None)
    return doc



@router.get("/benefit-weeks/{wid}")
async def get_week(wid: str, user=Depends(get_current_user)):
    w = await db.benefit_weeks.find_one({"id": wid, "user_id": user["id"]}, {"_id": 0})
    if not w:
        raise HTTPException(status_code=404, detail="Not found")
    return w



@router.put("/benefit-weeks/{wid}")
async def update_week(wid: str, body: BenefitWeekIn, user=Depends(get_current_user)):
    existing = await db.benefit_weeks.find_one(
        {"id": wid, "user_id": user["id"]}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    update = body.model_dump()
    await db.benefit_weeks.update_one(
        {"id": wid, "user_id": user["id"]}, {"$set": update}
    )
    diff = diff_dict(existing, update, ["week_start", "week_end", "notes", "certified"])
    await log_audit(
        user["id"],
        "UPDATE",
        "benefit_week",
        wid,
        f"Week {body.week_start}–{body.week_end} — {diff}",
    )
    w = await db.benefit_weeks.find_one({"id": wid}, {"_id": 0})
    return w



@router.delete("/benefit-weeks/{wid}")
async def delete_week(wid: str, user=Depends(get_current_user)):
    res = await db.benefit_weeks.delete_one({"id": wid, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await db.contacts.delete_many({"benefit_week_id": wid, "user_id": user["id"]})
    await log_audit(
        user["id"], "DELETE", "benefit_week", wid, "Week deleted (cascaded contacts)"
    )
    return {"ok": True}
