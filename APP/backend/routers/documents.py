# Auto-split from the former monolithic server.py — routes only.
# Shared app state, models, and helpers live in core.py; `from core import *`
# re-exports FastAPI symbols (APIRouter, Depends, HTTPException, File, Form,
# UploadFile, Request, the response classes), the Pydantic models, config,
# db, and the public helpers.
from core import *  # noqa: F401,F403
import io
import magic as _magic          # python-magic: validates actual file bytes
from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError


router = APIRouter()



# ── Document processing helpers ──────────────────────────────────────────────

def _detect_mime(raw: bytes) -> str:
    """Return the MIME type detected from actual file content (not HTTP header)."""
    return _magic.from_buffer(raw[:4096], mime=True)


def _image_to_pdf(raw: bytes) -> bytes:
    """Convert JPEG / PNG / WEBP bytes → a single-page compressed PDF."""
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img)          # honour EXIF rotation
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    # Cap the long edge at 2 000 px to save storage
    MAX_PX = 2000
    if img.width > MAX_PX or img.height > MAX_PX:
        img.thumbnail((MAX_PX, MAX_PX), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PDF", optimize=True)
    return buf.getvalue()


def _compress_pdf(raw: bytes) -> bytes:
    """Losslessly compress a PDF via pypdf stream compression."""
    try:
        reader = PdfReader(io.BytesIO(raw))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        for page in writer.pages:
            page.compress_content_streams()
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
        buf = io.BytesIO()
        writer.write(buf)
        compressed = buf.getvalue()
        # Only use the compressed version if it's actually smaller
        return compressed if len(compressed) < len(raw) else raw
    except PdfReadError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid or corrupt PDF: {exc}",
        ) from exc



@router.post("/documents/upload", status_code=201)
async def upload_document(
    file: UploadFile,
    title: str = Form(...),
    document_type: str = Form("other"),
    received_date: str = Form(""),
    notes: str = Form(""),
    claimant_id: str = Form(""),
    user=Depends(get_current_user),
):
    # Tier enforcement: document storage. Free tier is 0 MB (uploads disabled);
    # paid tiers have a total-storage cap. Check the tier before reading the
    # file so free users are rejected without doing the upload work.
    tier = await sub.get_user_tier(db, user["id"])
    storage_mb = sub.get_tier_limits(tier).get("document_storage_mb") or 0
    if storage_mb <= 0:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "upgrade_required",
                "feature": "document_storage_mb",
                "message": "Document storage requires a paid plan. Upgrade to upload documents.",
            },
        )

    # Case Worker quota is per-seat: 1 GB × number of licensed seats.
    if tier == sub.Tier.CASEWORKER:
        sub_doc = await db.subscriptions.find_one({"user_id": user["id"]})
        seats = max(1, int(sub_doc.get("seats", 1))) if sub_doc else 1
        storage_mb = storage_mb * seats

    if file.content_type not in DOC_MIME_ALLOWLIST:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. Allowed: JPEG, PNG, WEBP, PDF.",
        )
    raw = await file.read(MAX_DOC_BYTES + 1)
    if len(raw) > MAX_DOC_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_DOC_BYTES // (1024*1024)} MB.",
        )

    # Enforce the plan's total-storage cap across all of this user's documents.
    agg = await db.document_files.aggregate(
        [
            {"$match": {"user_id": user["id"]}},
            {"$group": {"_id": None, "total": {"$sum": "$file_size"}}},
        ]
    ).to_list(1)
    used_bytes = agg[0]["total"] if agg else 0
    if used_bytes + len(raw) > storage_mb * 1024 * 1024:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "quota_exceeded",
                "feature": "document_storage_mb",
                "message": (
                    f"This upload would exceed your {storage_mb} MB storage limit. "
                    "Delete a document or upgrade for more space."
                ),
            },
        )
    # ── Security: validate actual content matches claimed MIME ──────────────
    detected_mime = _detect_mime(raw)
    if detected_mime not in DOC_MIME_ALLOWLIST:
        raise HTTPException(
            status_code=415,
            detail=(
                f"File content was detected as '{detected_mime}', which is not allowed. "
                "Please upload a valid JPEG, PNG, WEBP, or PDF."
            ),
        )

    # ── Normalise: images → PDF; compress all PDFs before storage ────────
    base_name = (file.filename or "document").rsplit(".", 1)[0]
    if detected_mime.startswith("image/"):
        try:
            raw = _image_to_pdf(raw)
        except Exception as exc:
            raise HTTPException(
                status_code=422, detail=f"Could not process image: {exc}"
            ) from exc
        stored_content_type = "application/pdf"
        stored_filename = base_name + ".pdf"
    else:
        raw = _compress_pdf(raw)
        stored_content_type = "application/pdf"
        stored_filename = base_name + ".pdf"

    import base64
    file_b64 = base64.b64encode(raw).decode("ascii")
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "claimant_id": claimant_id or None,
        "title": title.strip(),
        "document_type": document_type,
        "received_date": received_date or None,
        "notes": notes.strip(),
        "filename": stored_filename,
        "content_type": stored_content_type,
        "file_data": file_b64,
        "file_size": len(raw),
        "created_at": datetime.utcnow(),
    }
    await db.document_files.insert_one(doc)
    doc.pop("_id", None)
    doc.pop("file_data", None)  # don't return the binary blob in the response
    await log_audit(
        user["id"], "CREATE", "document", doc["id"],
        f"Uploaded: {title} ({document_type})"
    )
    return doc



@router.get("/documents")
async def list_documents(user=Depends(get_current_user)):
    docs = (
        await db.document_files.find(
            {"user_id": user["id"]},
            {"_id": 0, "file_data": 0},  # exclude binary blob from list
        )
        .sort("created_at", -1)
        .to_list(500)
    )
    return docs



@router.get("/documents/{did}/file")
async def serve_document(did: str, user=Depends(get_current_user)):
    doc = await db.document_files.find_one(
        {"id": did, "user_id": user["id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    import base64, io
    raw = base64.b64decode(doc["file_data"])
    filename = doc.get("filename", "document")
    content_type = doc.get("content_type", "application/octet-stream")
    return StreamingResponse(
        io.BytesIO(raw),
        media_type=content_type,
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )



@router.delete("/documents/{did}")
async def delete_document(did: str, user=Depends(get_current_user)):
    res = await db.document_files.delete_one({"id": did, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await log_audit(user["id"], "DELETE", "document", did, "Document deleted")
    return {"ok": True}
