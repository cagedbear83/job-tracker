import { useEffect, useState, useMemo, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { api, formatApiError, API, getValidToken } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { FeatureGate } from "@/components/FeatureGate";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  PlusIcon,
  TrashIcon,
  PencilSimpleIcon,
  FilePdfIcon,
  ArrowLeftIcon,
  CheckCircleIcon,
  WarningIcon,
  DownloadSimpleIcon,
  CircleNotchIcon,
  ClipboardTextIcon,
  FunnelIcon,
  XIcon,
  BookmarkSimpleIcon,
  TagIcon,
  CaretDownIcon,
} from "@phosphor-icons/react";
import { toast } from "sonner";

const METHODS = ["In Person", "Phone", "Email", "Online", "Mail", "Other"];

const TYPE_OF_WORK_OPTIONS = [
  "Full-time",
  "Part-time",
  "Independent Contractor",
  "Temporary/Seasonal",
  "Contract-to-hire",
];

const RESULT_OPTIONS = [
  "Applied",
  "Awaiting Outcome",
  "Interview Scheduled",
  "Interviewing",
  "Hired",
  "Networking",
  "Not Hired",
  "Not Hiring/Did not Apply",
];

const EMPTY_FILTERS = {
  result: "",
  method: "",
  type_of_work: "",
  tags: [],    // array of tag IDs
  date_mode: "none",  // "none" | "single" | "range"
  date_single: "",
  date_from: "",
  date_to: "",
};

const blank = (wid) => ({
  benefit_week_id: wid,
  contact_date: new Date().toISOString().slice(0, 10),
  employer_name: "",
  employer_address: "",
  contact_method: "Online",
  type_of_work: "",
  position_applied: "",
  person_contacted: "",
  result: "Applied",
  source_url: "",
  tags: [],
});

// ── Inline tag chip ────────────────────────────────────────────────────────────
function TagChip({ name, onRemove, small = false }) {
  return (
    <span
      className={`inline-flex items-center gap-1 border border-border bg-secondary text-foreground font-semibold ${
        small ? "text-[10px] px-1.5 py-0.5" : "text-xs px-2 py-1"
      }`}
    >
      {name}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="text-muted-foreground hover:text-foreground ml-0.5"
          aria-label={`Remove tag ${name}`}
        >
          <XIcon size={10} weight="bold" />
        </button>
      )}
    </span>
  );
}

// ── Tag input with autocomplete ────────────────────────────────────────────────
function TagInput({ selectedTagIds, allTags, onChange, onCreateTag }) {
  const [input, setInput] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);

  const selectedTags = allTags.filter((t) => selectedTagIds.includes(t.id));
  const filtered = allTags.filter(
    (t) =>
      !selectedTagIds.includes(t.id) &&
      t.name.toLowerCase().includes(input.toLowerCase())
  );
  const exactMatch = allTags.find(
    (t) => t.name.toLowerCase() === input.trim().toLowerCase()
  );

  const addTag = (tag) => {
    onChange([...selectedTagIds, tag.id]);
    setInput("");
    setShowSuggestions(false);
  };

  const handleKeyDown = async (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const name = input.trim();
      if (!name) return;
      if (exactMatch) {
        addTag(exactMatch);
      } else {
        const newTag = await onCreateTag(name);
        if (newTag) addTag(newTag);
      }
    }
    if (e.key === "Escape") setShowSuggestions(false);
  };

  const removeTag = (tagId) => {
    onChange(selectedTagIds.filter((id) => id !== tagId));
  };

  return (
    <div className="space-y-2">
      {selectedTags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {selectedTags.map((t) => (
            <TagChip key={t.id} name={t.name} onRemove={() => removeTag(t.id)} />
          ))}
        </div>
      )}
      <div className="relative">
        <div className="flex items-center border border-border focus-within:border-primary">
          <TagIcon size={14} weight="bold" className="ml-2 text-muted-foreground shrink-0" />
          <input
            className="flex-1 px-2 py-2 text-sm bg-transparent outline-none placeholder:text-muted-foreground"
            placeholder="Type to search or create a tag, then press Enter…"
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              setShowSuggestions(true);
            }}
            onFocus={() => setShowSuggestions(true)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
            onKeyDown={handleKeyDown}
          />
        </div>
        {showSuggestions && (input || filtered.length > 0) && (
          <div className="absolute z-50 top-full left-0 right-0 bg-background border border-border shadow-md max-h-40 overflow-y-auto">
            {filtered.map((t) => (
              <button
                key={t.id}
                type="button"
                className="w-full text-left px-3 py-2 text-sm hover:bg-secondary flex items-center gap-2"
                onMouseDown={() => addTag(t)}
              >
                <TagIcon size={12} className="text-muted-foreground" />
                {t.name}
              </button>
            ))}
            {input.trim() && !exactMatch && (
              <button
                type="button"
                className="w-full text-left px-3 py-2 text-sm hover:bg-secondary text-primary flex items-center gap-2"
                onMouseDown={async () => {
                  const newTag = await onCreateTag(input.trim());
                  if (newTag) addTag(newTag);
                }}
              >
                <PlusIcon size={12} weight="bold" />
                Create &quot;{input.trim()}&quot;
              </button>
            )}
            {!input.trim() && filtered.length === 0 && allTags.length === 0 && (
              <div className="px-3 py-2 text-xs text-muted-foreground">
                Type a tag name and press Enter to create your first tag
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Facet option row ───────────────────────────────────────────────────────────
function FacetOption({ label, count, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full flex items-center justify-between px-2 py-1.5 text-xs rounded text-left hover:bg-secondary transition-colors ${
        active ? "bg-secondary font-semibold text-foreground" : "text-muted-foreground"
      }`}
    >
      <span>{label}</span>
      <span className="text-[10px] tabular-nums bg-border px-1.5 py-0.5 rounded font-mono">
        {count}
      </span>
    </button>
  );
}

// ── Count helper ───────────────────────────────────────────────────────────────
function countField(contacts, field) {
  const acc = {};
  for (const c of contacts) {
    const v = c[field];
    if (v) acc[v] = (acc[v] || 0) + 1;
  }
  return acc;
}

function countTagsUsage(contacts) {
  const acc = {};
  for (const c of contacts) {
    for (const tagId of c.tags || []) {
      acc[tagId] = (acc[tagId] || 0) + 1;
    }
  }
  return acc;
}

// ─────────────────────────────────────────────────────────────────────────────
export default function WeekDetail() {
  const { id } = useParams();
  const [week, setWeek] = useState(null);
  const [contacts, setContacts] = useState([]);
  const [allTags, setAllTags] = useState([]);
  const [savedViews, setSavedViews] = useState([]);
  const [pageLoading, setPageLoading] = useState(true);
  const [pageError, setPageError] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(blank(id));
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [downloadingCsv, setDownloadingCsv] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [saveViewName, setSaveViewName] = useState("");
  const [savingView, setSavingView] = useState(false);

  const load = async () => {
    setPageError("");
    try {
      const [w, c, t, v] = await Promise.all([
        api.get(`/benefit-weeks/${id}`),
        api.get(`/contacts?week_id=${id}`),
        api.get("/tags"),
        api.get("/saved-views"),
      ]);
      setWeek(w.data);
      setContacts(c.data);
      setAllTags(t.data);
      setSavedViews(v.data);
    } catch (e) {
      setPageError(formatApiError(e));
      toast.error(formatApiError(e));
    } finally {
      setPageLoading(false);
    }
  };

  useEffect(() => {
    setPageLoading(true);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // ── Tag management ──────────────────────────────────────────────────────────
  const createTag = useCallback(async (name) => {
    try {
      const { data } = await api.post("/tags", { name });
      setAllTags((prev) => {
        if (prev.find((t) => t.id === data.id)) return prev;
        return [...prev, data].sort((a, b) => a.name.localeCompare(b.name));
      });
      return data;
    } catch (e) {
      toast.error(formatApiError(e));
      return null;
    }
  }, []);

  // ── Facet counts (computed from full contact list, not filtered) ────────────
  const facets = useMemo(() => {
    const resultCounts = countField(contacts, "result");
    const methodCounts = countField(contacts, "contact_method");
    const towCounts = countField(contacts, "type_of_work");
    const tagCounts = countTagsUsage(contacts);
    return { result: resultCounts, method: methodCounts, type_of_work: towCounts, tags: tagCounts };
  }, [contacts]);

  // ── Filtered contacts ───────────────────────────────────────────────────────
  const displayedContacts = useMemo(() => {
    return contacts.filter((c) => {
      if (filters.result && c.result !== filters.result) return false;
      if (filters.method && c.contact_method !== filters.method) return false;
      if (filters.type_of_work && c.type_of_work !== filters.type_of_work) return false;
      if (filters.tags.length > 0 && !filters.tags.every((tid) => (c.tags || []).includes(tid))) return false;
      if (filters.date_mode === "single" && filters.date_single) {
        if (c.contact_date !== filters.date_single) return false;
      }
      if (filters.date_mode === "range") {
        if (filters.date_from && c.contact_date < filters.date_from) return false;
        if (filters.date_to && c.contact_date > filters.date_to) return false;
      }
      return true;
    });
  }, [contacts, filters]);

  const activeFilterCount = [
    filters.result,
    filters.method,
    filters.type_of_work,
    filters.tags.length > 0 ? "tags" : "",
    filters.date_mode !== "none" ? "date" : "",
  ].filter(Boolean).length;

  const clearFilters = () => setFilters(EMPTY_FILTERS);

  const loadView = (view) => {
    setFilters({ ...EMPTY_FILTERS, ...view.filters });
    setFilterOpen(false);
  };

  const saveView = async () => {
    if (!saveViewName.trim()) return;
    setSavingView(true);
    try {
      const { data } = await api.post("/saved-views", {
        name: saveViewName.trim(),
        filters: {
          result: filters.result,
          method: filters.method,
          type_of_work: filters.type_of_work,
          tags: filters.tags,
          date_mode: filters.date_mode,
          date_single: filters.date_single,
          date_from: filters.date_from,
          date_to: filters.date_to,
        },
      });
      setSavedViews((prev) => [...prev, data].sort((a, b) => a.name.localeCompare(b.name)));
      setSaveViewName("");
      toast.success(`View "${data.name}" saved`);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setSavingView(false);
    }
  };

  const deleteView = async (viewId, viewName) => {
    try {
      await api.delete(`/saved-views/${viewId}`);
      setSavedViews((prev) => prev.filter((v) => v.id !== viewId));
      toast.success(`View "${viewName}" deleted`);
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  // ── Dialog helpers ──────────────────────────────────────────────────────────
  const openNew = () => {
    setEditing(null);
    setForm(blank(id));
    setOpen(true);
  };
  const openEdit = (c) => {
    setEditing(c);
    setForm({ ...c, tags: c.tags || [] });
    setOpen(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      if (editing) {
        const { data: updated } = await api.put(`/contacts/${editing.id}`, form);
        if (updated.benefit_week_id !== editing.benefit_week_id) {
          toast.success("Contact moved — the date falls in a different benefit week, so it's been reassigned there.");
        } else {
          toast.success("Contact updated");
        }
      } else {
        await api.post("/contacts", form);
        toast.success("Contact added");
      }
      setOpen(false);
      await load();
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (cid) => {
    setDeletingId(cid);
    try {
      await api.delete(`/contacts/${cid}`);
      toast.success("Contact deleted");
      await load();
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setDeletingId(null);
    }
  };

  const downloadPdf = async () => {
    setDownloadingPdf(true);
    const toastId = toast.loading("Generating report...");
    try {
      const token = await getValidToken();
      const res = await fetch(`${API}/reports/benefit-week/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 120_000);
      toast.success("Report opened in new tab", { id: toastId });
    } catch {
      toast.error("Failed to generate report. Please try again.", { id: toastId });
    } finally {
      setDownloadingPdf(false);
    }
  };

  const downloadCsv = async () => {
    setDownloadingCsv(true);
    const toastId = toast.loading("Preparing CSV export...");
    try {
      const token = await getValidToken();
      const res = await fetch(`${API}/contacts/export.csv?week_id=${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Contacts_${week.week_start}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("CSV downloaded", { id: toastId });
    } catch {
      toast.error("Failed to export CSV. Please try again.", { id: toastId });
    } finally {
      setDownloadingCsv(false);
    }
  };

  // ── Loading / error states ─────────────────────────────────────────────────
  if (pageLoading) {
    return (
      <div className="space-y-6" data-testid="week-detail-page">
        <div className="flex items-center gap-3 text-muted-foreground py-24 justify-center">
          <CircleNotchIcon size={20} weight="bold" className="animate-spin" />
          <span className="kbd-label">Loading benefit week...</span>
        </div>
      </div>
    );
  }

  if (pageError || !week) {
    return (
      <div className="space-y-6" data-testid="week-detail-page">
        <div className="border border-destructive/30 bg-destructive/10 p-8 text-center">
          <WarningIcon size={28} weight="fill" className="text-[#DC2626] mx-auto mb-3" />
          <p className="text-sm text-destructive font-semibold mb-1">
            Couldn't load this benefit week
          </p>
          <p className="text-xs text-destructive mb-4">
            {pageError || "The week may not exist or you may not have access."}
          </p>
          <div className="flex gap-2 justify-center">
            <Button
              variant="outline"
              className="rounded-none border-destructive/30 text-destructive hover:bg-red-100"
              onClick={() => { setPageLoading(true); load(); }}
            >
              Try Again
            </Button>
            <Link to="/weeks">
              <Button variant="outline" className="rounded-none border-border">
                Back to All Weeks
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const compliant = contacts.length >= 3;
  const filterTagObjects = allTags.filter((t) => filters.tags.includes(t.id));

  return (
    <div className="space-y-6" data-testid="week-detail-page">
      {/* ── Page header ── */}
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <Link
            to="/weeks"
            className="kbd-label text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
          >
            <ArrowLeftIcon size={12} weight="bold" /> All Weeks
          </Link>
          <h1 className="font-display font-black text-3xl sm:text-4xl tracking-tighter mt-2 font-mono-data">
            {week.week_start} <span className="text-muted-foreground">→</span>{" "}
            {week.week_end}
          </h1>
          <div className="flex items-center gap-3 mt-2">
            {compliant ? (
              <span className="inline-flex items-center gap-1 text-xs font-bold text-[#16A34A]">
                <CheckCircleIcon size={14} weight="fill" /> COMPLIANT ({contacts.length}/3)
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-xs font-bold text-[#DC2626]">
                <WarningIcon size={14} weight="fill" /> {3 - contacts.length} MORE CONTACT
                {3 - contacts.length === 1 ? "" : "S"} NEEDED
              </span>
            )}
            {week.certified && (
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-muted-foreground">
                CERTIFIED WITH IDES
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button
            variant="outline"
            className="rounded-none border-border min-w-[110px]"
            onClick={downloadCsv}
            disabled={downloadingCsv}
            data-testid="download-csv-button"
          >
            {downloadingCsv ? (
              <><CircleNotchIcon size={16} weight="bold" className="mr-2 animate-spin" />Exporting...</>
            ) : (
              <><DownloadSimpleIcon size={16} weight="bold" className="mr-2" /> CSV</>
            )}
          </Button>
          <FeatureGate feature="pdf_exports_per_month" metered showUsage>
            <Button
              variant="outline"
              className="rounded-none border-border min-w-[190px]"
              onClick={downloadPdf}
              disabled={downloadingPdf}
              data-testid="download-pdf-button"
            >
              {downloadingPdf ? (
                <><CircleNotchIcon size={16} weight="bold" className="mr-2 animate-spin" />Generating Report...</>
              ) : (
                <><FilePdfIcon size={16} weight="bold" className="mr-2" /> Download Report (PDF)</>
              )}
            </Button>
          </FeatureGate>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button
                className="rounded-none bg-primary hover:bg-primary/90"
                onClick={openNew}
                data-testid="new-contact-button"
              >
                <PlusIcon size={16} weight="bold" className="mr-2" /> Work Search Contact
              </Button>
            </DialogTrigger>
            <DialogContent className="rounded-none max-w-2xl" data-testid="contact-dialog">
              <DialogHeader>
                <DialogTitle className="font-display tracking-tight">
                  {editing ? "Edit Contact" : "New Work Search Contact"}
                </DialogTitle>
              </DialogHeader>
              <div className="grid grid-cols-12 gap-3">
                <div className="col-span-6">
                  <Label className="kbd-label">Contact Date</Label>
                  <Input
                    type="date"
                    value={form.contact_date}
                    onChange={(e) => setForm({ ...form, contact_date: e.target.value })}
                    className="rounded-none mt-2"
                    data-testid="contact-date-input"
                  />
                </div>
                <div className="col-span-6">
                  <Label className="kbd-label">Contact Method</Label>
                  <Select
                    value={form.contact_method}
                    onValueChange={(v) => setForm({ ...form, contact_method: v })}
                  >
                    <SelectTrigger className="rounded-none mt-2" data-testid="contact-method-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {METHODS.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="col-span-12">
                  <Label className="kbd-label">Employer Name</Label>
                  <Input
                    value={form.employer_name}
                    onChange={(e) => setForm({ ...form, employer_name: e.target.value })}
                    className="rounded-none mt-2"
                    data-testid="contact-employer-input"
                  />
                </div>
                <div className="col-span-12">
                  <Label className="kbd-label">Employer Address</Label>
                  <Input
                    value={form.employer_address}
                    onChange={(e) => setForm({ ...form, employer_address: e.target.value })}
                    className="rounded-none mt-2"
                    data-testid="contact-address-input"
                  />
                </div>
                <div className="col-span-6">
                  <Label className="kbd-label">Position Applied For</Label>
                  <Input
                    value={form.position_applied}
                    onChange={(e) => setForm({ ...form, position_applied: e.target.value })}
                    className="rounded-none mt-2"
                    data-testid="contact-position-input"
                  />
                </div>
                <div className="col-span-6">
                  <Label className="kbd-label">Type of Work</Label>
                  <Select
                    value={form.type_of_work}
                    onValueChange={(v) => setForm({ ...form, type_of_work: v })}
                  >
                    <SelectTrigger className="rounded-none mt-2" data-testid="contact-type-select">
                      <SelectValue placeholder="Select type..." />
                    </SelectTrigger>
                    <SelectContent>
                      {TYPE_OF_WORK_OPTIONS.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="col-span-6">
                  <Label className="kbd-label">Person Contacted</Label>
                  <Input
                    value={form.person_contacted}
                    onChange={(e) => setForm({ ...form, person_contacted: e.target.value })}
                    className="rounded-none mt-2"
                    data-testid="contact-person-input"
                  />
                </div>
                <div className="col-span-6">
                  <Label className="kbd-label">Result</Label>
                  <Select
                    value={form.result}
                    onValueChange={(v) => setForm({ ...form, result: v })}
                  >
                    <SelectTrigger className="rounded-none mt-2" data-testid="contact-result-select">
                      <SelectValue placeholder="Select result..." />
                    </SelectTrigger>
                    <SelectContent>
                      {RESULT_OPTIONS.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="col-span-12">
                  <Label className="kbd-label">Source URL</Label>
                  <Input
                    value={form.source_url}
                    onChange={(e) => setForm({ ...form, source_url: e.target.value })}
                    className="rounded-none mt-2"
                    placeholder="https://..."
                    data-testid="contact-url-input"
                  />
                </div>
                {/* ── Tags ── */}
                <div className="col-span-12">
                  <Label className="kbd-label">Tags</Label>
                  <div className="mt-2">
                    <TagInput
                      selectedTagIds={form.tags || []}
                      allTags={allTags}
                      onChange={(tags) => setForm({ ...form, tags })}
                      onCreateTag={createTag}
                    />
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  className="rounded-none"
                  onClick={() => setOpen(false)}
                  disabled={saving}
                >
                  Cancel
                </Button>
                <Button
                  className="rounded-none bg-primary hover:bg-primary/90 min-w-[140px]"
                  onClick={save}
                  disabled={saving}
                  data-testid="contact-save-button"
                >
                  {saving ? (
                    <><CircleNotchIcon size={16} weight="bold" className="mr-2 animate-spin" />Saving...</>
                  ) : (
                    "Save Contact"
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {week.notes && (
        <div className="border-l-4 border-border pl-4 text-sm text-foreground">
          <div className="kbd-label">Notes</div>
          <div className="mt-1">{week.notes}</div>
        </div>
      )}

      {/* ── Filter bar ─────────────────────────────────────────────────────── */}
      <div className="flex items-start gap-2 flex-wrap">
        <Popover open={filterOpen} onOpenChange={setFilterOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              className={`rounded-none border-border gap-2 ${activeFilterCount > 0 ? "border-primary text-primary" : ""}`}
              data-testid="filter-button"
            >
              <FunnelIcon size={14} weight={activeFilterCount > 0 ? "fill" : "regular"} />
              Filter
              {activeFilterCount > 0 && (
                <span className="bg-primary text-primary-foreground text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                  {activeFilterCount}
                </span>
              )}
              <CaretDownIcon size={12} weight="bold" />
            </Button>
          </PopoverTrigger>
          <PopoverContent
            className="rounded-none p-0 w-80 max-h-[80vh] overflow-y-auto border border-border bg-background shadow-lg"
            align="start"
          >
            {/* ── Saved views ── */}
            {savedViews.length > 0 && (
              <div className="border-b border-border p-3">
                <div className="kbd-label mb-2">Saved Views</div>
                <div className="space-y-1">
                  {savedViews.map((v) => (
                    <div key={v.id} className="flex items-center gap-1">
                      <button
                        type="button"
                        className="flex-1 text-left text-xs px-2 py-1.5 hover:bg-secondary rounded text-foreground flex items-center gap-1.5"
                        onClick={() => loadView(v)}
                      >
                        <BookmarkSimpleIcon size={11} weight="fill" className="text-muted-foreground shrink-0" />
                        {v.name}
                      </button>
                      <button
                        type="button"
                        className="p-1 text-muted-foreground hover:text-destructive"
                        onClick={() => deleteView(v.id, v.name)}
                        aria-label="Delete view"
                      >
                        <XIcon size={11} weight="bold" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── Result ── */}
            <div className="border-b border-border p-3">
              <div className="kbd-label mb-2">Result</div>
              <div className="space-y-0.5">
                {RESULT_OPTIONS.filter((r) => (facets.result[r] || 0) > 0).map((r) => (
                  <FacetOption
                    key={r}
                    label={r}
                    count={facets.result[r] || 0}
                    active={filters.result === r}
                    onClick={() => setFilters((f) => ({ ...f, result: f.result === r ? "" : r }))}
                  />
                ))}
                {Object.keys(facets.result).length === 0 && (
                  <p className="text-xs text-muted-foreground px-2">No contacts yet</p>
                )}
              </div>
            </div>

            {/* ── Contact Method ── */}
            <div className="border-b border-border p-3">
              <div className="kbd-label mb-2">Contact Method</div>
              <div className="space-y-0.5">
                {METHODS.filter((m) => (facets.method[m] || 0) > 0).map((m) => (
                  <FacetOption
                    key={m}
                    label={m}
                    count={facets.method[m] || 0}
                    active={filters.method === m}
                    onClick={() => setFilters((f) => ({ ...f, method: f.method === m ? "" : m }))}
                  />
                ))}
              </div>
            </div>

            {/* ── Type of Work ── */}
            <div className="border-b border-border p-3">
              <div className="kbd-label mb-2">Type of Work</div>
              <div className="space-y-0.5">
                {TYPE_OF_WORK_OPTIONS.filter((t) => (facets.type_of_work[t] || 0) > 0).map((t) => (
                  <FacetOption
                    key={t}
                    label={t}
                    count={facets.type_of_work[t] || 0}
                    active={filters.type_of_work === t}
                    onClick={() => setFilters((f) => ({ ...f, type_of_work: f.type_of_work === t ? "" : t }))}
                  />
                ))}
                {Object.keys(facets.type_of_work).length === 0 && (
                  <p className="text-xs text-muted-foreground px-2">None logged</p>
                )}
              </div>
            </div>

            {/* ── Tags ── */}
            {allTags.length > 0 && (
              <div className="border-b border-border p-3">
                <div className="kbd-label mb-2">Tags</div>
                <div className="space-y-0.5">
                  {allTags
                    .filter((t) => (facets.tags[t.id] || 0) > 0)
                    .map((t) => (
                      <FacetOption
                        key={t.id}
                        label={t.name}
                        count={facets.tags[t.id] || 0}
                        active={filters.tags.includes(t.id)}
                        onClick={() =>
                          setFilters((f) => ({
                            ...f,
                            tags: f.tags.includes(t.id)
                              ? f.tags.filter((id) => id !== t.id)
                              : [...f.tags, t.id],
                          }))
                        }
                      />
                    ))}
                  {allTags.every((t) => (facets.tags[t.id] || 0) === 0) && (
                    <p className="text-xs text-muted-foreground px-2">No tagged contacts in this week</p>
                  )}
                </div>
              </div>
            )}

            {/* ── Date ── */}
            <div className="border-b border-border p-3">
              <div className="kbd-label mb-2">Date</div>
              <div className="space-y-2">
                <div className="flex gap-1">
                  {["none", "single", "range"].map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setFilters((f) => ({ ...f, date_mode: mode }))}
                      className={`flex-1 text-xs py-1 border transition-colors ${
                        filters.date_mode === mode
                          ? "border-primary bg-secondary font-semibold text-foreground"
                          : "border-border text-muted-foreground hover:bg-secondary"
                      }`}
                    >
                      {mode === "none" ? "Any" : mode === "single" ? "Date" : "Range"}
                    </button>
                  ))}
                </div>
                {filters.date_mode === "single" && (
                  <Input
                    type="date"
                    className="rounded-none text-xs h-8"
                    value={filters.date_single}
                    onChange={(e) => setFilters((f) => ({ ...f, date_single: e.target.value }))}
                  />
                )}
                {filters.date_mode === "range" && (
                  <div className="space-y-1">
                    <Input
                      type="date"
                      className="rounded-none text-xs h-8"
                      value={filters.date_from}
                      placeholder="From"
                      onChange={(e) => setFilters((f) => ({ ...f, date_from: e.target.value }))}
                    />
                    <Input
                      type="date"
                      className="rounded-none text-xs h-8"
                      value={filters.date_to}
                      placeholder="To"
                      onChange={(e) => setFilters((f) => ({ ...f, date_to: e.target.value }))}
                    />
                  </div>
                )}
              </div>
            </div>

            {/* ── Save view ── */}
            <div className="p-3">
              <div className="kbd-label mb-2">Save Current Filters</div>
              <div className="flex gap-1">
                <Input
                  className="rounded-none text-xs h-8 flex-1"
                  placeholder="View name…"
                  value={saveViewName}
                  onChange={(e) => setSaveViewName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && saveView()}
                />
                <Button
                  size="sm"
                  variant="outline"
                  className="rounded-none h-8 px-2"
                  onClick={saveView}
                  disabled={savingView || !saveViewName.trim() || activeFilterCount === 0}
                >
                  {savingView ? (
                    <CircleNotchIcon size={12} weight="bold" className="animate-spin" />
                  ) : (
                    <BookmarkSimpleIcon size={12} weight="bold" />
                  )}
                </Button>
              </div>
              {activeFilterCount === 0 && (
                <p className="text-[10px] text-muted-foreground mt-1">Set at least one filter to save a view</p>
              )}
            </div>

            {/* ── Footer actions ── */}
            {activeFilterCount > 0 && (
              <div className="border-t border-border p-2">
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full rounded-none text-xs text-muted-foreground"
                  onClick={() => { clearFilters(); setFilterOpen(false); }}
                >
                  Clear all filters
                </Button>
              </div>
            )}
          </PopoverContent>
        </Popover>

        {/* ── Active filter chips ── */}
        {filters.result && (
          <span className="inline-flex items-center gap-1 border border-primary/40 bg-primary/5 text-primary text-xs px-2 py-1 font-semibold">
            {filters.result}
            <button type="button" onClick={() => setFilters((f) => ({ ...f, result: "" }))} className="ml-0.5">
              <XIcon size={11} weight="bold" />
            </button>
          </span>
        )}
        {filters.method && (
          <span className="inline-flex items-center gap-1 border border-primary/40 bg-primary/5 text-primary text-xs px-2 py-1 font-semibold">
            {filters.method}
            <button type="button" onClick={() => setFilters((f) => ({ ...f, method: "" }))} className="ml-0.5">
              <XIcon size={11} weight="bold" />
            </button>
          </span>
        )}
        {filters.type_of_work && (
          <span className="inline-flex items-center gap-1 border border-primary/40 bg-primary/5 text-primary text-xs px-2 py-1 font-semibold">
            {filters.type_of_work}
            <button type="button" onClick={() => setFilters((f) => ({ ...f, type_of_work: "" }))} className="ml-0.5">
              <XIcon size={11} weight="bold" />
            </button>
          </span>
        )}
        {filterTagObjects.map((t) => (
          <span
            key={t.id}
            className="inline-flex items-center gap-1 border border-primary/40 bg-primary/5 text-primary text-xs px-2 py-1 font-semibold"
          >
            <TagIcon size={11} />
            {t.name}
            <button
              type="button"
              onClick={() => setFilters((f) => ({ ...f, tags: f.tags.filter((id) => id !== t.id) }))}
              className="ml-0.5"
            >
              <XIcon size={11} weight="bold" />
            </button>
          </span>
        ))}
        {filters.date_mode !== "none" && (
          <span className="inline-flex items-center gap-1 border border-primary/40 bg-primary/5 text-primary text-xs px-2 py-1 font-semibold">
            {filters.date_mode === "single" && filters.date_single
              ? filters.date_single
              : `${filters.date_from || "…"} → ${filters.date_to || "…"}`}
            <button
              type="button"
              onClick={() => setFilters((f) => ({ ...f, date_mode: "none", date_single: "", date_from: "", date_to: "" }))}
              className="ml-0.5"
            >
              <XIcon size={11} weight="bold" />
            </button>
          </span>
        )}

        {activeFilterCount > 0 && (
          <span className="text-xs text-muted-foreground self-center">
            {displayedContacts.length} of {contacts.length}
          </span>
        )}
      </div>

      {/* ── Contacts table ─────────────────────────────────────────────────── */}
      <div className="border border-border bg-background overflow-x-auto">
        <table className="w-full compliance-table text-sm">
          <thead className="bg-primary text-white">
            <tr className="text-left">
              <th className="kbd-label !text-white/70 w-10">#</th>
              <th className="kbd-label !text-white/70">Date</th>
              <th className="kbd-label !text-white/70">Employer & Address</th>
              <th className="kbd-label !text-white/70">Method</th>
              <th className="kbd-label !text-white/70">Position / Type</th>
              <th className="kbd-label !text-white/70">Result</th>
              <th className="kbd-label !text-white/70 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {displayedContacts.length === 0 && contacts.length === 0 && (
              <tr>
                <td colSpan={7} className="py-16">
                  <div className="flex flex-col items-center justify-center text-center gap-3">
                    <ClipboardTextIcon size={32} weight="light" className="text-muted-foreground" />
                    <div>
                      <p className="text-sm font-semibold text-muted-foreground">No contacts logged yet</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Illinois requires at least 3 work-search contacts for this benefit week.
                      </p>
                    </div>
                    <Button
                      size="sm"
                      className="rounded-none bg-primary hover:bg-primary/90 mt-1"
                      onClick={openNew}
                    >
                      <PlusIcon size={14} weight="bold" className="mr-2" />
                      Log Your First Contact
                    </Button>
                  </div>
                </td>
              </tr>
            )}
            {displayedContacts.length === 0 && contacts.length > 0 && (
              <tr>
                <td colSpan={7} className="py-10">
                  <div className="flex flex-col items-center gap-2 text-center">
                    <FunnelIcon size={24} weight="light" className="text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">No contacts match the active filters.</p>
                    <Button size="sm" variant="ghost" className="rounded-none text-xs" onClick={clearFilters}>
                      Clear filters
                    </Button>
                  </div>
                </td>
              </tr>
            )}
            {displayedContacts.map((c, i) => {
              const contactTags = allTags.filter((t) => (c.tags || []).includes(t.id));
              return (
                <tr key={c.id} className="border-b border-border" data-testid={`contact-row-${c.id}`}>
                  <td className="font-mono-data text-muted-foreground">{i + 1}</td>
                  <td className="font-mono-data">{c.contact_date}</td>
                  <td>
                    <div className="font-semibold">{c.employer_name}</div>
                    <div className="text-xs text-muted-foreground">{c.employer_address}</div>
                  </td>
                  <td>
                    <span className="text-xs font-semibold uppercase tracking-wider border border-border px-2 py-0.5">
                      {c.contact_method}
                    </span>
                  </td>
                  <td>
                    <div>{c.position_applied || "—"}</div>
                    {c.type_of_work && (
                      <div className="text-xs text-muted-foreground">{c.type_of_work}</div>
                    )}
                    {contactTags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {contactTags.map((t) => (
                          <TagChip key={t.id} name={t.name} small />
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="text-xs">{c.result}</td>
                  <td className="text-right">
                    <div className="inline-flex gap-1">
                      <Button
                        size="sm"
                        variant="outline"
                        className="rounded-none border-border"
                        onClick={() => openEdit(c)}
                        disabled={deletingId === c.id}
                        data-testid={`edit-contact-${c.id}`}
                      >
                        <PencilSimpleIcon size={14} weight="bold" />
                      </Button>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            size="sm"
                            variant="outline"
                            className="rounded-none border-border hover:bg-destructive/10 hover:text-[#DC2626]"
                            disabled={deletingId === c.id}
                            data-testid={`delete-contact-${c.id}`}
                          >
                            {deletingId === c.id ? (
                              <CircleNotchIcon size={14} weight="bold" className="animate-spin" />
                            ) : (
                              <TrashIcon size={14} weight="bold" />
                            )}
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent className="rounded-none">
                          <AlertDialogHeader>
                            <AlertDialogTitle>Delete contact?</AlertDialogTitle>
                            <AlertDialogDescription>This action cannot be undone.</AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel className="rounded-none">Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              className="rounded-none bg-[#DC2626] hover:bg-destructive/90"
                              onClick={() => remove(c.id)}
                              data-testid={`confirm-delete-contact-${c.id}`}
                            >
                              Delete
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
