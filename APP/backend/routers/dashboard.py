# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403

router = APIRouter()


# ============== Dashboard summary ==============
@router.get("/dashboard")
async def dashboard(user=Depends(get_current_user)):
    cid = await get_active_claimant_id(user["id"])
    week_q = {"user_id": user["id"]}
    contact_q = {"user_id": user["id"]}
    if cid:
        week_q["$or"] = [{"claimant_id": cid}, {"claimant_id": {"$exists": False}}]
        contact_q["$or"] = [{"claimant_id": cid}, {"claimant_id": {"$exists": False}}]
    weeks = await db.benefit_weeks.count_documents(week_q)
    contacts = await db.contacts.count_documents(contact_q)
    compliant = 0
    non_compliant = 0
    recent = (
        await db.benefit_weeks.find(week_q, {"_id": 0})
        .sort("week_start", -1)
        .to_list(100)
    )
    for w in recent:
        n = await db.contacts.count_documents({"benefit_week_id": w["id"]})
        if n >= 3:
            compliant += 1
        else:
            non_compliant += 1
    profile = None
    if cid:
        profile = await db.profiles.find_one(
            {"id": cid, "user_id": user["id"]}, {"_id": 0}
        )
    return {
        "total_weeks": weeks,
        "total_contacts": contacts,
        "compliant_weeks": compliant,
        "non_compliant_weeks": non_compliant,
        "profile_complete": bool(
            profile and profile.get("first_name") and profile.get("last_name")
        ),
        "active_claimant_id": cid,
    }



# ============== Dashboard Trend ==============
@router.get("/dashboard/trend")
async def dashboard_trend(weeks: int = 12, user=Depends(get_current_user)):
    await sub.gate_feature(db, user["id"], "advanced_analytics")
    cid = await get_active_claimant_id(user["id"])
    q = {"user_id": user["id"]}
    if cid:
        q["$or"] = [{"claimant_id": cid}, {"claimant_id": {"$exists": False}}]
    recent = (
        await db.benefit_weeks.find(q, {"_id": 0})
        .sort("week_start", -1)
        .to_list(min(max(weeks, 1), 52))
    )
    recent.reverse()
    out = []
    for w in recent:
        n = await db.contacts.count_documents({"benefit_week_id": w["id"]})
        out.append({
            "week_start": w["week_start"],
            "week_end": w["week_end"],
            "contacts": n,
            "target": 3,
            "compliant": n >= 3,
        })
    return out
