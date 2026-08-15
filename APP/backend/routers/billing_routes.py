# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403

router = APIRouter()



# ============== Billing (Stripe) ==============
@router.post("/billing/checkout")
async def billing_checkout(
    payload: billing_logic.CheckoutRequest, user=Depends(get_current_user)
):
    return await billing_logic.create_checkout_session(
        db, os.environ.get("FRONTEND_URL", "http://localhost:3000"), user, payload
    )



@router.post("/billing/portal")
async def billing_portal(user=Depends(get_current_user)):
    return await billing_logic.create_portal_session(
        db, os.environ.get("FRONTEND_URL", "http://localhost:3000"), user
    )



@router.get("/billing/status")
async def billing_status_route(user=Depends(get_current_user)):
    return await billing_logic.billing_status(db, user)
