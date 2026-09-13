import { useEffect, useState, useCallback, useMemo } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  MagnifyingGlassIcon,
  FunnelIcon,
  XIcon,
  BookmarkSimpleIcon,
  TagIcon,
  CaretDownIcon,
  ArrowRightIcon,
  LockIcon,
  CircleNotchIcon,
} from "@phosphor-icons/react";
import { toast } from "sonner";

// ─── Helpers ─────────────────────────────────────────────────────────────────

const EMPTY_FILTERS = {
  result: "",
  method: "",
  type_of_work: "",
  tags: [],
  date_mode: "none", // "none" | "single" | "range"
  date_single: "",
  date_from: "",
  date_to: "",
};

function activeFilterCount(filters) {
  let n = 0;
  if (filters.result) n++;
  if (filters.method) n++;
  if (filters.type_of_work) n++;
  if (filters.tags.length) n++;
  if (filters.date_mode !== "none") n++;
  return n;
}

function fmtDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `${m}/${d}/${y}`;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function TagChip({ name, onRemove, small }) {
  return (
    <span
      className={`inline-flex items-center gap-1 bg-secondary border border-border text-foreground font-medium ${
        small ? "text-[10px] px-1.5 py-0.5" : "text-xs px-2 py-0.5"
      }`}
    >
      <TagIcon size={small ? 9 : 11} />
      {name}
      {onRemove && (
        <button type="button" onClick={onRemove} className="ml-0.5 hover:text-destructive">
          <XIcon size={small ? 9 : 11} />
        </button>
      )}
    </span>
  );
}

function FacetOption({ label, count, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center justify-between w-full px-3 py-1.5 text-sm hover:bg-secondary text-left ${
        active ? "bg-secondary font-semibold text-foreground" : "text-muted-foreground"
      }`}
    >
      <span className="truncate">{label}</span>
      <span className="ml-2 text-xs tabular-nums shrink-0 text-muted-foreground">
        {count}
      </span>
    </button>
  );
}

function GatedRow({ row }) {
  return (
    <tr className="border-b border-border relative">
      <td colSpan={6} className="p-0">
        <div className="relative overflow-hidden">
          <div className="flex items-center gap-4 px-4 py-3 select-none pointer-events-none opacity-40 blur-[3px]">
            <span className="inline-block w-24 h-4 bg-muted rounded" />
            <span className="inline-block w-36 h-4 bg-muted rounded" />
            <span className="inline-block w-20 h-4 bg-muted rounded" />
            <span className="inline-block w-28 h-4 bg-muted rounded" />
            <span className="inline-block w-16 h-4 bg-muted rounded" />
          </div>
          <div className="absolute inset-0 flex items-center justify-center bg-background/60">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <LockIcon size={13} weight="bold" />
              <span>
                Week {fmtDate(row.week_start)}–{fmtDate(row.week_end)} ·{" "}
                <Link to="/profile#subscription" className="underline hover:text-primary">
                  Upgrade to view
                </Link>
              </span>
            </div>
          </div>
        </div>
      </td>
    </tr>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function AllContacts() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [inputQ, setInputQ] = useState(searchParams.get("q") || "");
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [filterOpen, setFilterOpen] = useState(false);

  const [allTags, setAllTags] = useState([]);
  const [savedViews, setSavedViews] = useState([]);
  const [saveViewName, setSaveViewName] = useState("");
  const [savingView, setSavingView] = useState(false);

  // allContacts holds the full unfiltered set from the server
  const [allContacts, setAllContacts] = useState([]);
  const [anyGated, setAnyGated] = useState(false);
  const [loading, setLoading] = useState(true);

  // Sync URL query param as user types
  useEffect(() => {
    const trimmed = inputQ.trim();
    setSearchParams(trimmed ? { q: trimmed } : {}, { replace: true });
  }, [inputQ, setSearchParams]);

  // Load all contacts + supporting data on mount
  useEffect(() => {
    api.get("/tags").then((r) => setAllTags(r.data)).catch(() => {});
    api.get("/saved-views").then((r) => setSavedViews(r.data)).catch(() => {});

    api.get("/contacts/search")
      .then(({ data }) => {
        setAllContacts(data.results || []);
        setAnyGated(data.gated || false);
      })
      .catch((e) => toast.error(formatApiError(e)))
      .finally(() => setLoading(false));
  }, []);

  // ─── Client-side filtering ─────────────────────────────────────────────────
  const displayedResults = useMemo(() => {
    const qLow = inputQ.trim().toLowerCase();
    return allContacts.filter((c) => {
      // Gated stubs have no real fields — always show them so the upgrade
      // prompt remains visible even when filters are active.
      if (c.gated) return true;

      // Text match across key fields
      if (
        qLow &&
        ![c.employer_name, c.position_applied, c.type_of_work, c.contact_method, c.result, c.employer_address]
          .some((v) => v && v.toLowerCase().includes(qLow))
      ) {
        return false;
      }

      // Facet filters
      if (filters.result && c.result !== filters.result) return false;
      if (filters.method && c.contact_method !== filters.method) return false;
      if (filters.type_of_work && c.type_of_work !== filters.type_of_work) return false;
      if (filters.tags.length && !filters.tags.some((tid) => (c.tags || []).includes(tid))) return false;

      // Date filters
      if (filters.date_mode === "single" && filters.date_single) {
        if (c.contact_date !== filters.date_single) return false;
      } else if (filters.date_mode === "range") {
        if (filters.date_from && c.contact_date < filters.date_from) return false;
        if (filters.date_to && c.contact_date > filters.date_to) return false;
      }

      return true;
    });
  }, [allContacts, inputQ, filters]);

  // ─── Facets computed from the full dataset (counts reflect total, not view) ─
  const facets = useMemo(() => {
    const result = {};
    const method = {};
    const type_of_work = {};
    const tags = {};
    allContacts.filter((c) => !c.gated).forEach((c) => {
      if (c.result) result[c.result] = (result[c.result] || 0) + 1;
      if (c.contact_method) method[c.contact_method] = (method[c.contact_method] || 0) + 1;
      if (c.type_of_work) type_of_work[c.type_of_work] = (type_of_work[c.type_of_work] || 0) + 1;
      (c.tags || []).forEach((tid) => { tags[tid] = (tags[tid] || 0) + 1; });
    });
    const toArr = (obj) =>
      Object.entries(obj)
        .map(([value, count]) => ({ value, count }))
        .sort((a, b) => b.count - a.count);
    const toTagArr = (obj) =>
      Object.entries(obj)
        .map(([id, count]) => ({ id, count }))
        .sort((a, b) => b.count - a.count);
    return {
      result: toArr(result),
      method: toArr(method),
      type_of_work: toArr(type_of_work),
      tags: toTagArr(tags),
    };
  }, [allContacts]);

  // ─── Filter handlers (no API call needed — useMemo reacts automatically) ───
  const applyFilter = useCallback((update) => {
    setFilters((prev) => ({ ...prev, ...update }));
  }, []);

  const clearFilters = useCallback(() => {
    setFilters(EMPTY_FILTERS);
  }, []);

  const loadView = useCallback((view) => {
    setFilters({ ...EMPTY_FILTERS, ...view.filters });
    setFilterOpen(false);
  }, []);

  const removeFilterChip = useCallback((key, value) => {
    setFilters((prev) => {
      if (key === "tags") return { ...prev, tags: prev.tags.filter((id) => id !== value) };
      if (key === "date") return { ...prev, date_mode: "none", date_single: "", date_from: "", date_to: "" };
      return { ...prev, [key]: "" };
    });
  }, []);

  // ─── Saved views ──────────────────────────────────────────────────────────
  const saveView = useCallback(async () => {
    const name = saveViewName.trim();
    if (!name) return;
    setSavingView(true);
    try {
      const { data: view } = await api.post("/saved-views", { name, filters });
      setSavedViews((prev) => [...prev, view].sort((a, b) => a.name.localeCompare(b.name)));
      setSaveViewName("");
      toast.success(`View "${name}" saved`);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setSavingView(false);
    }
  }, [saveViewName, filters]);

  const deleteView = useCallback(async (viewId) => {
    try {
      await api.delete(`/saved-views/${viewId}`);
      setSavedViews((prev) => prev.filter((v) => v.id !== viewId));
    } catch (e) {
      toast.error(formatApiError(e));
    }
  }, []);

  const filterCount = activeFilterCount(filters);
  const tagById = (id) => allTags.find((t) => t.id === id)?.name || id;
  const tagFacets = facets.tags.map((f) => ({
    ...f,
    name: allTags.find((t) => t.id === f.id)?.name || f.id,
  }));

  const visibleCount = displayedResults.filter((r) => !r.gated).length;
  const gatedCount = displayedResults.filter((r) => r.gated).length;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-display font-black text-2xl tracking-tight">All Contacts</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Search and browse your work-search contacts across all benefit weeks.
        </p>
      </div>

      {/* Search bar */}
      <form onSubmit={(e) => e.preventDefault()} className="flex items-center gap-2">
        <div className="relative flex-1">
          <MagnifyingGlassIcon
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            value={inputQ}
            onChange={(e) => setInputQ(e.target.value)}
            placeholder="Filter by employer, position, result…"
            className="pl-9 rounded-none"
          />
          {inputQ && (
            <button
              type="button"
              onClick={() => setInputQ("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <XIcon size={14} />
            </button>
          )}
        </div>

        {/* Filter popover */}
        <Popover open={filterOpen} onOpenChange={setFilterOpen}>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="outline"
              className={`rounded-none border-border relative ${
                filterCount > 0 ? "border-primary text-primary" : ""
              }`}
            >
              <FunnelIcon size={15} weight="bold" className="mr-2" />
              Filter
              {filterCount > 0 && (
                <span className="ml-2 bg-primary text-primary-foreground text-[10px] font-bold w-4 h-4 flex items-center justify-center">
                  {filterCount}
                </span>
              )}
              <CaretDownIcon size={12} className="ml-1" />
            </Button>
          </PopoverTrigger>
          <PopoverContent
            align="end"
            className="w-72 p-0 rounded-none border-border shadow-lg max-h-[80vh] overflow-y-auto"
          >
            {/* Saved views */}
            {savedViews.length > 0 && (
              <div className="border-b border-border pb-2">
                <div className="px-3 pt-3 pb-1 kbd-label">Saved Views</div>
                {savedViews.map((v) => (
                  <div key={v.id} className="flex items-center group">
                    <button
                      type="button"
                      onClick={() => loadView(v)}
                      className="flex-1 px-3 py-1.5 text-sm text-left hover:bg-secondary truncate"
                    >
                      {v.name}
                    </button>
                    <button
                      type="button"
                      onClick={() => deleteView(v.id)}
                      className="px-2 py-1.5 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <XIcon size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Result facets */}
            {facets.result.length > 0 && (
              <div className="border-b border-border pb-2">
                <div className="px-3 pt-3 pb-1 kbd-label">Result</div>
                {facets.result.map((f) => (
                  <FacetOption
                    key={f.value}
                    label={f.value}
                    count={f.count}
                    active={filters.result === f.value}
                    onClick={() =>
                      applyFilter({ result: filters.result === f.value ? "" : f.value })
                    }
                  />
                ))}
              </div>
            )}

            {/* Method facets */}
            {facets.method.length > 0 && (
              <div className="border-b border-border pb-2">
                <div className="px-3 pt-3 pb-1 kbd-label">Contact Method</div>
                {facets.method.map((f) => (
                  <FacetOption
                    key={f.value}
                    label={f.value}
                    count={f.count}
                    active={filters.method === f.value}
                    onClick={() =>
                      applyFilter({ method: filters.method === f.value ? "" : f.value })
                    }
                  />
                ))}
              </div>
            )}

            {/* Type of Work facets */}
            {facets.type_of_work.length > 0 && (
              <div className="border-b border-border pb-2">
                <div className="px-3 pt-3 pb-1 kbd-label">Type of Work</div>
                {facets.type_of_work.map((f) => (
                  <FacetOption
                    key={f.value}
                    label={f.value}
                    count={f.count}
                    active={filters.type_of_work === f.value}
                    onClick={() =>
                      applyFilter({
                        type_of_work: filters.type_of_work === f.value ? "" : f.value,
                      })
                    }
                  />
                ))}
              </div>
            )}

            {/* Tag facets */}
            {tagFacets.length > 0 && (
              <div className="border-b border-border pb-2">
                <div className="px-3 pt-3 pb-1 kbd-label">Tags</div>
                {tagFacets.map((f) => (
                  <FacetOption
                    key={f.id}
                    label={f.name}
                    count={f.count}
                    active={filters.tags.includes(f.id)}
                    onClick={() =>
                      applyFilter({
                        tags: filters.tags.includes(f.id)
                          ? filters.tags.filter((id) => id !== f.id)
                          : [...filters.tags, f.id],
                      })
                    }
                  />
                ))}
              </div>
            )}

            {/* Date filter */}
            <div className="border-b border-border pb-3">
              <div className="px-3 pt-3 pb-1 kbd-label">Date</div>
              <div className="flex px-3 gap-1 mb-2">
                {["none", "single", "range"].map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => applyFilter({ date_mode: mode })}
                    className={`text-xs px-2 py-1 border ${
                      filters.date_mode === mode
                        ? "border-primary bg-primary text-primary-foreground font-semibold"
                        : "border-border text-muted-foreground hover:bg-secondary"
                    }`}
                  >
                    {mode === "none" ? "Any" : mode === "single" ? "Date" : "Range"}
                  </button>
                ))}
              </div>
              {filters.date_mode === "single" && (
                <div className="px-3">
                  <input
                    type="date"
                    value={filters.date_single}
                    onChange={(e) => applyFilter({ date_single: e.target.value })}
                    className="w-full border border-border bg-background text-sm px-2 py-1"
                  />
                </div>
              )}
              {filters.date_mode === "range" && (
                <div className="px-3 space-y-1">
                  <input
                    type="date"
                    value={filters.date_from}
                    onChange={(e) => applyFilter({ date_from: e.target.value })}
                    className="w-full border border-border bg-background text-sm px-2 py-1"
                  />
                  <input
                    type="date"
                    value={filters.date_to}
                    onChange={(e) => applyFilter({ date_to: e.target.value })}
                    className="w-full border border-border bg-background text-sm px-2 py-1"
                  />
                </div>
              )}
            </div>

            {/* Save view */}
            <div className="border-b border-border p-3">
              <div className="kbd-label mb-2">Save Current Filters</div>
              <div className="flex gap-1">
                <input
                  type="text"
                  value={saveViewName}
                  onChange={(e) => setSaveViewName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && saveView()}
                  placeholder="View name…"
                  className="flex-1 min-w-0 border border-border bg-background text-sm px-2 py-1"
                  disabled={filterCount === 0}
                />
                <button
                  type="button"
                  onClick={saveView}
                  disabled={!saveViewName.trim() || filterCount === 0 || savingView}
                  className="border border-border px-2 py-1 hover:bg-secondary disabled:opacity-40"
                  title="Save view"
                >
                  <BookmarkSimpleIcon size={14} />
                </button>
              </div>
            </div>

            {filterCount > 0 && (
              <div className="p-2">
                <button
                  type="button"
                  onClick={() => { clearFilters(); setFilterOpen(false); }}
                  className="w-full text-xs text-muted-foreground hover:text-foreground py-1"
                >
                  Clear all filters
                </button>
              </div>
            )}
          </PopoverContent>
        </Popover>
      </form>

      {/* Active filter chips */}
      {filterCount > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {filters.result && (
            <TagChip name={`Result: ${filters.result}`} onRemove={() => removeFilterChip("result")} />
          )}
          {filters.method && (
            <TagChip name={`Method: ${filters.method}`} onRemove={() => removeFilterChip("method")} />
          )}
          {filters.type_of_work && (
            <TagChip
              name={`Type: ${filters.type_of_work}`}
              onRemove={() => removeFilterChip("type_of_work")}
            />
          )}
          {filters.tags.map((id) => (
            <TagChip
              key={id}
              name={`Tag: ${tagById(id)}`}
              onRemove={() => removeFilterChip("tags", id)}
            />
          ))}
          {filters.date_mode !== "none" && (
            <TagChip
              name={
                filters.date_mode === "single"
                  ? `Date: ${fmtDate(filters.date_single)}`
                  : `${fmtDate(filters.date_from) || "…"} – ${fmtDate(filters.date_to) || "…"}`
              }
              onRemove={() => removeFilterChip("date")}
            />
          )}
        </div>
      )}

      {/* Gated upgrade banner */}
      {anyGated && (
        <div className="border border-amber-400 bg-amber-50 dark:bg-amber-950/30 px-4 py-3 flex items-center gap-3 text-sm">
          <LockIcon size={16} className="text-amber-600 shrink-0" weight="bold" />
          <div className="flex-1">
            <span className="font-semibold text-amber-800 dark:text-amber-300">
              Some results are from other benefit weeks.
            </span>{" "}
            <span className="text-amber-700 dark:text-amber-400">
              Upgrade your plan to see contacts from all weeks.
            </span>
          </div>
          <Link
            to="/profile#subscription"
            className="shrink-0 bg-amber-500 hover:bg-amber-600 text-white text-xs font-bold px-3 py-1.5"
          >
            Upgrade
          </Link>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="border border-border p-12 text-center text-muted-foreground">
          <CircleNotchIcon size={24} className="animate-spin mx-auto mb-2 opacity-40" />
          <p className="text-sm">Loading contacts…</p>
        </div>
      )}

      {/* Empty states */}
      {!loading && allContacts.length === 0 && (
        <div className="border border-border p-12 text-center text-muted-foreground">
          <MagnifyingGlassIcon size={32} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">No contacts yet. Add your first work-search contact from a benefit week.</p>
        </div>
      )}

      {!loading && allContacts.length > 0 && displayedResults.length === 0 && (
        <div className="border border-border p-12 text-center text-muted-foreground">
          <p className="text-sm">No contacts match your search.</p>
        </div>
      )}

      {/* Results table */}
      {!loading && displayedResults.length > 0 && (
        <div className="border border-border overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-secondary">
                <th className="px-4 py-2 text-left font-semibold kbd-label">Date</th>
                <th className="px-4 py-2 text-left font-semibold kbd-label">Employer</th>
                <th className="px-4 py-2 text-left font-semibold kbd-label">Position / Type</th>
                <th className="px-4 py-2 text-left font-semibold kbd-label">Method</th>
                <th className="px-4 py-2 text-left font-semibold kbd-label">Result</th>
                <th className="px-4 py-2 text-left font-semibold kbd-label">Week</th>
              </tr>
            </thead>
            <tbody>
              {displayedResults.map((row) =>
                row.gated ? (
                  <GatedRow key={row.id} row={row} />
                ) : (
                  <tr
                    key={row.id}
                    onClick={() => navigate(`/weeks/${row.benefit_week_id}`)}
                    className="border-b border-border hover:bg-secondary cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-2.5 whitespace-nowrap">{fmtDate(row.contact_date)}</td>
                    <td className="px-4 py-2.5">
                      <div className="font-medium">{row.employer_name}</div>
                      {row.employer_address && (
                        <div className="text-xs text-muted-foreground">{row.employer_address}</div>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <div>{row.position_applied || row.type_of_work || "—"}</div>
                      {row.position_applied && row.type_of_work && (
                        <div className="text-xs text-muted-foreground">{row.type_of_work}</div>
                      )}
                      {(row.tags || []).length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {(row.tags || []).map((tid) => {
                            const tagName = allTags.find((t) => t.id === tid)?.name;
                            return tagName ? <TagChip key={tid} name={tagName} small /> : null;
                          })}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-2.5 whitespace-nowrap">{row.contact_method}</td>
                    <td className="px-4 py-2.5">{row.result || "—"}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap">
                      <div className="flex items-center gap-1 text-muted-foreground">
                        <span>{fmtDate(row.week_start)}–{fmtDate(row.week_end)}</span>
                        <ArrowRightIcon size={11} className="opacity-50" />
                      </div>
                    </td>
                  </tr>
                )
              )}
            </tbody>
          </table>
          <div className="px-4 py-2 border-t border-border text-xs text-muted-foreground">
            {visibleCount} contact{visibleCount !== 1 ? "s" : ""}
            {anyGated ? ` shown · ${gatedCount} gated` : ""}
            {allContacts.filter((c) => !c.gated).length !== visibleCount
              ? ` (filtered from ${allContacts.filter((c) => !c.gated).length})`
              : ""}
          </div>
        </div>
      )}
    </div>
  );
}
