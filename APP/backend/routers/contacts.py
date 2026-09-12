# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403
from core import _add_business_days
import re as _re

router = APIRouter()



# ============== Work Search Contacts ==============
@router.get("/contacts")
async def list_contacts(week_id: Optional[str] = None, user=Depends(get_current_user)):
    query = {"user_id": user["id"]}
    if week_id:
        query["benefit_week_id"] = week_id
    else:
        cid = await get_active_claimant_id(user["id"])
        if cid:
            query["$or"] = [{"claimant_id": cid}, {"claimant_id": {"$exists": False}}]
    items = (
        await db.contacts.find(query, {"_id": 0}).sort("contact_date", -1).to_list(5000)
    )
    return items



@router.post("/contacts")
async def create_contact(body: ContactIn, user=Depends(get_current_user)):
    w = await db.benefit_weeks.find_one(
        {"id": body.benefit_week_id, "user_id": user["id"]}, {"_id": 0}
    )
    if not w:
        raise HTTPException(status_code=404, detail="Benefit week not found")
    cid = str(uuid.uuid4())
    doc = {
        "id": cid,
        "user_id": user["id"],
        "claimant_id": w.get("claimant_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        **body.model_dump(),
    }
    await db.contacts.insert_one(doc)
    await log_audit(
        user["id"], "CREATE", "contact", cid, f"Contact: {body.employer_name}"
    )

    # Auto-add a Calendar follow-up reminder 5 business days after this
    # contact is LOGGED (i.e. from today, when it's submitted — not from the
    # contact_date itself, which can be back-dated). Uses event_type "other"
    # since the schema doesn't have a dedicated "follow_up" type, and rides
    # the same generic reminder engine as every other Calendar event (see
    # core.py's _broadcast_event_reminders), so it gets a 3-days-before and
    # a morning-of email reminder with no special-cased scheduling needed.
    tz = pytz.timezone("America/Chicago")
    followup_date = _add_business_days(datetime.now(tz).date(), 5)
    await db.calendar_events.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "event_date": followup_date.isoformat(),
        "event_type": "other",
        "title": f"Follow up — {body.employer_name}",
        "notes": f"Auto-added: follow up on your {body.contact_date} contact with {body.employer_name}.",
        "claimant_id": w.get("claimant_id"),
        "created_at": datetime.now(timezone.utc),
    })

    doc.pop("_id", None)
    return doc



@router.put("/contacts/{cid}")
async def update_contact(cid: str, body: ContactIn, user=Depends(get_current_user)):
    existing = await db.contacts.find_one(
        {"id": cid, "user_id": user["id"]}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    update = body.model_dump()

    # ── Auto-reassign to the correct benefit week when the date changes ──────
    # If the edited date no longer falls within the contact's stated week,
    # search for the benefit week whose Sun–Sat window contains the new date
    # and silently move the contact there.
    new_date = body.contact_date
    if new_date != existing.get("contact_date"):
        current_week = await db.benefit_weeks.find_one(
            {"id": body.benefit_week_id, "user_id": user["id"]}, {"_id": 0}
        )
        date_fits = (
            current_week
            and current_week["week_start"] <= new_date <= current_week["week_end"]
        )
        if not date_fits:
            correct_week = await db.benefit_weeks.find_one(
                {
                    "user_id": user["id"],
                    "week_start": {"$lte": new_date},
                    "week_end": {"$gte": new_date},
                }
            )
            if correct_week:
                update["benefit_week_id"] = correct_week["id"]

    await db.contacts.update_one({"id": cid, "user_id": user["id"]}, {"$set": update})
    keys = [
        "contact_date", "employer_name", "employer_address", "contact_method",
        "type_of_work", "position_applied", "person_contacted", "result", "source_url",
        "tags",
    ]
    diff = diff_dict(existing, update, keys)
    await log_audit(
        user["id"], "UPDATE", "contact", cid, f"{body.employer_name} — {diff}"
    )
    c = await db.contacts.find_one({"id": cid}, {"_id": 0})
    return c



@router.delete("/contacts/{cid}")
async def delete_contact(cid: str, user=Depends(get_current_user)):
    res = await db.contacts.delete_one({"id": cid, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await log_audit(user["id"], "DELETE", "contact", cid, "Contact deleted")
    return {"ok": True}



# ============== Cross-Week Contact Search ==============

def _build_text_query(q: str) -> dict:
    """
    Build a MongoDB $or query that checks q (case-insensitive regex) against
    every searchable text field on a contact document.
    """
    pattern = {"$regex": _re.escape(q.strip()), "$options": "i"}
    return {
        "$or": [
            {"employer_name": pattern},
            {"employer_address": pattern},
            {"type_of_work": pattern},
            {"position_applied": pattern},
            {"person_contacted": pattern},
            {"result": pattern},
            {"source_url": pattern},
            {"contact_method": pattern},
        ]
    }


async def _get_current_week(user_id: str) -> Optional[dict]:
    """
    Return the benefit week whose window contains today (Chicago time).
    Falls back to the most recently created week if no week spans today.
    """
    tz = pytz.timezone("America/Chicago")
    today = datetime.now(tz).date().isoformat()

    current = await db.benefit_weeks.find_one(
        {
            "user_id": user_id,
            "week_start": {"$lte": today},
            "week_end": {"$gte": today},
        },
        {"_id": 0},
    )
    if current:
        return current

    # Fallback: most recently created week
    weeks = (
        await db.benefit_weeks.find({"user_id": user_id}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(1)
    )
    return weeks[0] if weeks else None


@router.get("/contacts/search")
async def search_contacts(
    q: Optional[str] = None,
    result: Optional[str] = None,
    method: Optional[str] = None,
    type_of_work: Optional[str] = None,
    tag: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    week_id: Optional[str] = None,
    user=Depends(get_current_user),
):
    """
    Cross-week contact search with facet counts.

    Free-tier hard gate: contacts from weeks other than the current benefit
    week are returned as stub rows — {gated: True, id, week_id, week_start,
    week_end} — with no field values. The frontend renders these as blurred
    placeholder rows with an upgrade CTA.

    Paid tiers receive full field values for all matching contacts.

    Response shape:
    {
        "results": [ ...contacts or stub rows... ],
        "facets": {
            "result": [{"value": "Applied", "count": 12}, ...],
            "method": [...],
            "type_of_work": [...],
            "tags": [{"id": "...", "name": "...", "count": 3}, ...],
        },
        "gated": bool  // true if any rows were hard-gated (free tier)
    }
    """
    from subscription import get_user_tier, Tier  # local import avoids circular

    tier = await get_user_tier(db, user["id"])
    is_free = tier == Tier.FREE

    # ── Resolve current week for free-tier gating ────────────────────────────
    current_week: Optional[dict] = None
    if is_free:
        current_week = await _get_current_week(user["id"])

    # ── Build base query (shared by both results + facets) ───────────────────
    base_query: dict = {"user_id": user["id"]}

    if q and q.strip():
        base_query.update(_build_text_query(q))

    if result:
        base_query["result"] = result
    if method:
        base_query["contact_method"] = method
    if type_of_work:
        base_query["type_of_work"] = type_of_work
    if tag:
        base_query["tags"] = tag
    if date_from:
        base_query.setdefault("contact_date", {})["$gte"] = date_from
    if date_to:
        base_query.setdefault("contact_date", {})["$lte"] = date_to
    if week_id:
        base_query["benefit_week_id"] = week_id

    # ── Fetch matching contacts ───────────────────────────────────────────────
    raw_contacts = (
        await db.contacts.find(base_query, {"_id": 0})
        .sort("contact_date", -1)
        .to_list(2000)
    )

    # ── Gather week metadata for all referenced weeks ────────────────────────
    week_ids = list({c["benefit_week_id"] for c in raw_contacts if c.get("benefit_week_id")})
    weeks_by_id: dict[str, dict] = {}
    if week_ids:
        week_docs = await db.benefit_weeks.find(
            {"id": {"$in": week_ids}, "user_id": user["id"]}, {"_id": 0}
        ).to_list(len(week_ids))
        weeks_by_id = {w["id"]: w for w in week_docs}

    # ── Apply tier gate — build result rows ──────────────────────────────────
    current_week_id = current_week["id"] if current_week else None
    any_gated = False
    results = []

    for contact in raw_contacts:
        wid = contact.get("benefit_week_id")
        week_doc = weeks_by_id.get(wid, {})

        if is_free and wid != current_week_id:
            # Hard gate: return stub with no field values
            any_gated = True
            results.append({
                "gated": True,
                "id": contact["id"],
                "week_id": wid,
                "week_start": week_doc.get("week_start"),
                "week_end": week_doc.get("week_end"),
            })
        else:
            row = {**contact, "gated": False}
            row["week_start"] = week_doc.get("week_start")
            row["week_end"] = week_doc.get("week_end")
            results.append(row)

    # ── Facet counts — run against base text/date/week query only ────────────
    # Counts use the *keyword + date* query but NOT the active field filter,
    # so the filter popover shows how many results exist per option.
    facet_base: dict = {"user_id": user["id"]}
    if q and q.strip():
        facet_base.update(_build_text_query(q))
    if date_from:
        facet_base.setdefault("contact_date", {})["$gte"] = date_from
    if date_to:
        facet_base.setdefault("contact_date", {})["$lte"] = date_to
    if week_id:
        facet_base["benefit_week_id"] = week_id
    # For free tier, limit facet counts to current week so they don't hint at
    # gated data.
    if is_free and current_week_id:
        facet_base["benefit_week_id"] = current_week_id

    async def _count_by_field(field: str) -> list[dict]:
        pipeline = [
            {"$match": facet_base},
            {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
            {"$match": {"_id": {"$ne": None, "$ne": ""}}},
            {"$sort": {"count": -1}},
        ]
        docs = await db.contacts.aggregate(pipeline).to_list(100)
        return [{"value": d["_id"], "count": d["count"]} for d in docs]

    async def _count_tags() -> list[dict]:
        pipeline = [
            {"$match": {**facet_base, "tags": {"$exists": True, "$ne": []}}},
            {"$unwind": "$tags"},
            {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        docs = await db.contacts.aggregate(pipeline).to_list(200)
        tag_ids = [d["_id"] for d in docs]
        counts_by_id = {d["_id"]: d["count"] for d in docs}

        # Resolve tag names
        tag_docs = await db.tags.find(
            {"user_id": user["id"], "id": {"$in": tag_ids}}, {"_id": 0}
        ).to_list(len(tag_ids))
        tag_names = {t["id"]: t["name"] for t in tag_docs}

        return [
            {"id": tid, "name": tag_names.get(tid, tid), "count": counts_by_id[tid]}
            for tid in tag_ids
        ]

    import asyncio as _asyncio
    result_counts, method_counts, tow_counts, tag_counts = await _asyncio.gather(
        _count_by_field("result"),
        _count_by_field("contact_method"),
        _count_by_field("type_of_work"),
        _count_tags(),
    )

    return {
        "results": results,
        "facets": {
            "result": result_counts,
            "method": method_counts,
            "type_of_work": tow_counts,
            "tags": tag_counts,
        },
        "gated": any_gated,
    }


# ============== CSV Export ==============
@router.get("/contacts/export.csv")
async def export_contacts_csv(
    week_id: Optional[str] = None, user=Depends(get_current_user)
):
    q = {"user_id": user["id"]}
    if week_id:
        # Single-week export is available on every tier.
        q["benefit_week_id"] = week_id
    else:
        # Exporting the full history is a paid feature.
        await sub.gate_feature(db, user["id"], "csv_export_full_history")
        cid = await get_active_claimant_id(user["id"])
        if cid:
            q["$or"] = [{"claimant_id": cid}, {"claimant_id": {"$exists": False}}]
    contacts = (
        await db.contacts.find(q, {"_id": 0}).sort("contact_date", 1).to_list(10000)
    )
    buf = io.StringIO()
    fields = [
        "contact_date", "employer_name", "employer_address", "contact_method",
        "position_applied", "type_of_work", "person_contacted", "result", "source_url",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for c in contacts:
        writer.writerow(c)
    buf.seek(0)
    await log_audit(user["id"], "EXPORT_CSV", "contact", week_id, f"Exported {len(contacts)} contacts to CSV")
    fname = f"contacts_{week_id or 'all'}.csv"
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )
