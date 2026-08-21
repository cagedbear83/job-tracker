# Case-worker invitations, backed by Clerk.
#
# This used to be a local invite-code system: a `db.invites` row with a random
# code, a hand-built HTML email, a GET /invite/{code} lookup, and a
# POST /invite/redeem that created the account and signed the user in.
#
# Clerk now owns that lifecycle — it sends the email, tracks
# pending / accepted / revoked, and enforces expiry. The two endpoints the
# frontend used to drive redemption are gone:
#
#   GET  /invite/{code}   -> Clerk ticket flow (__clerk_ticket in the URL)
#   POST /invite/redeem   -> Clerk <SignUp/> completes it
#
# The claimant metadata this app needs rides along in the invitation's
# public_metadata, which Clerk copies onto the user it creates. clerk_auth's
# get_or_create_user reads it back to attach the claimant label and the
# inviting case worker, and routers/auth.py's onboarding step consumes the
# label when it builds the profile.
from core import *  # noqa: F401,F403

import clerk_auth

router = APIRouter()


def _signup_url() -> str:
    """Where an invitee lands after clicking the emailed link.

    Clerk appends `__clerk_ticket` to this URL; the <SignUp/> component picks
    it up and completes the invitation.
    """
    base = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    return f"{base}/sign-up"


@router.post("/admin/invites")
async def create_invite(body: InviteCreate, admin=Depends(require_admin)):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(
            status_code=400, detail="A user with that email already exists"
        )

    invitation = clerk_auth.create_invitation(
        email=email,
        redirect_url=_signup_url(),
        claimant_label=body.claimant_label or "Primary",
        invited_by=admin["id"],
        note=body.note,
    )

    await log_audit(
        admin["id"],
        "INVITE_CREATE",
        "invite",
        invitation.get("id", ""),
        f"Invite for {email}",
    )
    return invitation


@router.get("/admin/invites")
async def list_invites(admin=Depends(require_admin)):
    """Pending and historical invitations, straight from Clerk.

    Shaped to match what the admin table rendered off the old local rows so
    the frontend keeps working: `email`, `claimant_label`, `note`, `used`.
    """
    items = clerk_auth.list_invitations()
    out = []
    for inv in items:
        meta = inv.get("public_metadata") or {}
        out.append(
            {
                "id": inv.get("id"),
                "email": inv.get("email_address"),
                "claimant_label": meta.get("claimant_label", "Primary"),
                "note": meta.get("note", ""),
                "status": inv.get("status"),
                "used": inv.get("status") == "accepted",
                "created_at": inv.get("created_at"),
                "expires_at": inv.get("expires_at"),
                "invited_by": meta.get("invited_by", ""),
            }
        )
    return out


@router.delete("/admin/invites/{invitation_id}")
async def revoke_invite(invitation_id: str, admin=Depends(require_admin)):
    """Revoke a pending invitation.

    Takes a Clerk invitation id (inv_...) where this used to take the local
    random code.
    """
    clerk_auth.revoke_invitation(invitation_id)
    await log_audit(
        admin["id"], "INVITE_REVOKE", "invite", invitation_id, "Invite revoked"
    )
    return {"ok": True}
