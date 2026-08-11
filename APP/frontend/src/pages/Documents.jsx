import { useEffect, useRef, useState } from "react";
import { api, formatApiError, API } from "@/lib/api";
import { getToken } from "@/lib/tokenStorage";
import {
  FileTextIcon,
  UploadSimpleIcon,
  TrashIcon,
  ArrowSquareOutIcon,
  PlusIcon,
  FileIcon,
  ImageIcon,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";

// ── Document type config ─────────────────────────────────────────────────────
const DOC_TYPES = [
  { value: "determination_letter", label: "Determination Letter" },
  { value: "certification_form",   label: "Certification Form"   },
  { value: "questionnaire",        label: "Questionnaire"        },
  { value: "appeal_notice",        label: "Appeal Notice"        },
  { value: "overpayment_notice",   label: "Overpayment Notice"   },
  { value: "correspondence",       label: "General Correspondence"},
  { value: "other",                label: "Other"                },
];

const docTypeLabel = Object.fromEntries(DOC_TYPES.map((t) => [t.value, t.label]));

const MAX_MB = 4;
const ACCEPT  = "image/jpeg,image/png,image/webp,application/pdf";

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return new Date(y, m - 1, d).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric",
  });
}

const blankForm = () => ({
  title: "",
  document_type: "other",
  received_date: "",
  notes: "",
  file: null,
});

export default function DocumentsPage() {
  const [docs, setDocs]         = useState([]);
  const [loading, setLoading]   = useState(true);
  const [open, setOpen]         = useState(false);
  const [form, setForm]         = useState(blankForm());
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);

  // ── Load ──────────────────────────────────────────────────────────────────
  const load = async () => {
    try {
      const { data } = await api.get("/documents");
      setDocs(data);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  // ── File handling ─────────────────────────────────────────────────────────
  const pickFile = (f) => {
    if (!f) return;
    if (f.size > MAX_MB * 1024 * 1024) {
      toast.error(`File too large. Maximum is ${MAX_MB} MB.`);
      return;
    }
    const ok = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
    if (!ok.includes(f.type)) {
      toast.error("Only JPEG, PNG, WEBP, or PDF files are supported.");
      return;
    }
    // Auto-fill title from filename if blank
    const name = f.name.replace(/\.[^.]+$/, "").replace(/[-_]/g, " ");
    setForm((prev) => ({
      ...prev,
      file: f,
      title: prev.title || name,
    }));
  };

  const onFileInput = (e) => pickFile(e.target.files?.[0]);

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    pickFile(e.dataTransfer.files?.[0]);
  };

  // ── Upload ────────────────────────────────────────────────────────────────
  const upload = async () => {
    if (!form.file) { toast.error("Please select a file."); return; }
    if (!form.title.trim()) { toast.error("Title is required."); return; }

    setUploading(true);
    const fd = new FormData();
    fd.append("file", form.file);
    fd.append("title", form.title.trim());
    fd.append("document_type", form.document_type);
    fd.append("received_date", form.received_date);
    fd.append("notes", form.notes.trim());

    try {
      const token = getToken();
      const res = await fetch(`${API}/documents/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      toast.success("Document uploaded");
      setOpen(false);
      setForm(blankForm());
      await load();
    } catch (e) {
      toast.error(e.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  // ── View file ────────────────────────────────────────────────────────────
  const viewFile = async (doc) => {
    try {
      const token = getToken();
      const res = await fetch(`${API}/documents/${doc.id}/file`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 120_000);
    } catch {
      toast.error("Could not open document.");
    }
  };

  // ── Delete ────────────────────────────────────────────────────────────────
  const remove = async (id) => {
    try {
      await api.delete(`/documents/${id}`);
      toast.success("Document deleted");
      await load();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────
  const isImage = (ct) => ct?.startsWith("image/");

  return (
    <div className="space-y-6" data-testid="documents-page">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="kbd-label">IDES Paperwork</div>
          <h1 className="font-display font-black text-4xl tracking-tighter mt-1">
            My Documents
          </h1>
          <p className="text-sm text-zinc-600 mt-2 max-w-2xl">
            Upload photos or scans of IDES letters, forms, and correspondence.
            Supported formats: JPEG, PNG, WEBP, PDF — max {MAX_MB} MB each.
          </p>
        </div>
        <Button
          className="rounded-none bg-[#0033A0] hover:bg-[#002266]"
          onClick={() => { setForm(blankForm()); setOpen(true); }}
          data-testid="upload-doc-button"
        >
          <PlusIcon size={16} weight="bold" className="mr-2" /> Upload Document
        </Button>
      </div>

      {/* ── Document grid ── */}
      {loading ? (
        <div className="text-sm text-zinc-500 py-12 text-center">Loading…</div>
      ) : docs.length === 0 ? (
        <div className="border border-dashed border-zinc-300 bg-zinc-50 py-16 text-center">
          <FileTextIcon size={40} weight="thin" className="mx-auto text-zinc-300 mb-3" />
          <p className="text-sm text-zinc-500">No documents yet.</p>
          <p className="text-xs text-zinc-400 mt-1">
            Upload a photo or scan of IDES paperwork to get started.
          </p>
          <Button
            className="mt-4 rounded-none bg-[#0033A0] hover:bg-[#002266]"
            onClick={() => { setForm(blankForm()); setOpen(true); }}
          >
            <UploadSimpleIcon size={14} weight="bold" className="mr-2" />
            Upload First Document
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {docs.map((doc) => (
            <div
              key={doc.id}
              className="border border-zinc-200 bg-white hover:border-zinc-400 transition-colors"
              data-testid={`doc-card-${doc.id}`}
            >
              {/* Icon / preview placeholder */}
              <div className="bg-zinc-50 border-b border-zinc-200 h-28 flex items-center justify-center">
                {isImage(doc.content_type) ? (
                  <ImageIcon size={36} weight="thin" className="text-zinc-300" />
                ) : (
                  <FileIcon size={36} weight="thin" className="text-zinc-300" />
                )}
              </div>

              <div className="p-3 space-y-2">
                {/* Type badge */}
                <div className="kbd-label text-[10px]">
                  {docTypeLabel[doc.document_type] || doc.document_type}
                </div>

                {/* Title */}
                <div className="font-semibold text-sm text-zinc-900 leading-tight line-clamp-2">
                  {doc.title}
                </div>

                {/* Meta */}
                <div className="text-xs text-zinc-400 space-y-0.5">
                  {doc.received_date && (
                    <div>Received: {formatDate(doc.received_date)}</div>
                  )}
                  <div>
                    Uploaded: {formatDate(doc.created_at?.slice(0, 10))} · {formatBytes(doc.file_size)}
                  </div>
                </div>

                {doc.notes && (
                  <p className="text-xs text-zinc-500 line-clamp-2 border-t border-zinc-100 pt-2">
                    {doc.notes}
                  </p>
                )}

                {/* Actions */}
                <div className="flex items-center gap-2 pt-1">
                  <Button
                    size="sm"
                    variant="outline"
                    className="rounded-none border-zinc-300 flex-1 text-xs"
                    onClick={() => viewFile(doc)}
                  >
                    <ArrowSquareOutIcon size={12} weight="bold" className="mr-1.5" />
                    Open
                  </Button>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button
                        size="sm"
                        variant="outline"
                        className="rounded-none border-zinc-300 text-red-600 hover:border-red-300"
                        data-testid={`delete-doc-${doc.id}`}
                      >
                        <TrashIcon size={12} weight="bold" />
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent className="rounded-none">
                      <AlertDialogHeader>
                        <AlertDialogTitle>Delete document?</AlertDialogTitle>
                        <AlertDialogDescription>
                          "{doc.title}" will be permanently deleted. This cannot be undone.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel className="rounded-none">Cancel</AlertDialogCancel>
                        <AlertDialogAction
                          className="rounded-none bg-red-600 hover:bg-red-700"
                          onClick={() => remove(doc.id)}
                        >
                          Delete
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Upload dialog ── */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="rounded-none max-w-lg" data-testid="upload-dialog">
          <DialogHeader>
            <DialogTitle className="font-display tracking-tight">
              Upload IDES Document
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {/* Drop zone */}
            <div
              role="button"
              tabIndex={0}
              className={`border-2 border-dashed rounded-none p-6 text-center cursor-pointer transition-colors
                ${dragOver ? "border-[#0033A0] bg-blue-50" : "border-zinc-300 hover:border-zinc-400"}`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => fileRef.current?.click()}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  fileRef.current?.click();
                }
              }}
              data-testid="drop-zone"
            >
              <UploadSimpleIcon size={28} weight="thin" className="mx-auto text-zinc-400 mb-2" />
              {form.file ? (
                <div>
                  <div className="text-sm font-semibold text-zinc-800">{form.file.name}</div>
                  <div className="text-xs text-zinc-400 mt-1">{formatBytes(form.file.size)}</div>
                </div>
              ) : (
                <div>
                  <div className="text-sm text-zinc-600">
                    Drag & drop or <span className="text-[#0033A0] font-semibold">browse</span>
                  </div>
                  <div className="text-xs text-zinc-400 mt-1">
                    JPEG · PNG · WEBP · PDF — max {MAX_MB} MB
                  </div>
                </div>
              )}
              <input
                ref={fileRef}
                type="file"
                accept={ACCEPT}
                className="hidden"
                onChange={onFileInput}
                data-testid="file-input"
              />
            </div>

            {/* Title */}
            <div>
              <Label className="kbd-label">Title <span className="text-red-500">*</span></Label>
              <Input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="e.g. Determination Letter June 2026"
                className="rounded-none mt-2"
                data-testid="doc-title-input"
              />
            </div>

            {/* Document type */}
            <div>
              <Label className="kbd-label">Document Type</Label>
              <select
                value={form.document_type}
                onChange={(e) => setForm({ ...form, document_type: e.target.value })}
                className="w-full mt-2 border border-zinc-300 rounded-none px-3 py-2 text-sm focus:outline-none focus:border-[#0033A0]"
                data-testid="doc-type-select"
              >
                {DOC_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>

            {/* Received date */}
            <div>
              <Label className="kbd-label">
                Date Received <span className="text-zinc-400 normal-case font-normal">(optional)</span>
              </Label>
              <Input
                type="date"
                value={form.received_date}
                onChange={(e) => setForm({ ...form, received_date: e.target.value })}
                className="rounded-none mt-2"
                data-testid="doc-date-input"
              />
            </div>

            {/* Notes */}
            <div>
              <Label className="kbd-label">
                Notes <span className="text-zinc-400 normal-case font-normal">(optional)</span>
              </Label>
              <Input
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                placeholder="What is this document about?"
                className="rounded-none mt-2"
                data-testid="doc-notes-input"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" className="rounded-none" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              className="rounded-none bg-[#0033A0] hover:bg-[#002266]"
              onClick={upload}
              disabled={uploading || !form.file}
              data-testid="doc-upload-submit"
            >
              {uploading ? "Uploading…" : "Upload"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}