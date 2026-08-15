# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403

router = APIRouter()



# ============== Claimant Profiles (multi) ==============
@router.get("/profile")
async def get_active_profile(user=Depends(get_current_user)):
    cid = await get_active_claimant_id(user["id"])
    if not cid:
        return None
    return await db.profiles.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0})



@router.put("/profile")
async def upsert_profile(body: ProfileIn, user=Depends(get_current_user)):
    cid = await get_active_claimant_id(user["id"])
    now = datetime.now(timezone.utc).isoformat()
    if cid:
        existing = (
            await db.profiles.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0})
            or {}
        )
        update = body.model_dump()
        update["updated_at"] = now
        await db.profiles.update_one(
            {"id": cid, "user_id": user["id"]}, {"$set": update}
        )
        diff = diff_dict(existing, update, list(body.model_dump().keys()))
        await log_audit(
            user["id"], "UPDATE", "claimant", cid, f"Claimant updated — {diff}"
        )
        return {**existing, **update}
    pid = str(uuid.uuid4())
    doc = {"id": pid, "user_id": user["id"], "updated_at": now, **body.model_dump()}
    await db.profiles.insert_one(doc)
    await db.users.update_one({"id": user["id"]}, {"$set": {"active_claimant_id": pid}})
    await log_audit(
        user["id"], "CREATE", "claimant", pid, f"Claimant created: {body.label}"
    )
    doc.pop("_id", None)
    return doc
