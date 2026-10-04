import { stateKey, type ParsedQuery } from "./nlq";
import { istMonthEnd } from "./format";
import type { TenderDoc } from "./types";

/**
 * URL-encoded filter state (spec #57). Every filter is a query param so
 * searches are shareable and back-button safe.
 */

export interface Filters extends ParsedQuery {
  status?: string;
  source?: string;
  sort?: "relevance" | "closing" | "value" | "newest";
  /** include tenders whose value is not disclosed even when a value filter is active */
  includeUnknownValue?: boolean;
}

export function filtersFromSearchParams(sp: URLSearchParams): Filters {
  const f: Filters = { keywords: sp.get("q") ?? "" };
  if (sp.get("state")) f.state = sp.get("state")!;
  if (sp.get("category")) f.category = sp.get("category")!;
  const min = parseFloatSafe(sp.get("min"));
  if (min != null) f.minValue = min;
  const max = parseFloatSafe(sp.get("max"));
  if (max != null) f.maxValue = max;
  const days = parseIntSafe(sp.get("within"));
  if (days != null) f.closingWithinDays = days;
  if (sp.get("month") === "1") f.closingThisMonth = true;
  if (sp.get("source")) f.source = sp.get("source")!;
  if (sp.get("status")) f.status = sp.get("status")!;
  if (sp.get("unknown") === "1") f.includeUnknownValue = true;
  if (sp.get("sort")) f.sort = sp.get("sort") as Filters["sort"];
  return f;
}

export function filtersToSearchParams(f: Filters): URLSearchParams {
  const sp = new URLSearchParams();
  if (f.keywords) sp.set("q", f.keywords);
  if (f.state) sp.set("state", f.state);
  if (f.category) sp.set("category", f.category);
  if (f.minValue) sp.set("min", String(Math.round(f.minValue)));
  if (f.maxValue) sp.set("max", String(Math.round(f.maxValue)));
  if (f.closingWithinDays) sp.set("within", String(f.closingWithinDays));
  if (f.closingThisMonth) sp.set("month", "1");
  if (f.source) sp.set("source", f.source);
  if (f.status) sp.set("status", f.status);
  if (f.includeUnknownValue) sp.set("unknown", "1");
  if (f.sort && f.sort !== "relevance") sp.set("sort", f.sort);
  return sp;
}

// ---- deterministic filtering + ranking --------------------------------------

export function valueFilterActive(f: Filters): boolean {
  return f.minValue != null || f.maxValue != null;
}

/**
 * Value filter verdict. A missing value is UNKNOWN, never zero (spec #31):
 * with an active value filter unknown rows are excluded unless the user opts
 * in, and callers surface how many were hidden.
 */
export function valueVerdict(d: TenderDoc, f: Filters): "ok" | "fail" | "unknown" {
  if (!valueFilterActive(f)) return "ok";
  if (d.value == null) return f.includeUnknownValue ? "ok" : "unknown";
  if (f.minValue != null && d.value < f.minValue) return "fail";
  if (f.maxValue != null && d.value > f.maxValue) return "fail";
  return "ok";
}

/** Every structured (non-keyword, non-value) filter. Shared by strict and relaxed paths. */
export function passesStructure(d: TenderDoc, f: Filters, now = new Date()): boolean {
  if (f.state && stateKey(d.state) !== stateKey(f.state)) return false;
  if (f.source && d.source !== f.source) return false;
  if (f.status && d.status !== f.status) return false;
  if (f.category && !(d.category ?? "").toLowerCase().includes(f.category.toLowerCase())) return false;
  const closing = d.closing_at ? new Date(d.closing_at).getTime() : null;
  if (f.closingWithinDays != null) {
    if (closing == null || Number.isNaN(closing)) return false;
    const horizon = now.getTime() + f.closingWithinDays * 86_400_000;
    if (closing < now.getTime() || closing > horizon) return false;
  }
  if (f.closingThisMonth) {
    if (closing == null || Number.isNaN(closing)) return false;
    if (closing < now.getTime() || closing > istMonthEnd(now)) return false;
  }
  return true;
}

function haystack(d: TenderDoc): string {
  return `${d.title ?? ""} ${d.authority ?? ""} ${d.category ?? ""} ${d.ref ?? ""} ${d.tender_number ?? ""} ${d.id}`.toLowerCase();
}

/** Plain substring filtering (used until the search index is ready). */
export function applyFilters(docs: TenderDoc[], f: Filters, now = new Date()): TenderDoc[] {
  const kw = f.keywords.toLowerCase().split(/\s+/).filter(Boolean);
  return docs.filter((d) => {
    if (!passesStructure(d, f, now)) return false;
    if (valueVerdict(d, f) !== "ok") return false;
    const hay = haystack(d);
    return kw.every((term) => hay.includes(term));
  });
}

/**
 * Strict AND filtering; when it would return zero results for multi-term
 * queries, degrade gracefully to ranked OR (matched-terms count desc). Only the
 * keyword AND is relaxed: every structured filter stays in force.
 */
export function applyFiltersRelaxed(
  docs: TenderDoc[],
  f: Filters,
  now = new Date(),
): { docs: TenderDoc[]; relaxed: boolean } {
  const strict = applyFilters(docs, f, now);
  const kw = f.keywords.toLowerCase().split(/\s+/).filter((t) => t.length > 1);
  if (strict.length > 0 || kw.length < 2) {
    return { docs: strict, relaxed: false };
  }
  const scored = docs
    .map((d) => {
      const hay = haystack(d);
      let hits = 0;
      for (const t of kw) if (hay.includes(t)) hits++;
      return { d, hits };
    })
    .filter((x) => x.hits > 0 && passesStructure(x.d, f, now) && valueVerdict(x.d, f) === "ok")
    .sort((a, b) => b.hits - a.hits)
    .map((x) => x.d);
  return { docs: scored, relaxed: scored.length > 0 };
}

export function sortDocs(docs: TenderDoc[], sort: Filters["sort"]): TenderDoc[] {
  const arr = [...docs];
  switch (sort) {
    case "closing":
      return arr.sort(
        (a, b) => ts(a.closing_at, Infinity) - ts(b.closing_at, Infinity),
      );
    case "value":
      return arr.sort((a, b) => (b.value ?? -1) - (a.value ?? -1));
    case "newest":
      return arr.sort((a, b) => ts(b.published_at, 0) - ts(a.published_at, 0));
    default:
      return arr;
  }
}

function ts(v: string | null, fallback: number): number {
  if (!v) return fallback;
  const t = new Date(v).getTime();
  return Number.isNaN(t) ? fallback : t;
}

function parseFloatSafe(s: string | null): number | undefined {
  if (!s) return undefined;
  const n = Number(s);
  return Number.isFinite(n) ? n : undefined;
}

function parseIntSafe(s: string | null): number | undefined {
  if (!s) return undefined;
  const n = parseInt(s, 10);
  return Number.isFinite(n) ? n : undefined;
}
