"""
routers/tags.py — Per-user tag management for work-search contacts.

Tags are stored in the `tags` collection as {id, user_id, name, created_at}.
Contacts reference them by ID in the `tags: list[str]` field on ContactIn.
"""
import re as _re

from core import *  # noqa: F401,F403

router = APIRouter()


# ============== Tags ==============

@router.get("/tags")
async def list_tags(user=Depends(get_current_user)):
    """Return all tags for this user, sorted alphabetically."""
    tags = (
        await db.tags.find({"user_id": user["id"]}, {"_id": 0})
        .sort("name", 1)
        .to_list(1000)
    )
    return tags


@router.post("/tags")
async def create_tag(body: dict, user=Depends(get_current_user)):
    """
    Create a new tag (case-insensitive dedup). Returns existing tag if the
    name already exists so the caller can treat POST as upsert-by-name.
    """
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Tag name is required")

    # Case-insensitive duplicate check
    pattern = f"^{_re.escape(name)}$"
    existing = await db.tags.find_one(
        {"user_id": user["id"], "name": {"$regex": pattern, "$options": "i"}},
        {"_id": 0},
    )
    if existing:
        return existing

    tag = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.tags.insert_one(tag)
    tag.pop("_id", None)
    return tag


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: str, user=Depends(get_current_user)):
    """Delete a tag and remove it from every contact that references it."""
    res = await db.tags.delete_one({"id": tag_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Scrub the tag ID from all contacts owned by this user
    await db.contacts.update_many(
        {"user_id": user["id"], "tags": tag_id},
        {"$pull": {"tags": tag_id}},
    )
    return {"ok": True}
