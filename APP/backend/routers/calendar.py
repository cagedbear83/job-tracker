# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403

router = APIRouter()



@router.get("/calendar-events")
async def list_calendar_events(user=Depends(get_current_user)):
    events = (
        await db.calendar_events.find(
            {"user_id": user["id"]}, {"_id": 0}
        )
        .sort("event_date", 1)
        .to_list(1000)
    )
    return events



@router.post("/calendar-events", status_code=201)
async def create_calendar_event(
    body: CalendarEventIn, user=Depends(get_current_user)
):
    await sub.gate_feature(db, user["id"], "calendar_events")
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "event_date": body.event_date,
        "event_type": body.event_type,
        "title": body.title,
        "notes": body.notes,
        "claimant_id": body.claimant_id,
        "created_at": datetime.utcnow(),
    }
    await db.calendar_events.insert_one(doc)
    doc.pop("_id", None)
    await log_audit(
        user["id"], "CREATE", "calendar_event", doc["id"],
        f"{body.event_type}: {body.title} on {body.event_date}"
    )
    return doc



@router.put("/calendar-events/{eid}")
async def update_calendar_event(
    eid: str, body: CalendarEventIn, user=Depends(get_current_user)
):
    await sub.gate_feature(db, user["id"], "calendar_events")
    existing = await db.calendar_events.find_one(
        {"id": eid, "user_id": user["id"]}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    update = {
        "event_date": body.event_date,
        "event_type": body.event_type,
        "title": body.title,
        "notes": body.notes,
        "claimant_id": body.claimant_id,
    }
    await db.calendar_events.update_one(
        {"id": eid, "user_id": user["id"]}, {"$set": update}
    )
    await log_audit(
        user["id"], "UPDATE", "calendar_event", eid,
        f"{body.event_type}: {body.title}"
    )
    doc = await db.calendar_events.find_one({"id": eid}, {"_id": 0})
    return doc



@router.delete("/calendar-events/{eid}")
async def delete_calendar_event(eid: str, user=Depends(get_current_user)):
    res = await db.calendar_events.delete_one({"id": eid, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await log_audit(user["id"], "DELETE", "calendar_event", eid, "Event deleted")
    return {"ok": True}
