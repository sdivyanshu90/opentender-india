import { useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useData } from "../App";
import { filtersFromSearchParams, filtersToSearchParams, applyFiltersRelaxed, sortDocs, type Filters } from "../lib/filters";
import { parseQuery } from "../lib/nlq";
import { matchTender } from "../lib/match";
import FilterBar from "./FilterBar";
import { TenderCard, TenderRow } from "./TenderViews";
import { EmptyState, SkeletonRows } from "./Badges";
import { updateWorkspace, useWorkspace } from "../lib/store";
import { toggleCompare as toggleCompareSel, useCompareIds } from "../lib/compare";

export default function ResultsList() {
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const compareIds = useCompareIds();
  const { docs, loading } = useData();
  const ws = useWorkspace();

  const filters = useMemo(() => {
    const f = filtersFromSearchParams(sp);
    // NLQ pre-interpretation (spec #14): structured filters win; keywords parsed
    const parsed = parseQuery(f.keywords ?? "");
    return {
      ...f,
      keywords: parsed.keywords,
      state: f.state ?? parsed.state,
      minValue: f.minValue ?? parsed.minValue,
      closingWithinDays: f.closingWithinDays ?? parsed.closingWithinDays,
      closingThisMonth: f.closingThisMonth || parsed.closingThisMonth === true,
    } as Filters;
  }, [sp]);

  const { results, relaxed } = useMemo(() => {
    const r = applyFiltersRelaxed(docs, filters);
    return { results: sortDocs(r.docs, filters.sort), relaxed: r.relaxed };
  }, [docs, filters]);

  const profileMatches = useMemo(() => {
    if (!ws.profile) return new Map<string, ReturnType<typeof matchTender>>();
    return new Map(results.slice(0, 200).map((d) => [d.id, matchTender(d, ws.profile)]));
  }, [results, ws.profile]);

  if (loading) return <SkeletonRows />;

  const todayStr = new Date().toISOString().slice(0, 10);
  const isFresh = (doc: (typeof results)[number]) => doc.first_seen_at?.slice(0, 10) === todayStr;

  const toggleBookmark = (id: string) =>
    updateWorkspace((cur) => {
      const bookmarks = { ...cur.bookmarks };
      if (bookmarks[id]) delete bookmarks[id];
      else bookmarks[id] = { at: Date.now(), status: "new", notes: "" };
      return { ...cur, bookmarks };
    });

  return (
    <div className="space-y-4">
      <FilterBar
        filters={filters}
        onChange={(next: Filters) => {
          const sp = filtersToSearchParams(next);
          void sp;
          navigate(`?${filtersToSearchParams(next).toString()}`);
        }}
      />
      <div className="flex items-center justify-between">
        <p className="text-sm text-ink-500" role="status">
          <b className="text-ink-800">{results.length}</b> tenders
          {filters.keywords ? <> for “{filters.keywords}”</> : ""}
          {relaxed && (
            <span className="ml-2 text-xs text-accent-600" title="No exact match for all words — showing closest matches">
              · closest matches (no exact result for all words)
            </span>
          )}
        </p>
        <div className="flex items-center gap-2 text-xs">
          <SortSelect value={filters.sort} onChange={(sort) => navigate(`?${withParam(sp, "sort", sort ?? "")}`)} />
          <ViewToggle />
        </div>
      </div>

      {results.length === 0 ? (
        <EmptyState
          title="No tenders match these filters"
          hint="Try widening the value range or deadline window. Coverage depends on connected sources."
        />
      ) : ws.prefs.view === "cards" ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 [&>*]:min-w-0">
          {results.slice(0, 100).map((doc) => (
            <TenderCard
              key={doc.id}
              doc={doc}
              isNew={isFresh(doc)}
              bookmarked={!!ws.bookmarks[doc.id]}
              match={profileMatches.get(doc.id)}
              onToggleBookmark={() => toggleBookmark(doc.id)}
            />
          ))}
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse">
            <thead>
              <tr>
                <th className="table-header w-8"></th>
                <th className="table-header">Tender</th>
                <th className="table-header hidden md:table-cell">Location</th>
                <th className="table-header text-right">Value</th>
                <th className="table-header">Deadline</th>
                <th className="table-header hidden lg:table-cell">Match</th>
                <th className="table-header hidden md:table-cell">Status</th>
                <th className="table-header hidden xl:table-cell">Source</th>
                <th className="table-header"></th>
              </tr>
            </thead>
            <tbody>
              {results.slice(0, 200).map((doc) => (
                <TenderRow
                  key={doc.id}
                  doc={doc}
                  isNew={isFresh(doc)}
                  bookmarked={!!ws.bookmarks[doc.id]}
                  selected={compareIds.includes(doc.id)}
                  match={profileMatches.get(doc.id)}
                  onToggleBookmark={() => toggleBookmark(doc.id)}
                  onToggleCompare={() => toggleCompareSel(doc.id)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
      {results.length > 200 && (
        <p className="pt-2 text-center text-xs text-ink-400">
          Showing first 200 of {results.length}. Refine filters to narrow down.
        </p>
      )}
    </div>
  );
}

function SortSelect({ value, onChange }: { value: Filters["sort"]; onChange: (v: Filters["sort"]) => void }) {
  return (
    <select aria-label="Sort" value={value ?? "relevance"} onChange={(e) => onChange(e.target.value as Filters["sort"])} className="input !py-1.5">
      <option value="relevance">Relevance</option>
      <option value="closing">Closing soon</option>
      <option value="value">Highest value</option>
      <option value="newest">Newest</option>
    </select>
  );
}

function ViewToggle() {
  const ws = useWorkspace();
  return (
    <div className="flex overflow-hidden rounded-md border border-ink-200" role="group" aria-label="View mode">
      {(["table", "cards"] as const).map((v) => (
        <button
          key={v}
          onClick={() => updateWorkspace((cur) => ({ ...cur, prefs: { ...cur.prefs, view: v } }))}
          className={`px-2 py-1 ${ws.prefs.view === v ? "bg-accent-600 text-white" : "bg-white text-ink-500 hover:bg-ink-50"}`}
          aria-pressed={ws.prefs.view === v}
        >
          {v === "table" ? "▤" : "▣"}
        </button>
      ))}
    </div>
  );
}

function withParam(sp: URLSearchParams, key: string, value: string): URLSearchParams {
  const next = new URLSearchParams(sp);
  if (value) next.set(key, value);
  else next.delete(key);
  return next;
}

