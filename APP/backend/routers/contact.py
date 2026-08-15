# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403
from core import _contact_cors_headers, _generate_ref

router = APIRouter()


@router.options("/contact")
async def contact_options(request: Request):
    return Response(status_code=200, headers=_contact_cors_headers(request))



@router.post("/contact")
async def contact_form(payload: ContactRequest, request: Request):
    import re
    phone_digits = re.sub(r"\D", "", payload.phone)
    if len(phone_digits) != 10:
        raise HTTPException(status_code=400, detail="Invalid phone number — must be 10 digits.")

    ref = _generate_ref(payload.reason)

    support_html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#0033A0;padding:24px 32px;">
        <h2 style="color:#fff;margin:0;font-size:20px;">New Contact Form Submission</h2>
        <p style="color:#93AECF;margin:6px 0 0;font-size:13px;">Reference: <strong style="color:#fff;">{ref}</strong></p>
      </div>
      <div style="padding:24px 32px;border:1px solid #e4e4e7;border-top:none;">
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <tr><td style="padding:8px 0;color:#52525b;width:140px;">Reference</td>
              <td style="padding:8px 0;font-weight:700;color:#0033A0;">{ref}</td></tr>
          <tr><td style="padding:8px 0;color:#52525b;">Name</td>
              <td style="padding:8px 0;font-weight:600;">{payload.first_name} {payload.last_name}</td></tr>
          <tr><td style="padding:8px 0;color:#52525b;">Email</td>
              <td style="padding:8px 0;"><a href="mailto:{payload.email}">{payload.email}</a></td></tr>
          <tr><td style="padding:8px 0;color:#52525b;">Phone</td>
              <td style="padding:8px 0;">{payload.phone}</td></tr>
          <tr><td style="padding:8px 0;color:#52525b;">Reason</td>
              <td style="padding:8px 0;">{payload.reason}</td></tr>
        </table>
        <hr style="border:none;border-top:1px solid #e4e4e7;margin:16px 0;">
        <p style="color:#52525b;font-size:13px;margin:0 0 8px;">Message:</p>
        <p style="font-size:14px;white-space:pre-wrap;margin:0;">{html.escape(payload.message)}</p>
      </div>
    </div>
    """

    customer_html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#0033A0;padding:24px 32px;">
        <h2 style="color:#fff;margin:0;font-size:20px;">We received your message</h2>
        <p style="color:#93AECF;margin:6px 0 0;font-size:13px;">Reference: <strong style="color:#fff;">{ref}</strong></p>
      </div>
      <div style="padding:24px 32px;border:1px solid #e4e4e7;border-top:none;">
        <p style="font-size:14px;">Hi {html.escape(payload.first_name)},</p>
        <p style="font-size:14px;">
          Thanks for reaching out to Illinois UI Job Search Tracker. We&apos;ve received
          your message and will get back to you at this email address. Our average
          response time is <strong>2 business days</strong>.
        </p>
        <div style="background:#E8EDF7;border-left:4px solid #0033A0;padding:12px 16px;margin:16px 0;">
          <p style="margin:0;font-size:13px;color:#52525b;">Your reference number</p>
          <p style="margin:4px 0 0;font-size:20px;font-weight:700;color:#0033A0;letter-spacing:1px;">{ref}</p>
          <p style="margin:4px 0 0;font-size:12px;color:#52525b;">Include this in any follow-up so we can find your submission quickly.</p>
        </div>
        <hr style="border:none;border-top:1px solid #e4e4e7;margin:20px 0;">
        <p style="font-size:13px;color:#52525b;margin:0 0 12px;">Here&apos;s a recap of what you sent us:</p>
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
          <tr><td style="padding:6px 0;color:#52525b;width:140px;">Reason</td>
              <td style="padding:6px 0;">{html.escape(payload.reason)}</td></tr>
        </table>
        <div style="background:#f4f4f5;padding:12px 16px;margin-top:12px;font-size:13px;white-space:pre-wrap;">{html.escape(payload.message)}</div>
        <hr style="border:none;border-top:1px solid #e4e4e7;margin:20px 0;">
        <p style="font-size:12px;color:#52525b;margin:0;">
          Illinois UI Job Search Tracker is operated by KMG123 Enterprises LLC.
          This is an automated confirmation — please do not reply to this email.
          To follow up, visit
          <a href="https://illinoisjobtracker.com/contact">illinoisjobtracker.com/contact</a>.
        </p>
      </div>
    </div>
    """

    # Email 1 → support inbox (subject includes ref for easy inbox search)
    await send_email(
        "support@illinoisjobtracker.app",
        f"[{ref}] Contact form: {payload.reason} — {payload.first_name} {payload.last_name}",
        support_html,
    )

    # Email 2 → customer confirmation
    await send_email(
        payload.email,
        f"[{ref}] We received your message — Illinois UI Job Search Tracker",
        customer_html,
    )

    return JSONResponse({"status": "sent", "ref": ref}, headers=_contact_cors_headers(request))
