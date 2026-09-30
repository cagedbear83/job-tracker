import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useSubscription } from "@/hooks/useSubscription";
import { useUpgradeModal } from "@/components/UpgradeModal";
import {
  CheckCircleIcon,
  WarningIcon,
  CalendarBlankIcon,
  PlusIcon,
  TrendUpIcon,
  LockSimpleIcon,
  InfoIcon,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  ReferenceLine,
  Cell,
} from "recharts";

// ─── Skeleton shown while the initial API call is in flight ──────────────────

function MetricSkeleton() {
  return (
    <div className="border border-border bg-background p-6">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="h-10 w-16 mt-3" />
    </div>
  );
}

function WeekRowSkeleton() {
  return (
    <div className="flex items-center justify-between px-6 py-4">
      <div className="flex items-center gap-4">
        <Skeleton className="h-5 w-5 rounded-full" />
        <div>
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-3 w-24 mt-1.5" />
        </div>
      </div>
      <Skeleton className="h-4 w-20" />
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading dashboard">
      {/* Header */}
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <Skeleton className="h-3 w-16 mb-2" />
          <Skeleton className="h-12 w-48" />
        </div>
        <Skeleton className="h-10 w-36" />
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[0, 1, 2, 3].map((i) => (
          <MetricSkeleton key={i} />
        ))}
      </div>

      {/* Recent weeks */}
      <div className="border border-border bg-background">
        <div className="px-6 py-4 border-b border-border flex items-center justify-between">
          <div>
            <Skeleton className="h-3 w-16 mb-2" />
            <Skeleton className="h-6 w-36" />
          </div>
          <Skeleton className="h-4 w-14" />
        </div>
        <div className="divide-y divide-border">
          {[0, 1, 2].map((i) => (
            <WeekRowSkeleton key={i} />
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Metric card with optional tooltip ───────────────────────────────────────

function Metric({ label, value, accent, tooltip, testid }) {
  return (
    <div className="border border-border bg-background p-6" data-testid={testid}>
      <div className="kbd-label flex items-center gap-1.5">
        {label}
        {tooltip && (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
              >
                <InfoIcon size={11} weight="regular" aria-label={`Info: ${label}`} />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-[220px] text-center leading-snug">
              {tooltip}
            </TooltipContent>
          </Tooltip>
        )}
      </div>
      <div
        className={`mt-3 font-display font-black text-4xl tracking-tighter ${accent || "text-foreground"}`}
      >
        {value}
      </div>
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { hasFeature } = useSubscription();
  const { show } = useUpgradeModal();
  const canAnalytics = hasFeature("advanced_analytics");

  const [loading, setLoading] = useState(true);
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
      } catch (err) {
        toast.error(formatApiError(err));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    // Advanced analytics is a paid feature — skip the request entirely on the
    // free tier (the backend would return 402) and show a locked card instead.
    if (!canAnalytics) {
      setTrend([]);
      return;
    }
    api
      .get(`/dashboard/trend?weeks=${range}`)
      .then((r) => setTrend(r.data))
      .catch(() => {});
  }, [range, canAnalytics]);

  if (loading) {
    return <DashboardSkeleton />;
  }

  return (
    <TooltipProvider delayDuration={300}>
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
                className="rounded-none bg-primary hover:bg-primary/90"
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
            tooltip="Total benefit weeks on record for your account."
            testid="metric-weeks"
          />
          <Metric
            label="Total Contacts"
            value={stats?.total_contacts ?? "—"}
            tooltip="Total work-search contacts logged across all benefit weeks."
            testid="metric-contacts"
          />
          <Metric
            label="Compliant Weeks"
            value={stats?.compliant_weeks ?? "—"}
            accent="text-[#16A34A]"
            tooltip="Weeks where you logged ≥ 3 contacts — the IDES minimum to remain eligible for benefits."
            testid="metric-compliant"
          />
          <Metric
            label="Non-Compliant"
            value={stats?.non_compliant_weeks ?? "—"}
            accent="text-[#DC2626]"
            tooltip="Weeks with fewer than 3 contacts logged. Log more contacts or contact your case worker if you need an exemption."
            testid="metric-noncompliant"
          />
        </div>

        {!canAnalytics && (
          <button
            type="button"
            onClick={() =>
              show({
                feature: "advanced_analytics",
                message:
                  "Compliance trend analytics are available on paid plans.",
              })
            }
            className="w-full text-left border border-border bg-background p-6 flex items-center justify-between hover:bg-secondary transition-colors"
            data-testid="trend-locked"
          >
            <div>
              <div className="kbd-label flex items-center gap-2">
                <TrendUpIcon size={12} weight="bold" /> Compliance Trend
              </div>
              <p className="text-sm text-muted-foreground mt-1">
                See your work-search compliance over time. Upgrade to unlock
                analytics.
              </p>
            </div>
            <LockSimpleIcon size={20} weight="bold" className="text-muted-foreground" />
          </button>
        )}

        {canAnalytics && trend.length > 0 && (
          <div
            className="border border-border bg-background"
            data-testid="trend-chart"
          >
            <div className="px-6 py-4 border-b border-border flex items-center justify-between flex-wrap gap-3">
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
                  className="flex border border-border"
                  data-testid="trend-range-toggle"
                >
                  {[4, 12, 52].map((n) => (
                    <button
                      key={n}
                      type="button"
                      onClick={() => setRange(n)}
                      data-testid={`trend-range-${n}`}
                      className={`px-3 py-1 text-xs font-semibold uppercase tracking-wider ${range === n ? "bg-primary text-white" : "bg-background text-muted-foreground hover:text-foreground"}`}
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
                    <span className="border-t-2 border-dashed border-primary w-4" />{" "}
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
                    tick={{ fontSize: 11, fontFamily: "IBM Plex Sans", fill: "hsl(var(--muted-foreground))" }}
                    stroke="hsl(var(--border))"
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                    stroke="hsl(var(--border))"
                  />
                  <ChartTooltip
                    cursor={{ fill: "hsl(var(--secondary))" }}
                    contentStyle={{
                      background: "hsl(var(--popover))",
                      color: "hsl(var(--popover-foreground))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: 0,
                      fontFamily: "IBM Plex Sans",
                      fontSize: 12,
                    }}
                    labelStyle={{ color: "hsl(var(--popover-foreground))" }}
                    itemStyle={{ color: "hsl(var(--popover-foreground))" }}
                    formatter={(v, n, p) => [
                      `${v} contacts`,
                      p?.payload?.compliant ? "Compliant" : "Non-compliant",
                    ]}
                    labelFormatter={(l) => `Week of ${l}`}
                  />
                  <ReferenceLine y={3} stroke="hsl(var(--primary))" strokeDasharray="4 4" />
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
          <div className="border-l-4 border-[#EAB308] bg-[#EAB308]/10 p-4 flex items-start gap-3">
            <WarningIcon
              size={20}
              weight="fill"
              className="text-[#EAB308] flex-shrink-0 mt-0.5"
            />
            <div className="text-sm">
              <div className="font-semibold text-foreground">
                Complete your Claimant Profile
              </div>
              <p className="text-foreground mt-1">
                Your profile information is required to generate proper work
                search reports.{" "}
                <Link
                  to="/profile"
                  className="font-semibold underline text-primary"
                  data-testid="dashboard-profile-link"
                >
                  Go to profile →
                </Link>
              </p>
            </div>
          </div>
        )}

        <div className="border border-border bg-background">
          <div className="px-6 py-4 border-b border-border flex items-center justify-between">
            <div>
              <div className="kbd-label">Recent</div>
              <h2 className="font-display font-bold text-xl tracking-tight">
                Benefit Weeks
              </h2>
            </div>
            <Link
              to="/weeks"
              className="text-sm font-semibold text-primary underline"
            >
              View all
            </Link>
          </div>
          <div className="divide-y divide-border">
            {weeks.length === 0 && (
              <div className="px-6 py-12 text-center text-sm text-muted-foreground">
                <CalendarBlankIcon
                  size={32}
                  weight="thin"
                  className="mx-auto mb-2 text-muted-foreground"
                />
                No benefit weeks yet. Create your first one.
              </div>
            )}
            {weeks.slice(0, 5).map((w) => (
              <Link
                key={w.id}
                to={`/weeks/${w.id}`}
                className="flex items-center justify-between px-6 py-4 hover:bg-secondary transition-colors"
                data-testid={`dashboard-week-${w.id}`}
              >
                <div className="flex items-center gap-4">
                  <CalendarBlankIcon
                    size={20}
                    weight="regular"
                    className="text-muted-foreground"
                  />
                  <div>
                    <div className="font-semibold text-foreground font-mono-data">
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
    </TooltipProvider>
  );
}
