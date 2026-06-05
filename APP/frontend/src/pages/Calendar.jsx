import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { CalendarBlank, CheckCircle, Warning } from "@phosphor-icons/react";
import { toast } from "sonner";

function startOfWeek(d) { const x = new Date(d); x.setDate(x.getDate() - x.getDay()); x.setHours(0,0,0,0); return x; }
function addDays(d, n) { const x = new Date(d); x.setDate(x.getDate() + n); return x; }
function iso(d) { return d.toISOString().slice(0, 10); }
function monthGrid(year, month) {
  const first = new Date(year, month, 1);
  const gridStart = startOfWeek(first);
  const cells = [];
  for (let i = 0; i < 42; i++) cells.push(addDays(gridStart, i));
  return cells;
}

export default function CalendarPage() {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const [weeks, setWeeks] = useState([]);

  useEffect(() => {
    api.get("/benefit-weeks")
      .then((r) => setWeeks(r.data))
      .catch((e) => toast.error(formatApiError(e)));
  }, []);

  const weekByStart = useMemo(() => {
    const m = new Map();
    weeks.forEach((w) => m.set(w.week_start, w));
    return m;
  }, [weeks]);

  const cells = monthGrid(year, month);
  const monthName = new Date(year, month, 1).toLocaleString("en-US", { month: "long", year: "numeric" });

  const prev = () => {
    let m = month - 1, y = year;
    if (m < 0) { m = 11; y--; }
    setMonth(m); setYear(y);
  };
  const next = () => {
    let m = month + 1, y = year;
    if (m > 11) { m = 0; y++; }
    setMonth(m); setYear(y);
  };

  return (
    <div className="space-y-6" data-testid="calendar-page">
      <div>
        <div className="kbd-label">Weekly Compliance Calendar</div>
        <h1 className="font-display font-black text-4xl tracking-tighter mt-1">Calendar</h1>
        <p className="text-sm text-zinc-600 mt-2 max-w-2xl">
          Sunday rows highlight weeks you've logged. Green = compliant, red = under 3 contacts.
        </p>
      </div>

      <div className="border border-zinc-200 bg-white">
        <div className="px-6 py-4 border-b border-zinc-200 flex items-center justify-between">
          <button onClick={prev} className="text-sm font-semibold border border-zinc-300 px-3 py-1 hover:border-[#0033A0]" data-testid="calendar-prev">← Prev</button>
          <h2 className="font-display font-bold text-xl tracking-tight">{monthName}</h2>
          <button onClick={next} className="text-sm font-semibold border border-zinc-300 px-3 py-1 hover:border-[#0033A0]" data-testid="calendar-next">Next →</button>
        </div>

        <div className="grid grid-cols-7 border-b border-zinc-200">
          {["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map((d) => (
            <div key={d} className="kbd-label py-2 px-3 text-center border-r last:border-r-0 border-zinc-200">{d}</div>
          ))}
        </div>

        <div className="grid grid-cols-7">
          {cells.map((d, i) => {
            const inMonth = d.getMonth() === month;
            const isToday = iso(d) === iso(today);
            // a cell is "head of week" if it's Sunday — then we look up the matching week
            const isSunday = d.getDay() === 0;
            const matched = isSunday ? weekByStart.get(iso(d)) : null;

            return (
              <div
                key={i}
                className={`min-h-[88px] border-b border-r border-zinc-100 p-2 ${inMonth ? "bg-white" : "bg-[#FAFAFA]"} ${isToday ? "ring-2 ring-[#0033A0] ring-inset" : ""}`}
                data-testid={`cal-cell-${iso(d)}`}
              >
                <div className={`text-xs font-mono-data ${inMonth ? "text-zinc-900" : "text-zinc-400"}`}>{d.getDate()}</div>
                {matched && (
                  <Link to={`/weeks/${matched.id}`} className="block mt-1" data-testid={`cal-week-${matched.id}`}>
                    <div className={`text-[10px] font-semibold uppercase tracking-wider inline-flex items-center gap-1 px-1.5 py-0.5 border ${matched.contact_count >= 3 ? "border-[#16A34A] text-[#16A34A] bg-green-50" : "border-[#DC2626] text-[#DC2626] bg-red-50"}`}>
                      {matched.contact_count >= 3 ? <CheckCircle size={10} weight="fill" /> : <Warning size={10} weight="fill" />}
                      Week · {matched.contact_count}/3
                    </div>
                    <div className="text-[10px] text-zinc-500 mt-1">Sun–Sat</div>
                  </Link>
                )}
              </div>
            );
          })}
        </div>

        <div className="px-6 py-3 border-t border-zinc-200 flex items-center gap-4 text-xs text-zinc-600">
          <CalendarBlank size={14} weight="bold" />
          <span>{weeks.length} logged week{weeks.length === 1 ? "" : "s"} for active claimant</span>
        </div>
      </div>
    </div>
  );
}
