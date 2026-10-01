import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/queryKeys";
import { Link } from "react-router-dom";
import { api, API, getValidToken } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
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
  PlusIcon,
  TrashIcon,
  PencilSimpleIcon,
  CheckCircleIcon,
  WarningIcon,
  ArrowRightIcon,
  DownloadSimpleIcon,
  InfoIcon,
  CircleNotchIcon,
} from "@phosphor-icons/react";
import { toast } from "sonner";

function getSunday(d = new Date()) {
  const date = new Date(d);
  const day = date.getDay();
  date.setDate(date.getDate() - day);
  return date.toISOString().slice(0, 10);
}
function getSaturday(sundayStr) {
  const d = new Date(sundayStr + "T00:00:00");
  d.setDate(d.getDate() + 6);
  return d.toISOString().slice(0, 10);
}

// ─── Skeleton table rows shown while loading ──────────────────────────────────

function TableRowSkeleton() {
  return (
    <tr className="border-b border-border">
      <td className="px-4 py-3"><Skeleton className="h-4 w-40" /></td>
      <td className="px-4 py-3"><Skeleton className="h-4 w-6" /></td>
      <td className="px-4 py-3"><Skeleton className="h-4 w-24" /></td>
      <td className="px-4 py-3"><Skeleton className="h-4 w-8" /></td>
      <td className="px-4 py-3"><Skeleton className="h-4 w-32" /></td>
      <td className="px-4 py-3 text-right">
        <div className="inline-flex gap-1">
          <Skeleton className="h-7 w-16" />
          <Skeleton className="h-7 w-7" />
          <Skeleton className="h-7 w-7" />
        </div>
      </td>
    </tr>
  );
}

// ─── Column header with an optional tooltip ───────────────────────────────────

function Th({ children, tooltip, className = "" }) {
  return (
    <th className={`kbd-label ${className}`}>
      <span className="inline-flex items-center gap-1">
        {children}
        {tooltip && (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
              >
                <InfoIcon size={11} weight="regular" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-[220px] text-center leading-snug">
              {tooltip}
            </TooltipContent>
          </Tooltip>
        )}
      </span>
    </th>
  );
}

export default function BenefitWeeks() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({
    week_start: getSunday(),
    week_end: getSaturday(getSunday()),
    notes: "",
    certified: false,
    able_to_work: null,
    available_for_work: null,
    worked_for_pay: null,
  });


  const onWeekStart = (val) => {
    setForm({ ...form, week_start: val, week_end: getSaturday(val) });
  };

  const openNew = () => {
    setEditing(null);
    setForm({
      week_start: getSunday(),
      week_end: getSaturday(getSunday()),
      notes: "",
      certified: false,
      able_to_work: null,
      available_for_work: null,
      worked_for_pay: null,
    });
    setOpen(true);
  };

  const openEdit = (w) => {
    setEditing(w);
    setForm({
      week_start: w.week_start,
      week_end: w.week_end,
      notes: w.notes || "",
      certified: !!w.certified,
      able_to_work: w.able_to_work ?? null,
      available_for_work: w.available_for_work ?? null,
      worked_for_pay: w.worked_for_pay ?? null,
    });
    setOpen(true);
  };

  const weeksQuery = useQuery({
    queryKey: queryKeys.weeks.all(),
    queryFn:  () => api.get("/benefit-weeks").then(r => r.data),
  });
  const loading = weeksQuery.isLoading;
  const weeks   = weeksQuery.data ?? [];

  const saveMutation = useMutation({
    mutationFn: () =>
      editing
        ? api.put(`/benefit-weeks/${editing.id}`, form)
        : api.post("/benefit-weeks", form),
    onSuccess: () => {
      toast.success(editing ? "Week updated" : "Week created");
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: queryKeys.weeks.all() });
    },
  });
  const saving = saveMutation.isPending;

  const removeMutation = useMutation({
    mutationFn: (id) => api.delete(`/benefit-weeks/${id}`),
    onSuccess: () => {
      toast.success("Week deleted");
      queryClient.invalidateQueries({ queryKey: queryKeys.weeks.all() });
    },
  });

  const exportAll = async () => {
    try {
      const token = await getValidToken();
      const res = await fetch(`${API}/contacts/export.csv`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Contacts_all.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("All contacts exported");
    } catch {
      toast.error("Export failed");
    }
  };

  return (
    <TooltipProvider delayDuration={300}>
      <div className="space-y-6" data-testid="weeks-page">
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <div className="kbd-label">Compliance Period</div>
            <h1 className="font-display font-black text-4xl tracking-tighter mt-1">
              Benefit Weeks
            </h1>
            <p className="text-sm text-muted-foreground mt-2">
              Weeks run Sunday–Saturday. Each requires ≥ 3 work-search contacts.
            </p>
          </div>
          <Dialog open={open} onOpenChange={setOpen}>
            <div className="flex gap-2">
              <Button
                variant="outline"
                className="rounded-none border-border"
                onClick={exportAll}
                data-testid="export-all-button"
              >
                <DownloadSimpleIcon size={16} weight="bold" className="mr-2" />{" "}
                Export CSV
              </Button>
              <DialogTrigger asChild>
                <Button
                  className="rounded-none bg-primary hover:bg-primary/90"
                  onClick={openNew}
                  data-testid="new-week-button"
                >
                  <PlusIcon size={16} weight="bold" className="mr-2" /> New
                  Benefit Week
                </Button>
              </DialogTrigger>
            </div>
            <DialogContent className="rounded-none" data-testid="week-dialog">
              <DialogHeader>
                <DialogTitle className="font-display tracking-tight">
                  {editing ? "Edit Benefit Week" : "New Benefit Week"}
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                {/* Date range */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="kbd-label">Week Start (Sunday)</Label>
                    <Input
                      type="date"
                      value={form.week_start}
                      onChange={(e) => onWeekStart(e.target.value)}
                      className="rounded-none mt-2"
                      data-testid="week-start-input"
                    />
                  </div>
                  <div>
                    <Label className="kbd-label">Week End (Saturday)</Label>
                    <Input
                      type="date"
                      value={form.week_end}
                      onChange={(e) =>
                        setForm({ ...form, week_end: e.target.value })
                      }
                      className="rounded-none mt-2"
                      data-testid="week-end-input"
                    />
                  </div>
                </div>

                {/* IDES compliance questions */}
                <div className="border border-border bg-secondary p-3 space-y-3">
                  <p className="kbd-label text-xs text-muted-foreground uppercase tracking-widest">
                    IDES Certification Questions
                  </p>

                  {[
                    { key: "able_to_work",       label: "Were you able to work this week?" },
                    { key: "available_for_work", label: "Were you available for work this week?" },
                    { key: "worked_for_pay",     label: "Did you work any hours for pay this week?" },
                  ].map(({ key, label }) => (
                    <div key={key} className="flex items-center justify-between gap-4">
                      <span className="text-sm text-foreground">{label}</span>
                      <div className="flex items-center gap-4 text-sm shrink-0">
                        <label className="flex items-center gap-1.5 cursor-pointer">
                          <input
                            type="radio"
                            name={key}
                            value="yes"
                            checked={form[key] === true}
                            onChange={() => setForm({ ...form, [key]: true })}
                            className="accent-[#0033A0]"
                            data-testid={`${key}-yes`}
                          />
                          Yes
                        </label>
                        <label className="flex items-center gap-1.5 cursor-pointer">
                          <input
                            type="radio"
                            name={key}
                            value="no"
                            checked={form[key] === false}
                            onChange={() => setForm({ ...form, [key]: false })}
                            className="accent-[#0033A0]"
                            data-testid={`${key}-no`}
                          />
                          No
                        </label>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Notes */}
                <div>
                  <Label className="kbd-label">
                    Notes about this week{" "}
                    <span className="text-muted-foreground normal-case font-normal">
                      (illness, holidays, etc.)
                    </span>
                  </Label>
                  <Input
                    value={form.notes}
                    onChange={(e) => setForm({ ...form, notes: e.target.value })}
                    className="rounded-none mt-2"
                    placeholder="e.g. Sick Monday–Tuesday, observed holiday Friday"
                    data-testid="week-notes-input"
                  />
                </div>

                {/* Certified checkbox */}
                <label className="flex items-center gap-2 text-sm pt-1">
                  <input
                    type="checkbox"
                    checked={form.certified}
                    onChange={(e) =>
                      setForm({ ...form, certified: e.target.checked })
                    }
                    data-testid="week-certified-checkbox"
                  />
                  I certified this week with IDES
                </label>
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
                  className="rounded-none bg-primary hover:bg-primary/90"
                  onClick={() => saveMutation.mutate()}
                  disabled={saving}
                  data-testid="week-save-button"
                >
                  {saving ? (
                    <><CircleNotchIcon size={16} weight="bold" className="mr-2 animate-spin" />Saving...</>
                  ) : (
                    "Save"
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        <div className="border border-border bg-background overflow-x-auto">
          <table className="w-full compliance-table text-sm">
            <thead className="bg-secondary border-b border-border">
              <tr className="text-left">
                <Th>Week (Sun → Sat)</Th>
                <Th tooltip="Total work-search contacts logged for this benefit week.">
                  Contacts
                </Th>
                <Th tooltip="COMPLIANT = ≥ 3 contacts logged, meeting the IDES minimum. NON-COMPLIANT = fewer contacts logged.">
                  Status
                </Th>
                <Th tooltip="Whether you submitted your weekly certification to IDES for this period.">
                  Certified
                </Th>
                <Th>Notes</Th>
                <Th className="text-right">Actions</Th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <>
                  <TableRowSkeleton />
                  <TableRowSkeleton />
                  <TableRowSkeleton />
                </>
              )}
              {!loading && weeks.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-center text-muted-foreground py-12">
                    No weeks yet — click "New Benefit Week".
                  </td>
                </tr>
              )}
              {!loading && weeks.map((w) => (
                <tr
                  key={w.id}
                  className="border-b border-border"
                  data-testid={`week-row-${w.id}`}
                >
                  <td className="font-mono-data font-semibold">
                    {w.week_start} → {w.week_end}
                  </td>
                  <td className="font-mono-data">{w.contact_count}</td>
                  <td>
                    {w.contact_count >= 3 ? (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#16A34A]">
                        <CheckCircleIcon size={14} weight="fill" /> COMPLIANT
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#DC2626]">
                        <WarningIcon size={14} weight="fill" />{" "}
                        {3 - w.contact_count} short
                      </span>
                    )}
                  </td>
                  <td className="text-xs">{w.certified ? "YES" : "—"}</td>
                  <td className="text-xs text-muted-foreground max-w-[250px] truncate">
                    {w.notes || "—"}
                  </td>
                  <td className="text-right">
                    <div className="inline-flex gap-1">
                      <Link to={`/weeks/${w.id}`}>
                        <Button
                          size="sm"
                          variant="outline"
                          className="rounded-none border-border"
                          data-testid={`open-week-${w.id}`}
                        >
                          Open{" "}
                          <ArrowRightIcon
                            size={14}
                            className="ml-1"
                            weight="bold"
                          />
                        </Button>
                      </Link>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            size="sm"
                            variant="outline"
                            className="rounded-none border-border"
                            onClick={() => openEdit(w)}
                            data-testid={`edit-week-${w.id}`}
                          >
                            <PencilSimpleIcon size={14} weight="bold" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent side="top">Edit week</TooltipContent>
                      </Tooltip>
                      <AlertDialog>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <AlertDialogTrigger asChild>
                              <Button
                                size="sm"
                                variant="outline"
                                className="rounded-none border-border hover:bg-destructive/10 hover:text-[#DC2626]"
                                data-testid={`delete-week-${w.id}`}
                              >
                                <TrashIcon size={14} weight="bold" />
                              </Button>
                            </AlertDialogTrigger>
                          </TooltipTrigger>
                          <TooltipContent side="top">Delete week</TooltipContent>
                        </Tooltip>
                        <AlertDialogContent className="rounded-none">
                          <AlertDialogHeader>
                            <AlertDialogTitle>
                              Delete benefit week?
                            </AlertDialogTitle>
                            <AlertDialogDescription>
                              All work-search contacts inside this week will also
                              be deleted. This action cannot be undone.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel className="rounded-none">
                              Cancel
                            </AlertDialogCancel>
                            <AlertDialogAction
                              className="rounded-none bg-[#DC2626] hover:bg-destructive/90"
                              onClick={() => removeMutation.mutate(w.id)}
                              data-testid={`confirm-delete-week-${w.id}`}
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
    </TooltipProvider>
  );
}
