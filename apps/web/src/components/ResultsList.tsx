import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useData } from "../App";
import { filtersFromSearchParams, filtersToSearchParams, valueFilterActive, type Filters } from "../lib/filters";
import { parseQuery, stateKey } from "../lib/nlq";
import { mergeParsed, queryToParams, runQuery } from "../lib/query";
import { uniqueValues } from "../lib/data";
import { isRecentlyDiscovered, istDateKey } from "../lib/format";
import { matchTender } from "../lib/match";
import FilterBar from "./FilterBar";
import { TenderCard, TenderRow } from "./TenderViews";
import { EmptyState, SkeletonRows } from "./Badges";
import { addSavedSearch, updateWorkspace, useWorkspace } from "../lib/store";
import { buildTendersCsv, buildTendersJson, downloadBlob } from "../lib/export";
import { copyText, discoverUrl } from "../lib/share";
import type { TenderDoc } from "../lib/types";
import { toggleCompare as toggleCompareSel, useCompareIds } from "../lib/compare";

const PAGE = 100;

export type ResultsMode = "all" | "new" | "closing" | "changed";

export default function ResultsList({ mode = "all" }: { mode?: ResultsMode }) {
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const compareIds = useCompareIds();
  const { docs, index, byId, loading, error } = useData();
  const ws = useWorkspace();
  const [limit, setLimit] = useState(PAGE);

  const sources = useMemo(() => new Set(uniqueValues(docs, "source")), [docs]);

  const filters = useMemo(() => {
    const f = filtersFromSearchParams(sp);
    // NLQ pre-interpretation (spec #14): structured filters win; keywords parsed
    return mergeParsed(f, parseQuery(f.keywords ?? ""), sources) as Filters;
  }, [sp, sources]);

  // /new and /changed are real filters over the dataset, not just labels.
  const scoped = useMemo(() => {
    if (mode === "new") return docs.filter((d) => isRecentlyDiscovered(d.first_seen_at));
    if (mode === "changed") return docs.filter((d) => d.corrigenda_count > 0);
    return docs;
  }, [docs, mode]);

  const { results, relaxed, hiddenUnknownValue, indexed } = useMemo(() => {
    const r = runQuery(scoped, filters, { index, byId });
    return { results: r.docs, relaxed: r.relaxed, hiddenUnknownValue: r.hiddenUnknownValue, indexed: r.indexed };
  }, [scoped, filters, index, byId]);

  const stateKnown = useMemo(() => {
    const keys = new Set(docs.map((d) => stateKey(d.state)).filter(Boolean));
    return { any: keys.size > 0, has: (s: string) => keys.has(stateKey(s)) };
  }, [docs]);

  useEffect(() => setLimit(PAGE), [results]);

  const profileMatches = useMemo(() => {
    if (!ws.profile) return new Map<string, ReturnType<typeof matchTender>>();
    return new Map(results.slice(0, limit).map((d) => [d.id, matchTender(d, ws.profile)]));
  }, [results, ws.profile, limit]);

  if (loading) return <SkeletonRows />;

  const isFresh = (doc: (typeof results)[number]) => isRecentlyDiscovered(doc.first_seen_at);
  const visible = results.slice(0, limit);

  const toggleBookmark = (id: string) =>
    updateWorkspace((cur) => {
      const bookmarks = { ...cur.bookmarks };
      if (bookmarks[id]) delete bookmarks[id];
      else bookmarks[id] = { at: Date.now(), status: "new", notes: "" };
      return { ...cur, bookmarks };
    });

  const setUnknown = (include: boolean) =>
    navigate(`?${filtersToSearchParams({ ...filters, includeUnknownValue: include }).toString()}`);

  return (
    <div className="space-y-4">
      <SearchBox
        value={filters.keywords}
        onSubmit={(raw) => navigate(`?${queryToParams(raw, sp, sources).toString()}`)}
      />
      <FilterBar
        filters={filters}
        onChange={(next: Filters) => {
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
          {filters.keywords && !indexed && (
            <span className="ml-2 text-xs text-ink-400">· search index still loading, showing basic matches</span>
          )}
        </p>
        <div className="flex items-center gap-2 text-xs">
          <SortSelect value={filters.sort} onChange={(sort) => navigate(`?${withParam(sp, "sort", sort ?? "")}`)} />
          <ViewToggle />
        </div>
      </div>

      <ResultsActions params={sp.toString()} keywords={filters.keywords} results={results} />

      {valueFilterActive(filters) && (hiddenUnknownValue > 0 || filters.includeUnknownValue) && (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800" data-testid="unknown-value-note">
          {filters.includeUnknownValue ? (
            <>
              Including tenders whose value is not disclosed (their value is unknown, not zero).{" "}
              <button className="font-medium underline" onClick={() => setUnknown(false)}>
                Hide them
              </button>
            </>
          ) : (
            <>
              {hiddenUnknownValue} {hiddenUnknownValue === 1 ? "tender" : "tenders"} hidden: value not disclosed.{" "}
              <button className="font-medium underline" onClick={() => setUnknown(true)}>
                Include them
              </button>
            </>
          )}
        </p>
      )}

      {results.length === 0 ? (
        <NoResults
          error={error}
          datasetEmpty={docs.length === 0}
          scopedEmpty={scoped.length === 0}
          mode={mode}
          state={filters.state}
          stateKnown={filters.state ? stateKnown.has(filters.state) : true}
          anyState={stateKnown.any}
        />
      ) : ws.prefs.view === "cards" ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 [&>*]:min-w-0">
          {visible.map((doc) => (
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
              {visible.map((doc) => (
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
      {results.length > visible.length && (
        <div className="pt-2 text-center">
          <p className="text-xs text-ink-400">
            Showing {visible.length} of {results.length}. Refine filters to narrow down.
          </p>
          <button className="btn mt-2" onClick={() => setLimit((n) => n + PAGE)}>
            Show more
          </button>
        </div>
      )}
    </div>
  );
}

/** Save search / share link / export of the CURRENT result set (spec #21, #23). */
function ResultsActions({ params, keywords, results }: { params: string; keywords: string; results: TenderDoc[] }) {
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const flash = (t: string) => {
    setNote(t);
    setTimeout(() => setNote(null), 2000);
  };
  const stamp = istDateKey(new Date()) ?? "export";

  const save = () => {
    addSavedSearch(name || keywords || "Untitled search", params);
    setNaming(false);
    setName("");
    flash("Search saved");
  };

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      {naming ? (
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            save();
          }}
        >
          <input
            autoFocus
            aria-label="Saved search name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={keywords || "Name this search"}
            maxLength={200}
            className="input !py-1"
          />
          <button type="submit" className="btn btn-primary !py-1">
            Save
          </button>
          <button type="button" className="btn !py-1" onClick={() => setNaming(false)}>
            Cancel
          </button>
        </form>
      ) : (
        <button className="btn !py-1" disabled={!params} onClick={() => setNaming(true)}>
          Save this search
        </button>
      )}
      <button
        className="btn !py-1"
        onClick={async () => flash((await copyText(discoverUrl(params))) ? "Link copied" : "Copy failed — copy the address bar instead")}
      >
        Copy share link
      </button>
      <button
        className="btn !py-1"
        disabled={results.length === 0}
        onClick={() => downloadBlob(buildTendersCsv(results), `opentender-results-${stamp}.csv`)}
      >
        Export CSV
      </button>
      <button
        className="btn !py-1"
        disabled={results.length === 0}
        onClick={() => downloadBlob(buildTendersJson(results), `opentender-results-${stamp}.json`)}
      >
        Export JSON
      </button>
      {note && (
        <span aria-live="polite" className="text-emerald-700">
          {note}
        </span>
      )}
    </div>
  );
}

function SearchBox({ value, onSubmit }: { value: string; onSubmit: (raw: string) => void }) {
  const [text, setText] = useState(value);
  useEffect(() => setText(value), [value]);
  return (
    <form
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(text.trim());
      }}
      className="flex gap-2"
    >
      <input
        type="search"
        aria-label="Search tenders"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Search by keyword, tender number or ask e.g. “road repair Kerala under 50 lakh”"
        className="input w-full"
      />
      <button type="submit" className="btn btn-primary">
        Search
      </button>
    </form>
  );
}

function NoResults({
  error,
  datasetEmpty,
  scopedEmpty,
  mode,
  state,
  stateKnown,
  anyState,
}: {
  error: string | null;
  datasetEmpty: boolean;
  scopedEmpty: boolean;
  mode: ResultsMode;
  state?: string;
  stateKnown: boolean;
  anyState: boolean;
}) {
  if (error) return <EmptyState title="Tender data could not be loaded" hint={error} />;
  if (datasetEmpty) return <EmptyState title="No tender dataset published yet" hint="The daily ingestion has not produced data for this site yet." />;
  if (state && !stateKnown) {
    return (
      <EmptyState
        title={`No tenders from ${state} in this dataset`}
        hint={
          anyState
            ? `None of the tenders collected so far are tagged to ${state}. Coverage depends on which portals are connected — see Sources.`
            : `State information is not available in the current dataset, so state filters cannot match anything yet.`
        }
      />
    );
  }
  if (mode === "changed" && scopedEmpty)
    return <EmptyState title="No corrigenda detected" hint="No tender in the dataset has a recorded corrigendum or revision yet." />;
  if (mode === "new" && scopedEmpty)
    return <EmptyState title="Nothing new in the last 48 hours" hint="No tender was first discovered recently. Check Sources for portal status." />;
  return (
    <EmptyState
      title="No tenders match these filters"
      hint="Try widening the value range or deadline window. Coverage depends on connected sources."
    />
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
          aria-label={v === "table" ? "Table view" : "Card view"}
          title={v === "table" ? "Table view" : "Card view"}
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
