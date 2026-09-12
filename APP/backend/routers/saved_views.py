"""
routers/saved_views.py — Named saved filter views for the contacts search UI.

Each saved view stores a label + an arbitrary `filters` dict (whatever the
frontend composes from the Filter popover: result, method, type_of_work, tags,
date_from, date_to, week_id).  Retrieval is user-scoped; no tier gate — saved
views are available on all plans.
"""
from core import *  # noqa: F401,F403

router = APIRouter()


# ============== Saved Views ==============

@router.get("/saved-views")
async def list_saved_views(user=Depends(get_current_user)):
    """Return all saved views for this user, sorted by name."""
    views = (
        await db.saved_views.find({"user_id": user["id"]}, {"_id": 0})
        .sort("name", 1)
        .to_list(200)
    )
    return views


@router.post("/saved-views")
async def create_saved_view(body: dict, user=Depends(get_current_user)):
    """
    Create a named saved view.

    Expected body: { name: str, filters: { result?, method?, type_of_work?,
    tags?: str[], date_from?, date_to?, week_id?, q? } }
    """
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="View name is required")

    filters = body.get("filters") or {}
    if not isinstance(filters, dict):
        raise HTTPException(status_code=422, detail="filters must be an object")

    # Enforce a reasonable cap per user
    count = await db.saved_views.count_documents({"user_id": user["id"]})
    if count >= 50:
        raise HTTPException(
            status_code=400,
            detail="Maximum of 50 saved views reached. Delete one to create another.",
        )

    vid = str(uuid.uuid4())
    doc = {
        "id": vid,
        "user_id": user["id"],
        "name": name,
        "filters": filters,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.saved_views.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/saved-views/{view_id}")
async def update_saved_view(view_id: str, body: dict, user=Depends(get_current_user)):
    """Update the name or filters of an existing saved view."""
    existing = await db.saved_views.find_one(
        {"id": view_id, "user_id": user["id"]}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="View not found")

    update: dict = {}
    if "name" in body:
        name = (body["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail="View name is required")
        update["name"] = name
    if "filters" in body:
        if not isinstance(body["filters"], dict):
            raise HTTPException(status_code=422, detail="filters must be an object")
        update["filters"] = body["filters"]

    if update:
        await db.saved_views.update_one(
            {"id": view_id, "user_id": user["id"]}, {"$set": update}
        )

    updated = await db.saved_views.find_one({"id": view_id}, {"_id": 0})
    return updated


@router.delete("/saved-views/{view_id}")
async def delete_saved_view(view_id: str, user=Depends(get_current_user)):
    res = await db.saved_views.delete_one({"id": view_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="View not found")
    return {"ok": True}
