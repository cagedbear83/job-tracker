# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403
from core import _send_user_reminder

router = APIRouter()



@router.post("/reminders/test")
@rate_limit(RATE_LIMIT_REMINDER_TEST)
async def reminder_test(
    request: Request, kind: str = "friday", user=Depends(get_current_user)
):
    if kind not in ("sunday", "wednesday", "friday", "saturday"):
        raise HTTPException(status_code=400, detail="kind must be sunday|wednesday|friday|saturday")
    n = await _send_user_reminder(user, kind)
    return {"sent": n, "kind": kind}
