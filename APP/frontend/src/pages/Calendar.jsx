import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import {
  CalendarBlankIcon,
  CheckCircleIcon,
  WarningIcon,
  PlusIcon,
  TrashIcon,
  PencilSimpleIcon,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { FeatureGate } from "@/components/FeatureGate";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";

// ── Event type config ────────────────────────────────────────────────────────
const EVENT_TYPES = [
  { value: "certification",  label: "Certification",   color: "#0033A0", bg: "#EEF2FF" },
  { value: "ides_interview", label: "IDES Interview",  color: "#7C3AED", bg: "#F5F3FF" },
  { value: "appeal",         label: "Appeal",          color: "#DC2626", bg: "#FEF2F2" },
  { value: "questionnaire",  label: "Questionnaire",   color: "#D97706", bg: "#FFFBEB" },
  { value: "other",          label: "Other",           color: "#6B7280", bg: "#F3F4F6" },
];

const typeMap = Object.fromEntries(EVENT_TYPES.map((t) => [t.value, t]));

// ── Date helpers ─────────────────────────────────────────────────────────────
function startOfWeek(d) {
  const x = new Date(d);
  x.setDate(x.getDate() - x.getDay());
  x.setHours(0, 0, 0, 0);
  return x;
}
function addDays(d, n) {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}
function iso(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}
function monthGrid(year, month) {
  const first = new Date(year, month, 1);
  const gridStart = startOfWeek(first);
  const cells = [];
  for (let i = 0; i < 42; i++) cells.push(addDays(gridStart, i));
  return cells;
}
function fmtDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return new Date(y, m - 1, d).toLocaleDateString("en-US", {
    weekday: "long", month: "long", day: "numeric", year: "numeric",
  });
}

// ── Blank event form ─────────────────────────────────────────────────────────
const blank = (date = "") => ({
  event_date: date,
  event_type: "certification",
  title: "",
  notes: "",
});

export default function CalendarPage() {
  const today = new Date();
  const [year, setYear]   = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());

  const [weeks,  setWeeks]  = useState([]);
  const [events, setEvents] = useState([]);

  // Day-detail dialog
  const [dayDialog, setDayDialog]   = useState(false);
  const [selectedDay, setSelectedDay] = useState("");

  // Add/Edit event dialog
  const [eventDialog, setEventDialog] = useState(false);
  const [editingEvent, setEditingEvent] = useState(null);
  const [form, setForm] = useState(blank());
  const [saving, setSaving] = useState(false);

  // ── Data loading ───────────────────────────────────────────────────────────
  const load = async () => {
    try {
      const [w, e] = await Promise.all([
        api.get("/benefit-weeks"),
        api.get("/calendar-events"),
      ]);
      setWeeks(w.data);
      setEvents(e.data);
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  useEffect(() => { load(); }, []);

  // ── Lookups ────────────────────────────────────────────────────────────────
  const weekByStart = useMemo(() => {
    const m = new Map();
    weeks.forEach((w) => m.set(w.week_start, w));
    return m;
  }, [weeks]);

  // Map ISO date → events[]
  const eventsByDate = useMemo(() => {
    const m = new Map();
    events.forEach((e) => {
      if (!m.has(e.event_date)) m.set(e.event_date, []);
      m.get(e.event_date).push(e);
    });
    return m;
  }, [events]);

  const dayEvents = useMemo(
    () => eventsByDate.get(selectedDay) || [],
    [eventsByDate, selectedDay]
  );

  // ── Calendar nav ───────────────────────────────────────────────────────────
  const cells = monthGrid(year, month);
  const monthName = new Date(year, month, 1).toLocaleString("en-US", {
    month: "long", year: "numeric",
  });

  const prev = () => {
    if (month === 0) { setMonth(11); setYear(y => y - 1); }
    else setMonth(m => m - 1);
  };
  const next = () => {
    if (month === 11) { setMonth(0); setYear(y => y + 1); }
    else setMonth(m => m + 1);
  };

  // ── Day click ──────────────────────────────────────────────────────────────
  const openDay = (dateStr) => {
    setSelectedDay(dateStr);
    setDayDialog(true);
  };

  // ── Event CRUD ─────────────────────────────────────────────────────────────
  const openNewEvent = (date = selectedDay) => {
    setEditingEvent(null);
    setForm(blank(date));
    setDayDialog(false);
    setEventDialog(true);
  };

  const openEditEvent = (evt) => {
    setEditingEvent(evt);
    setForm({
      event_date: evt.event_date,
      event_type: evt.event_type,
      title: evt.title,
      notes: evt.notes || "",
    });
    setDayDialog(false);
    setEventDialog(true);
  };

  const saveEvent = async () => {
    if (!form.title.trim()) { toast.error("Title is required"); return; }
    setSaving(true);
    try {
      if (editingEvent) {
        await api.put(`/calendar-events/${editingEvent.id}`, form);
        toast.success("Event updated");
      } else {
        await api.post("/calendar-events", form);
        toast.success("Event added");
      }
      setEventDialog(false);
      await load();
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setSaving(false);
    }
  };

  const deleteEvent = async (eid) => {
    try {
      await api.delete(`/calendar-events/${eid}`);
      toast.success("Event deleted");
      await load();
      // Re-open day dialog with refreshed list
      setDayDialog(true);
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6" data-testid="calendar-page">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="kbd-label">Weekly Compliance Calendar</div>
          <h1 className="font-display font-black text-4xl tracking-tighter mt-1">
            Calendar
          </h1>
          <p className="text-sm text-zinc-600 mt-2 max-w-2xl">
            Click any day to view or add IDES events. Green/red badges show
            benefit-week compliance.
          </p>
        </div>
        <FeatureGate feature="calendar_events">
          <Button
            className="rounded-none bg-[#0033A0] hover:bg-[#002266]"
            onClick={() => openNewEvent(iso(today))}
            data-testid="add-event-button"
          >
            <PlusIcon size={16} weight="bold" className="mr-2" /> Add Event
          </Button>
        </FeatureGate>
      </div>

      {/* ── Event type legend ── */}
      <div className="flex flex-wrap gap-2">
        {EVENT_TYPES.map((t) => (
          <span
            key={t.value}
            className="inline-flex items-center gap-1.5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider border"
            style={{ borderColor: t.color, color: t.color, background: t.bg }}
          >
            <span className="w-2 h-2 rounded-full" style={{ background: t.color }} />
            {t.label}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider border border-green-600 text-green-700 bg-green-50">
          <CheckCircleIcon size={10} weight="fill" /> Week ≥3 contacts
        </span>
        <span className="inline-flex items-center gap-1.5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider border border-red-600 text-red-700 bg-red-50">
          <WarningIcon size={10} weight="fill" /> Week &lt;3 contacts
        </span>
      </div>

      {/* ── Calendar grid ── */}
      <div className="border border-zinc-200 bg-white">
        {/* Header nav */}
        <div className="px-6 py-4 border-b border-zinc-200 flex items-center justify-between">
          <button
            type="button"
            aria-label="Previous month"
            onClick={prev}
            className="text-sm font-semibold border border-zinc-300 px-3 py-1 hover:border-[#0033A0]"
            data-testid="calendar-prev"
          >
            ← Prev
          </button>
          <h2 className="font-display font-bold text-xl tracking-tight">{monthName}</h2>
          <button
            type="button"
            aria-label="Next month"
            onClick={next}
            className="text-sm font-semibold border border-zinc-300 px-3 py-1 hover:border-[#0033A0]"
            data-testid="calendar-next"
          >
            Next →
          </button>
        </div>

        {/* Day-of-week headers */}
        <div className="grid grid-cols-7 border-b border-zinc-200">
          {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
            <div key={d} className="kbd-label py-2 px-3 text-center border-r last:border-r-0 border-zinc-200">
              {d}
            </div>
          ))}
        </div>

        {/* Day cells */}
        <div className="grid grid-cols-7">
          {cells.map((d, i) => {
            const dateStr  = iso(d);
            const inMonth  = d.getMonth() === month;
            const isToday  = dateStr === iso(today);
            const isSunday = d.getDay() === 0;
            const matched  = isSunday ? weekByStart.get(dateStr) : null;
            const dayEvts  = eventsByDate.get(dateStr) || [];
            const MAX_DOTS = 2;

            return (
              <div
                key={i}
                role="button"
                tabIndex={0}
                onClick={() => openDay(dateStr)}
                onKeyDown={(evt) => {
                  if (evt.key === "Enter" || evt.key === " ") {
                    evt.preventDefault();
                    openDay(dateStr);
                  }
                }}
                className={`min-h-[96px] border-b border-r border-zinc-100 p-2 cursor-pointer transition-colors
                  ${inMonth ? "bg-white hover:bg-zinc-50" : "bg-[#FAFAFA] hover:bg-zinc-100"}
                  ${isToday ? "ring-2 ring-[#0033A0] ring-inset" : ""}`}
                data-testid={`cal-cell-${dateStr}`}
              >
                {/* Date number */}
                <div className={`text-xs font-mono-data ${inMonth ? "text-zinc-900" : "text-zinc-400"}`}>
                  {d.getDate()}
                </div>

                {/* Benefit week badge (Sundays only) */}
                {matched && (
                  <Link
                    to={`/weeks/${matched.id}`}
                    onClick={(e) => e.stopPropagation()}
                    className="block mt-1"
                    data-testid={`cal-week-${matched.id}`}
                  >
                    <div
                      className={`text-[10px] font-semibold uppercase tracking-wider inline-flex items-center gap-1 px-1.5 py-0.5 border
                        ${matched.contact_count >= 3
                          ? "border-[#16A34A] text-[#16A34A] bg-green-50"
                          : "border-[#DC2626] text-[#DC2626] bg-red-50"}`}
                    >
                      {matched.contact_count >= 3
                        ? <CheckCircleIcon size={10} weight="fill" />
                        : <WarningIcon size={10} weight="fill" />}
                      {matched.contact_count}/3
                    </div>
                  </Link>
                )}

                {/* Event dots */}
                {dayEvts.length > 0 && (
                  <div className="mt-1 space-y-0.5">
                    {dayEvts.slice(0, MAX_DOTS).map((evt) => {
                      const t = typeMap[evt.event_type] || typeMap.other;
                      return (
                        <div
                          key={evt.id}
                          className="text-[10px] font-semibold truncate px-1 py-0.5 leading-none"
                          style={{ background: t.bg, color: t.color, borderLeft: `2px solid ${t.color}` }}
                          title={evt.title}
                        >
                          {evt.title}
                        </div>
                      );
                    })}
                    {dayEvts.length > MAX_DOTS && (
                      <div className="text-[10px] text-zinc-400 pl-1">
                        +{dayEvts.length - MAX_DOTS} more
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="px-6 py-3 border-t border-zinc-200 flex items-center gap-4 text-xs text-zinc-600">
          <CalendarBlankIcon size={14} weight="bold" />
          <span>
            {weeks.length} logged week{weeks.length !== 1 ? "s" : ""} ·{" "}
            {events.length} IDES event{events.length !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {/* ── Day detail dialog ── */}
      <Dialog open={dayDialog} onOpenChange={setDayDialog}>
        <DialogContent className="rounded-none max-w-md" data-testid="day-dialog">
          <DialogHeader>
            <DialogTitle className="font-display tracking-tight">
              {fmtDate(selectedDay)}
            </DialogTitle>
          </DialogHeader>

          {dayEvents.length === 0 ? (
            <p className="text-sm text-zinc-500 py-2">No events on this day.</p>
          ) : (
            <div className="space-y-2">
              {dayEvents.map((evt) => {
                const t = typeMap[evt.event_type] || typeMap.other;
                return (
                  <div
                    key={evt.id}
                    className="flex items-start justify-between gap-3 p-3 border"
                    style={{ borderColor: t.color + "44", background: t.bg }}
                  >
                    <div className="min-w-0">
                      <div className="text-[10px] font-semibold uppercase tracking-wider mb-1" style={{ color: t.color }}>
                        {t.label}
                      </div>
                      <div className="text-sm font-semibold text-zinc-900 truncate">{evt.title}</div>
                      {evt.notes && (
                        <div className="text-xs text-zinc-500 mt-1 line-clamp-2">{evt.notes}</div>
                      )}
                    </div>
                    <div className="flex gap-1 shrink-0">
                      <button
                        type="button"
                        onClick={() => openEditEvent(evt)}
                        className="p-1 text-zinc-400 hover:text-[#0033A0]"
                        aria-label="Edit event"
                      >
                        <PencilSimpleIcon size={14} weight="bold" />
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteEvent(evt.id)}
                        className="p-1 text-zinc-400 hover:text-red-600"
                        aria-label="Delete event"
                      >
                        <TrashIcon size={14} weight="bold" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <DialogFooter className="gap-2">
            <Button variant="outline" className="rounded-none" onClick={() => setDayDialog(false)}>
              Close
            </Button>
            <Button
              className="rounded-none bg-[#0033A0] hover:bg-[#002266]"
              onClick={() => openNewEvent(selectedDay)}
            >
              <PlusIcon size={14} weight="bold" className="mr-1.5" /> Add Event
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Add / Edit event dialog ── */}
      <Dialog open={eventDialog} onOpenChange={setEventDialog}>
        <DialogContent className="rounded-none max-w-md" data-testid="event-dialog">
          <DialogHeader>
            <DialogTitle className="font-display tracking-tight">
              {editingEvent ? "Edit Event" : "Add IDES Event"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {/* Event type */}
            <div>
              <Label className="kbd-label">Event Type</Label>
              <div className="grid grid-cols-2 gap-2 mt-2">
                {EVENT_TYPES.map((t) => (
                  <label
                    key={t.value}
                    className={`flex items-center gap-2 p-2 border cursor-pointer text-sm transition-colors
                      ${form.event_type === t.value
                        ? "border-[#0033A0] bg-[#EEF2FF] font-semibold text-[#0033A0]"
                        : "border-zinc-200 hover:border-zinc-400"}`}
                  >
                    <input
                      type="radio"
                      name="event_type"
                      value={t.value}
                      checked={form.event_type === t.value}
                      onChange={() => setForm({ ...form, event_type: t.value })}
                      className="accent-[#0033A0]"
                    />
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ background: t.color }}
                    />
                    {t.label}
                  </label>
                ))}
              </div>
            </div>

            {/* Title */}
            <div>
              <Label className="kbd-label">Title</Label>
              <Input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="e.g. Bi-weekly certification due"
                className="rounded-none mt-2"
                data-testid="event-title-input"
              />
            </div>

            {/* Date */}
            <div>
              <Label className="kbd-label">Date</Label>
              <Input
                type="date"
                value={form.event_date}
                onChange={(e) => setForm({ ...form, event_date: e.target.value })}
                className="rounded-none mt-2"
                data-testid="event-date-input"
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
                placeholder="Additional details"
                className="rounded-none mt-2"
                data-testid="event-notes-input"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" className="rounded-none" onClick={() => setEventDialog(false)}>
              Cancel
            </Button>
            <Button
              className="rounded-none bg-[#0033A0] hover:bg-[#002266]"
              onClick={saveEvent}
              disabled={saving}
              data-testid="event-save-button"
            >
              {saving ? "Saving…" : "Save Event"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}