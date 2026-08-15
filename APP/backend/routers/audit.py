# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403

router = APIRouter()



# ============== Audit Log ==============
@router.get("/audit-log")
async def get_audit(
    q: Optional[str] = None,
    action: Optional[str] = None,
    entity: Optional[str] = None,
    limit: int = 2000,
    user=Depends(get_current_user),
):
    query = {"user_id": user["id"]}
    if action and action != "ALL":
        query["action"] = action
    if entity and entity != "ALL":
        query["entity"] = entity
    if q:
        query["detail"] = {"$regex": q, "$options": "i"}
    items = (
        await db.audit_log.find(query, {"_id": 0})
        .sort("timestamp", -1)
        .to_list(min(max(limit, 1), 5000))
    )
    return items
