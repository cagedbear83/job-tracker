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

    # Fetch totals, recent week IDs, and profile concurrently.
    # We only need the "id" field from each week to run the contact aggregation.
    import asyncio

    async def _none():
        return None

    profile_coro = (
        db.profiles.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0})
        if cid
        else _none()
    )
    weeks_total, contacts_total, recent, profile = await asyncio.gather(
        db.benefit_weeks.count_documents(week_q),
        db.contacts.count_documents(contact_q),
        db.benefit_weeks.find(week_q, {"_id": 0, "id": 1})
            .sort("week_start", -1)
            .to_list(100),
        profile_coro,
    )

    # Single aggregation replaces up to 100 sequential count_documents calls.
    compliant = 0
    non_compliant = 0
    week_ids = [w["id"] for w in recent]
    if week_ids:
        agg = await db.contacts.aggregate([
            {"$match": {"benefit_week_id": {"$in": week_ids}}},
            {"$group": {"_id": "$benefit_week_id", "count": {"$sum": 1}}},
        ]).to_list(len(week_ids))
        counts = {row["_id"]: row["count"] for row in agg}
        for wid in week_ids:
            if counts.get(wid, 0) >= 3:
                compliant += 1
            else:
                non_compliant += 1

    return {
        "total_weeks": weeks_total,
        "total_contacts": contacts_total,
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

    # Single aggregation replaces up to 52 sequential count_documents calls.
    week_ids = [w["id"] for w in recent]
    contact_counts: dict = {}
    if week_ids:
        agg = await db.contacts.aggregate([
            {"$match": {"benefit_week_id": {"$in": week_ids}}},
            {"$group": {"_id": "$benefit_week_id", "count": {"$sum": 1}}},
        ]).to_list(len(week_ids))
        contact_counts = {row["_id"]: row["count"] for row in agg}

    out = []
    for w in recent:
        n = contact_counts.get(w["id"], 0)
        out.append({
            "week_start": w["week_start"],
            "week_end": w["week_end"],
            "contacts": n,
            "target": 3,
            "compliant": n >= 3,
        })
    return out
