import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, formatApiError, API } from "@/lib/api";
import { Button } from "@/components/ui/button";
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
} from "@phosphor-icons/react";
import { toast } from "sonner";

const METHODS = ["In Person", "Phone", "Email", "Online", "Mail", "Other"];

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
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(blank(id));

  const load = async () => {
    try {
      const [w, c] = await Promise.all([
        api.get(`/benefit-weeks/${id}`),
        api.get(`/contacts?week_id=${id}`),
      ]);
      setWeek(w.data);
      setContacts(c.data);
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    load(); /* eslint-disable-next-line */
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
    try {
      if (editing) {
        await api.put(`/contacts/${editing.id}`, form);
        toast.success("Contact updated");
      } else {
        await api.post("/contacts", form);
        toast.success("Contact added");
      }
      setOpen(false);
      await load();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  const remove = async (cid) => {
    try {
      await api.delete(`/contacts/${cid}`);
      toast.success("Deleted");
      await load();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  const downloadPdf = async () => {
    try {
      const token = localStorage.getItem("ides_token");
      const res = await fetch(`${API}/reports/benefit-week/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `BenefitWeek_${week.week_start}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("PDF downloaded");
    } catch (e) {
      toast.error("Failed to generate PDF");
    }
  };

  const downloadCsv = async () => {
    try {
      const token = localStorage.getItem("ides_token");
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
      toast.success("CSV downloaded");
    } catch (e) {
      toast.error("Failed to export CSV");
    }
  };

  if (!week) return <div className="kbd-label">Loading...</div>;

  const compliant = contacts.length >= 3;

  return (
    <div className="space-y-6" data-testid="week-detail-page">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <Link
            to="/weeks"
            className="kbd-label text-zinc-500 hover:text-zinc-900 inline-flex items-center gap-1"
          >
            <ArrowLeftIcon size={12} weight="bold" /> All Weeks
          </Link>
          <h1 className="font-display font-black text-3xl sm:text-4xl tracking-tighter mt-2 font-mono-data">
            {week.week_start} <span className="text-zinc-400">→</span>{" "}
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
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-zinc-600">
                CERTIFIED WITH IDES
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="rounded-none border-zinc-300"
            onClick={downloadCsv}
            data-testid="download-csv-button"
          >
            <DownloadSimpleIcon size={16} weight="bold" className="mr-2" /> CSV
          </Button>
          <Button
            variant="outline"
            className="rounded-none border-zinc-300"
            onClick={downloadPdf}
            data-testid="download-pdf-button"
          >
            <FilePdfIcon size={16} weight="bold" className="mr-2" /> Download
            Report (PDF)
          </Button>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button
                className="rounded-none bg-[#0033A0] hover:bg-[#002266]"
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
                  <Input
                    value={form.type_of_work}
                    onChange={(e) =>
                      setForm({ ...form, type_of_work: e.target.value })
                    }
                    className="rounded-none mt-2"
                    data-testid="contact-type-input"
                  />
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
                  <Input
                    value={form.result}
                    onChange={(e) =>
                      setForm({ ...form, result: e.target.value })
                    }
                    className="rounded-none mt-2"
                    placeholder="e.g. Applied, Interview, No response"
                    data-testid="contact-result-input"
                  />
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
                >
                  Cancel
                </Button>
                <Button
                  className="rounded-none bg-[#0033A0] hover:bg-[#002266]"
                  onClick={save}
                  data-testid="contact-save-button"
                >
                  Save Contact
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {week.notes && (
        <div className="border-l-4 border-zinc-300 pl-4 text-sm text-zinc-700">
          <div className="kbd-label">Notes</div>
          <div className="mt-1">{week.notes}</div>
        </div>
      )}

      <div className="border border-zinc-200 bg-white overflow-x-auto">
        <table className="w-full compliance-table text-sm">
          <thead className="bg-[#0033A0] text-white">
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
                <td colSpan={7} className="text-center text-zinc-500 py-12">
                  No contacts yet — log your first work-search contact.
                </td>
              </tr>
            )}
            {contacts.map((c, i) => (
              <tr
                key={c.id}
                className="border-b border-zinc-100"
                data-testid={`contact-row-${c.id}`}
              >
                <td className="font-mono-data text-zinc-500">{i + 1}</td>
                <td className="font-mono-data">{c.contact_date}</td>
                <td>
                  <div className="font-semibold">{c.employer_name}</div>
                  <div className="text-xs text-zinc-500">
                    {c.employer_address}
                  </div>
                </td>
                <td>
                  <span className="text-xs font-semibold uppercase tracking-wider border border-zinc-300 px-2 py-0.5">
                    {c.contact_method}
                  </span>
                </td>
                <td>
                  <div>{c.position_applied || "—"}</div>
                  {c.type_of_work && (
                    <div className="text-xs text-zinc-500">
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
                      className="rounded-none border-zinc-300"
                      onClick={() => openEdit(c)}
                      data-testid={`edit-contact-${c.id}`}
                    >
                      <PencilSimpleIcon size={14} weight="bold" />
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          size="sm"
                          variant="outline"
                          className="rounded-none border-zinc-300 hover:bg-red-50 hover:text-[#DC2626]"
                          data-testid={`delete-contact-${c.id}`}
                        >
                          <TrashIcon size={14} weight="bold" />
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
                            className="rounded-none bg-[#DC2626] hover:bg-red-700"
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
