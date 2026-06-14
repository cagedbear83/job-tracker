import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  CheckCircleIcon,
  WarningIcon,
  IdentificationCardIcon,
  CalendarBlankIcon,
  BriefcaseIcon,
  PlusIcon,
  TrendUpIcon,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  ReferenceLine,
  Cell,
} from "recharts";

function Metric({ label, value, accent, testid }) {
  return (
    <div className="border border-zinc-200 bg-white p-6" data-testid={testid}>
      <div className="kbd-label">{label}</div>
      <div
        className={`mt-3 font-display font-black text-4xl tracking-tighter ${accent || "text-zinc-900"}`}
      >
        {value}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [weeks, setWeeks] = useState([]);
  const [trend, setTrend] = useState([]);
  const [range, setRange] = useState(12);

  useEffect(() => {
    (async () => {
      try {
        const [d, w] = await Promise.all([
          api.get("/dashboard"),
          api.get("/benefit-weeks"),
        ]);
        setStats(d.data);
        setWeeks(w.data);
      } catch (e) {
        toast.error(formatApiError(e));
      }
    })();
  }, []);

  useEffect(() => {
    api
      .get(`/dashboard/trend?weeks=${range}`)
      .then((r) => setTrend(r.data))
      .catch(() => {});
  }, [range]);

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="kbd-label">Overview</div>
          <h1 className="font-display font-black text-4xl sm:text-5xl tracking-tighter mt-1">
            Dashboard
          </h1>
        </div>
        <div className="flex gap-2">
          <Link to="/weeks">
            <Button
              className="rounded-none bg-[#0033A0] hover:bg-[#002266]"
              data-testid="dashboard-new-week"
            >
              <PlusIcon className="mr-2" size={16} weight="bold" /> New Benefit
              Week
            </Button>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Metric
          label="Benefit Weeks"
          value={stats?.total_weeks ?? "—"}
          testid="metric-weeks"
        />
        <Metric
          label="Total Contacts"
          value={stats?.total_contacts ?? "—"}
          testid="metric-contacts"
        />
        <Metric
          label="Compliant Weeks"
          value={stats?.compliant_weeks ?? "—"}
          accent="text-[#16A34A]"
          testid="metric-compliant"
        />
        <Metric
          label="Non-Compliant"
          value={stats?.non_compliant_weeks ?? "—"}
          accent="text-[#DC2626]"
          testid="metric-noncompliant"
        />
      </div>

      {trend.length > 0 && (
        <div
          className="border border-zinc-200 bg-white"
          data-testid="trend-chart"
        >
          <div className="px-6 py-4 border-b border-zinc-200 flex items-center justify-between flex-wrap gap-3">
            <div>
              <div className="kbd-label flex items-center gap-2">
                <TrendUpIcon size={12} weight="bold" /> Compliance Trend
              </div>
              <h2 className="font-display font-bold text-xl tracking-tight">
                Last {trend.length} of {range} weeks
              </h2>
            </div>
            <div className="flex items-center gap-3">
              <div
                className="flex border border-zinc-300"
                data-testid="trend-range-toggle"
              >
                {[4, 12, 52].map((n) => (
                  <button
                    key={n}
                    onClick={() => setRange(n)}
                    data-testid={`trend-range-${n}`}
                    className={`px-3 py-1 text-xs font-semibold uppercase tracking-wider ${range === n ? "bg-[#0033A0] text-white" : "bg-white text-zinc-600 hover:text-zinc-900"}`}
                  >
                    {n} wk
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-4 text-xs">
                <span className="inline-flex items-center gap-1">
                  <span className="w-3 h-3 bg-[#16A34A]" /> ≥3
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="w-3 h-3 bg-[#DC2626]" /> &lt;3
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="border-t-2 border-dashed border-[#0033A0] w-4" />{" "}
                  target
                </span>
              </div>
            </div>
          </div>
          <div className="p-4">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart
                data={trend}
                margin={{ top: 8, right: 8, left: 0, bottom: 8 }}
              >
                <XAxis
                  dataKey="week_start"
                  tick={{ fontSize: 11, fontFamily: "IBM Plex Sans" }}
                  stroke="#52525B"
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 11 }}
                  stroke="#52525B"
                />
                <Tooltip
                  cursor={{ fill: "#F4F4F5" }}
                  contentStyle={{
                    border: "1px solid #D4D4D8",
                    borderRadius: 0,
                    fontFamily: "IBM Plex Sans",
                    fontSize: 12,
                  }}
                  formatter={(v, n, p) => [
                    `${v} contacts`,
                    p?.payload?.compliant ? "Compliant" : "Non-compliant",
                  ]}
                  labelFormatter={(l) => `Week of ${l}`}
                />
                <ReferenceLine y={3} stroke="#0033A0" strokeDasharray="4 4" />
                <Bar dataKey="contacts" radius={0}>
                  {trend.map((entry, idx) => (
                    <Cell
                      key={idx}
                      fill={entry.compliant ? "#16A34A" : "#DC2626"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {!stats?.profile_complete && (
        <div className="border-l-4 border-[#EAB308] bg-yellow-50 p-4 flex items-start gap-3">
          <WarningIcon
            size={20}
            weight="fill"
            className="text-[#EAB308] flex-shrink-0 mt-0.5"
          />
          <div className="text-sm">
            <div className="font-semibold text-zinc-900">
              Complete your Claimant Profile
            </div>
            <p className="text-zinc-700 mt-1">
              Your profile information is required to generate proper work
              search reports.{" "}
              <Link
                to="/profile"
                className="font-semibold underline text-[#0033A0]"
                data-testid="dashboard-profile-link"
              >
                Go to profile →
              </Link>
            </p>
          </div>
        </div>
      )}

      <div className="border border-zinc-200 bg-white">
        <div className="px-6 py-4 border-b border-zinc-200 flex items-center justify-between">
          <div>
            <div className="kbd-label">Recent</div>
            <h2 className="font-display font-bold text-xl tracking-tight">
              Benefit Weeks
            </h2>
          </div>
          <Link
            to="/weeks"
            className="text-sm font-semibold text-[#0033A0] underline"
          >
            View all
          </Link>
        </div>
        <div className="divide-y divide-zinc-100">
          {weeks.length === 0 && (
            <div className="px-6 py-12 text-center text-sm text-zinc-500">
              <CalendarBlankIcon
                size={32}
                weight="thin"
                className="mx-auto mb-2 text-zinc-400"
              />
              No benefit weeks yet. Create your first one.
            </div>
          )}
          {weeks.slice(0, 5).map((w) => (
            <Link
              key={w.id}
              to={`/weeks/${w.id}`}
              className="flex items-center justify-between px-6 py-4 hover:bg-zinc-50 transition-colors"
              data-testid={`dashboard-week-${w.id}`}
            >
              <div className="flex items-center gap-4">
                <CalendarBlankIcon
                  size={20}
                  weight="regular"
                  className="text-zinc-500"
                />
                <div>
                  <div className="font-semibold text-zinc-900 font-mono-data">
                    {w.week_start} → {w.week_end}
                  </div>
                  <div className="kbd-label mt-1">
                    {w.contact_count} contacts logged
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {w.contact_count >= 3 ? (
                  <span className="flex items-center gap-1 text-xs font-semibold text-[#16A34A]">
                    <CheckCircleIcon size={14} weight="fill" /> COMPLIANT
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-xs font-semibold text-[#DC2626]">
                    <WarningIcon size={14} weight="fill" />{" "}
                    {3 - w.contact_count} MORE NEEDED
                  </span>
                )}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
