import { useEffect, useState } from "react";
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
});

export default function WeekDetail() {
  const { id } = useParams();
  const [week, setWeek] = useState(null);
  const [contacts, setContacts] = useState([]);
  const [pageLoading, setPageLoading] = useState(true);
  const [pageError, setPageError] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(blank(id));

  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [downloadingCsv, setDownloadingCsv] = useState(false);

  const load = async () => {
    setPageError("");
    try {
      const [w, c] = await Promise.all([
        api.get(`/benefit-weeks/${id}`),
        api.get(`/contacts?week_id=${id}`),
      ]);
      setWeek(w.data);
      setContacts(c.data);
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

  const openNew = () => {
    setEditing(null);
    setForm(blank(id));
    setOpen(true);
  };
  const openEdit = (c) => {
    setEditing(c);
    setForm({ ...c });
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
      // Open the PDF inline in a new tab so the browser's PDF viewer loads it.
      // Revoke the object URL after 2 minutes — enough time for the tab to finish loading.
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 120_000);
      toast.success("Report opened in new tab", { id: toastId });
    } catch {
      toast.error("Failed to generate report. Please try again.", {
        id: toastId,
      });
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

  // ---------- Page-level loading state ----------
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

  // ---------- Page-level error state ----------
  if (pageError || !week) {
    return (
      <div className="space-y-6" data-testid="week-detail-page">
        <div className="border border-destructive/30 bg-destructive/10 p-8 text-center">
          <WarningIcon
            size={28}
            weight="fill"
            className="text-[#DC2626] mx-auto mb-3"
          />
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
              onClick={() => {
                setPageLoading(true);
                load();
              }}
            >
              Try Again
            </Button>
            <Link to="/weeks">
              <Button
                variant="outline"
                className="rounded-none border-border"
              >
                Back to All Weeks
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const compliant = contacts.length >= 3;

  return (
    <div className="space-y-6" data-testid="week-detail-page">
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
                <CheckCircleIcon size={14} weight="fill" /> COMPLIANT (
                {contacts.length}/3)
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-xs font-bold text-[#DC2626]">
                <WarningIcon size={14} weight="fill" /> {3 - contacts.length}{" "}
                MORE CONTACT{3 - contacts.length === 1 ? "" : "S"} NEEDED
              </span>
            )}
            {week.certified && (
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-muted-foreground">
                CERTIFIED WITH IDES
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="rounded-none border-border min-w-[110px]"
            onClick={downloadCsv}
            disabled={downloadingCsv}
            data-testid="download-csv-button"
          >
            {downloadingCsv ? (
              <>
                <CircleNotchIcon
                  size={16}
                  weight="bold"
                  className="mr-2 animate-spin"
                />
                Exporting...
              </>
            ) : (
              <>
                <DownloadSimpleIcon size={16} weight="bold" className="mr-2" />{" "}
                CSV
              </>
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
                <>
                  <CircleNotchIcon
                    size={16}
                    weight="bold"
                    className="mr-2 animate-spin"
                  />
                  Generating Report...
                </>
              ) : (
                <>
                  <FilePdfIcon size={16} weight="bold" className="mr-2" />{" "}
                  Download Report (PDF)
                </>
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
                <PlusIcon size={16} weight="bold" className="mr-2" /> Work
                Search Contact
              </Button>
            </DialogTrigger>
            <DialogContent
              className="rounded-none max-w-2xl"
              data-testid="contact-dialog"
            >
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
                    onChange={(e) =>
                      setForm({ ...form, contact_date: e.target.value })
                    }
                    className="rounded-none mt-2"
                    data-testid="contact-date-input"
                  />
                </div>
                <div className="col-span-6">
                  <Label className="kbd-label">Contact Method</Label>
                  <Select
                    value={form.contact_method}
                    onValueChange={(v) =>
                      setForm({ ...form, contact_method: v })
                    }
                  >
                    <SelectTrigger
                      className="rounded-none mt-2"
                      data-testid="contact-method-select"
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {METHODS.map((m) => (
                        <SelectItem key={m} value={m}>
                          {m}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="col-span-12">
                  <Label className="kbd-label">Employer Name</Label>
                  <Input
                    value={form.employer_name}
                    onChange={(e) =>
                      setForm({ ...form, employer_name: e.target.value })
                    }
                    className="rounded-none mt-2"
                    data-testid="contact-employer-input"
                  />
                </div>
                <div className="col-span-12">
                  <Label className="kbd-label">Employer Address</Label>
                  <Input
                    value={form.employer_address}
                    onChange={(e) =>
                      setForm({ ...form, employer_address: e.target.value })
                    }
                    className="rounded-none mt-2"
                    data-testid="contact-address-input"
                  />
                </div>
                <div className="col-span-6">
                  <Label className="kbd-label">Position Applied For</Label>
                  <Input
                    value={form.position_applied}
                    onChange={(e) =>
                      setForm({ ...form, position_applied: e.target.value })
                    }
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
                    <SelectTrigger
                      className="rounded-none mt-2"
                      data-testid="contact-type-select"
                    >
                      <SelectValue placeholder="Select type..." />
                    </SelectTrigger>
                    <SelectContent>
                      {TYPE_OF_WORK_OPTIONS.map((t) => (
                        <SelectItem key={t} value={t}>
                          {t}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="col-span-6">
                  <Label className="kbd-label">Person Contacted</Label>
                  <Input
                    value={form.person_contacted}
                    onChange={(e) =>
                      setForm({ ...form, person_contacted: e.target.value })
                    }
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
                    <SelectTrigger
                      className="rounded-none mt-2"
                      data-testid="contact-result-select"
                    >
                      <SelectValue placeholder="Select result..." />
                    </SelectTrigger>
                    <SelectContent>
                      {RESULT_OPTIONS.map((r) => (
                        <SelectItem key={r} value={r}>
                          {r}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="col-span-12">
                  <Label className="kbd-label">Source URL</Label>
                  <Input
                    value={form.source_url}
                    onChange={(e) =>
                      setForm({ ...form, source_url: e.target.value })
                    }
                    className="rounded-none mt-2"
                    placeholder="https://..."
                    data-testid="contact-url-input"
                  />
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
                    <>
                      <CircleNotchIcon
                        size={16}
                        weight="bold"
                        className="mr-2 animate-spin"
                      />
                      Saving...
                    </>
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
            {contacts.length === 0 && (
              <tr>
                <td colSpan={7} className="py-16">
                  <div className="flex flex-col items-center justify-center text-center gap-3">
                    <ClipboardTextIcon
                      size={32}
                      weight="light"
                      className="text-muted-foreground"
                    />
                    <div>
                      <p className="text-sm font-semibold text-muted-foreground">
                        No contacts logged yet
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Illinois requires at least 3 work-search contacts for
                        this benefit week.
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
            {contacts.map((c, i) => (
              <tr
                key={c.id}
                className="border-b border-border"
                data-testid={`contact-row-${c.id}`}
              >
                <td className="font-mono-data text-muted-foreground">{i + 1}</td>
                <td className="font-mono-data">{c.contact_date}</td>
                <td>
                  <div className="font-semibold">{c.employer_name}</div>
                  <div className="text-xs text-muted-foreground">
                    {c.employer_address}
                  </div>
                </td>
                <td>
                  <span className="text-xs font-semibold uppercase tracking-wider border border-border px-2 py-0.5">
                    {c.contact_method}
                  </span>
                </td>
                <td>
                  <div>{c.position_applied || "—"}</div>
                  {c.type_of_work && (
                    <div className="text-xs text-muted-foreground">
                      {c.type_of_work}
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
                            <CircleNotchIcon
                              size={14}
                              weight="bold"
                              className="animate-spin"
                            />
                          ) : (
                            <TrashIcon size={14} weight="bold" />
                          )}
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent className="rounded-none">
                        <AlertDialogHeader>
                          <AlertDialogTitle>Delete contact?</AlertDialogTitle>
                          <AlertDialogDescription>
                            This action cannot be undone.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel className="rounded-none">
                            Cancel
                          </AlertDialogCancel>
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
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}