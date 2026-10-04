import type { Filters } from "./filters";
import { applyFiltersRelaxed, passesStructure, sortDocs, valueVerdict } from "./filters";
import { parseQuery, type ParsedQuery } from "./nlq";
import { searchHits, termCount, type TenderIndex } from "./search";
import type { TenderDoc } from "./types";

/**
 * One pipeline for Discover and the command palette: MiniSearch relevance
 * (fuzzy + prefix, ranked) first, then structured filters on top.
 */

export interface QueryCtx {
  index: TenderIndex | null;
  byId: Map<string, TenderDoc>;
}

export interface QueryResult {
  docs: TenderDoc[];
  /** keyword AND was relaxed to OR (structured filters are never relaxed) */
  relaxed: boolean;
  /** rows excluded only because their value is not disclosed while a value filter is active */
  hiddenUnknownValue: number;
  /** false while the search index is still building (substring fallback used) */
  indexed: boolean;
}

export function runQuery(docs: TenderDoc[], f: Filters, ctx: QueryCtx, now = new Date()): QueryResult {
  const kw = f.keywords.trim();
  const finish = (ranked: TenderDoc[], relaxed: boolean, indexed: boolean): QueryResult => {
    const kept: TenderDoc[] = [];
    let hidden = 0;
    for (const d of ranked) {
      const v = valueVerdict(d, f);
      if (v === "ok") kept.push(d);
      else if (v === "unknown") hidden++;
    }
    // "relevance" keeps score order; other sorts reorder explicitly
    return { docs: sortDocs(kept, f.sort), relaxed, hiddenUnknownValue: hidden, indexed };
  };

  if (!kw) {
    return finish(
      docs.filter((d) => passesStructure(d, f, now)),
      false,
      ctx.index != null,
    );
  }

  if (!ctx.index) {
    // Index not ready yet: simple substring filter so results appear immediately.
    // applyFiltersRelaxed applies the value rule itself, so count hidden rows separately.
    const asIfUnknownIncluded = applyFiltersRelaxed(docs, { ...f, includeUnknownValue: true }, now);
    return finish(asIfUnknownIncluded.docs, asIfUnknownIncluded.relaxed, false);
  }

  const structured = (hits: { doc: TenderDoc }[]) =>
    hits.map((h) => h.doc).filter((d) => passesStructure(d, f, now));
  let ranked = structured(searchHits(ctx.index, ctx.byId, kw, "AND"));
  let relaxed = false;
  if (ranked.length === 0 && termCount(kw) >= 2) {
    ranked = structured(searchHits(ctx.index, ctx.byId, kw, "OR"));
    relaxed = ranked.length > 0;
  }
  return finish(ranked, relaxed, true);
}

/** Layer NLQ-parsed hints under explicit URL filters (explicit always wins). */
export function mergeParsed(f: Filters, parsed: ParsedQuery, knownSources?: ReadonlySet<string>): Filters {
  const hint = parsed.sourceHint && (!knownSources || knownSources.has(parsed.sourceHint)) ? parsed.sourceHint : undefined;
  return {
    ...f,
    keywords: parsed.keywords,
    state: f.state ?? parsed.state,
    category: f.category ?? parsed.category,
    minValue: f.minValue ?? parsed.minValue,
    maxValue: f.maxValue ?? parsed.maxValue,
    closingWithinDays: f.closingWithinDays ?? parsed.closingWithinDays,
    closingThisMonth: f.closingThisMonth || parsed.closingThisMonth === true,
    source: f.source ?? hint,
  };
}

/** Raw search text -> URL params (structured hints become real, visible filters). */
export function queryToParams(raw: string, base?: URLSearchParams, knownSources?: ReadonlySet<string>): URLSearchParams {
  const parsed = parseQuery(raw);
  const sp = new URLSearchParams(base);
  sp.delete("q");
  if (parsed.keywords) sp.set("q", parsed.keywords);
  if (parsed.state) sp.set("state", parsed.state);
  if (parsed.category) sp.set("category", parsed.category);
  if (parsed.minValue) sp.set("min", String(Math.round(parsed.minValue)));
  if (parsed.maxValue) sp.set("max", String(Math.round(parsed.maxValue)));
  if (parsed.closingWithinDays) sp.set("within", String(parsed.closingWithinDays));
  if (parsed.closingThisMonth) sp.set("month", "1");
  if (parsed.sourceHint && (!knownSources || knownSources.has(parsed.sourceHint))) sp.set("source", parsed.sourceHint);
  return sp;
}

