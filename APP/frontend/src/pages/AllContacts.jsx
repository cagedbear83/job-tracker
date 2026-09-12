import { useEffect, useState, useCallback, useRef } from "react";
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

function filtersToParams(q, filters) {
  const p = {};
  if (q && q.trim()) p.q = q.trim();
  if (filters.result) p.result = filters.result;
  if (filters.method) p.method = filters.method;
  if (filters.type_of_work) p.type_of_work = filters.type_of_work;
  if (filters.tags.length) p.tag = filters.tags[0]; // API takes one tag id
  if (filters.date_mode === "single" && filters.date_single) {
    p.date_from = filters.date_single;
    p.date_to = filters.date_single;
  } else if (filters.date_mode === "range") {
    if (filters.date_from) p.date_from = filters.date_from;
    if (filters.date_to) p.date_to = filters.date_to;
  }
  return p;
}

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
          {/* Blurred placeholder content */}
          <div className="flex items-center gap-4 px-4 py-3 select-none pointer-events-none opacity-40 blur-[3px]">
            <span className="text-sm w-24 bg-muted h-4 rounded" />
            <span className="text-sm w-36 bg-muted h-4 rounded" />
            <span className="text-sm w-20 bg-muted h-4 rounded" />
            <span className="text-sm w-28 bg-muted h-4 rounded" />
            <span className="text-sm w-16 bg-muted h-4 rounded" />
          </div>
          {/* Overlay */}
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

  const [q, setQ] = useState(searchParams.get("q") || "");
  const [inputQ, setInputQ] = useState(searchParams.get("q") || "");
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [filterOpen, setFilterOpen] = useState(false);

  const [allTags, setAllTags] = useState([]);
  const [savedViews, setSavedViews] = useState([]);
  const [saveViewName, setSaveViewName] = useState("");
  const [savingView, setSavingView] = useState(false);

  const [results, setResults] = useState([]);
  const [facets, setFacets] = useState({ result: [], method: [], type_of_work: [], tags: [] });
  const [anyGated, setAnyGated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  // Load tags + saved views on mount
  useEffect(() => {
    api.get("/tags").then((r) => r.json()).then(setAllTags).catch(() => {});
    api.get("/saved-views").then((r) => r.json()).then(setSavedViews).catch(() => {});

    // If there was a ?q= param, run the search immediately
    const initQ = searchParams.get("q") || "";
    if (initQ.trim()) {
      runSearch(initQ, EMPTY_FILTERS);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const runSearch = useCallback(async (searchQ, searchFilters) => {
    setLoading(true);
    setSearched(true);
    try {
      const params = filtersToParams(searchQ, searchFilters);
      const qs = new URLSearchParams(params).toString();
      const res = await api.get(`/contacts/search${qs ? `?${qs}` : ""}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setResults(data.results || []);
      setFacets(data.facets || { result: [], method: [], type_of_work: [], tags: [] });
      setAnyGated(data.gated || false);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSearch = useCallback(
    (e) => {
      e?.preventDefault();
      const trimmed = inputQ.trim();
      setQ(trimmed);
      setSearchParams(trimmed ? { q: trimmed } : {}, { replace: true });
      runSearch(trimmed, filters);
    },
    [inputQ, filters, runSearch, setSearchParams]
  );

  // Re-run when filters change (if we've already searched)
  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const searchedRef = useRef(searched);
  searchedRef.current = searched;

  const applyFilter = useCallback(
    (update) => {
      setFilters((prev) => {
        const next = { ...prev, ...update };
        if (searchedRef.current) {
          runSearch(q, next);
        }
        return next;
      });
    },
    [q, runSearch]
  );

  const clearFilters = useCallback(() => {
    setFilters(EMPTY_FILTERS);
    if (searched) runSearch(q, EMPTY_FILTERS);
  }, [q, runSearch, searched]);

  // Saved view ops
  const loadView = useCallback(
    (view) => {
      const f = { ...EMPTY_FILTERS, ...view.filters };
      setFilters(f);
      setFilterOpen(false);
      if (searched || q) runSearch(q, f);
    },
    [q, runSearch, searched]
  );

  const saveView = useCallback(async () => {
    const name = saveViewName.trim();
    if (!name) return;
    setSavingView(true);
    try {
      const res = await api.post("/saved-views", { name, filters });
      if (!res.ok) throw new Error(await res.text());
      const view = await res.json();
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

  // Active filter chip helpers
  const removeFilterChip = useCallback(
    (key, value) => {
      setFilters((prev) => {
        let next = { ...prev };
        if (key === "tags") {
          next.tags = prev.tags.filter((id) => id !== value);
        } else if (key === "date") {
          next = { ...next, date_mode: "none", date_single: "", date_from: "", date_to: "" };
        } else {
          next[key] = "";
        }
        if (searchedRef.current) runSearch(q, next);
        return next;
      });
    },
    [q, runSearch]
  );

  const filterCount = activeFilterCount(filters);

  // Tag name lookup
  const tagById = (id) => allTags.find((t) => t.id === id)?.name || id;

  // Resolve tag names in facets
  const tagFacets = (facets.tags || []).map((f) => ({
    ...f,
    name: allTags.find((t) => t.id === f.id)?.name || f.id,
  }));

  return (
    <div className="space-y-4">
      {/* Page header */}
      <div>
        <h1 className="font-display font-black text-2xl tracking-tight">All Contacts</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Search and browse your work-search contacts across all benefit weeks.
        </p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="flex items-center gap-2">
        <div className="relative flex-1">
          <MagnifyingGlassIcon
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            value={inputQ}
            onChange={(e) => setInputQ(e.target.value)}
            placeholder="Search employer, position, result, notes…"
            className="pl-9 rounded-none"
          />
        </div>
        <Button type="submit" className="rounded-none" disabled={loading}>
          {loading ? <CircleNotchIcon size={15} className="animate-spin" /> : "Search"}
        </Button>

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
            {(facets.result || []).length > 0 && (
              <div className="border-b border-border pb-2">
                <div className="px-3 pt-3 pb-1 kbd-label">Result</div>
                {(facets.result || []).map((f) => (
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
            {(facets.method || []).length > 0 && (
              <div className="border-b border-border pb-2">
                <div className="px-3 pt-3 pb-1 kbd-label">Contact Method</div>
                {(facets.method || []).map((f) => (
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
            {(facets.type_of_work || []).length > 0 && (
              <div className="border-b border-border pb-2">
                <div className="px-3 pt-3 pb-1 kbd-label">Type of Work</div>
                {(facets.type_of_work || []).map((f) => (
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
                    placeholder="From"
                  />
                  <input
                    type="date"
                    value={filters.date_to}
                    onChange={(e) => applyFilter({ date_to: e.target.value })}
                    className="w-full border border-border bg-background text-sm px-2 py-1"
                    placeholder="To"
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

            {/* Clear */}
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

      {/* Results table */}
      {!searched && !loading && (
        <div className="border border-border p-12 text-center text-muted-foreground">
          <MagnifyingGlassIcon size={32} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Enter a keyword or apply filters to search your contacts.</p>
        </div>
      )}

      {searched && !loading && results.length === 0 && (
        <div className="border border-border p-12 text-center text-muted-foreground">
          <p className="text-sm">No contacts matched your search.</p>
        </div>
      )}

      {loading && (
        <div className="border border-border p-12 text-center text-muted-foreground">
          <CircleNotchIcon size={24} className="animate-spin mx-auto mb-2 opacity-40" />
          <p className="text-sm">Searching…</p>
        </div>
      )}

      {!loading && results.length > 0 && (
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
              {results.map((row) =>
                row.gated ? (
                  <GatedRow key={row.id} row={row} />
                ) : (
                  <tr
                    key={row.id}
                    onClick={() => navigate(`/weeks/${row.benefit_week_id}`)}
                    className="border-b border-border hover:bg-secondary cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-2.5 whitespace-nowrap">
                      {fmtDate(row.contact_date)}
                    </td>
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
                            return tagName ? (
                              <TagChip key={tid} name={tagName} small />
                            ) : null;
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
            {results.filter((r) => !r.gated).length} contact
            {results.filter((r) => !r.gated).length !== 1 ? "s" : ""}
            {anyGated ? ` shown · ${results.filter((r) => r.gated).length} gated` : ""}
          </div>
        </div>
      )}
    </div>
  );
}
