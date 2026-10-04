import MiniSearch, { type SearchResult } from "minisearch";
import type { TenderDoc } from "./types";

/**
 * Local search (spec #72). Weighted fields:
 * tender number / reference > title > category > authority > location.
 */
function createIndex(): MiniSearch<TenderDoc> {
  return new MiniSearch<TenderDoc>({
    idField: "id",
    fields: ["tender_number", "ref", "title", "category", "authority", "state", "city"],
    storeFields: ["id"],
    searchOptions: {
      boost: { tender_number: 8, ref: 6, title: 3.5, category: 2, authority: 1.5 },
      prefix: true,
      // typo tolerance only for real words: numbers and short tokens must match exactly
      fuzzy: (term) => (term.length <= 3 || /\d/.test(term) ? false : 0.2),
      combineWith: "AND",
    },
    extractField: (doc, field) => {
      const v = String((doc as unknown as Record<string, unknown>)[field] ?? "");
      // "Dept › District › Office" and legacy "||" separators must tokenise as words
      return field === "authority" ? v.replace(/[|›]+/g, " ") : v;
    },
  });
}

export type TenderIndex = MiniSearch<TenderDoc>;

export function buildIndex(docs: TenderDoc[]): TenderIndex {
  const index = createIndex();
  index.addAll(docs);
  return index;
}

/**
 * Builds the index in small chunks that yield to the event loop between each,
 * so ~25k documents never block first paint or input. `cancelled` aborts early.
 */
export async function buildIndexAsync(
  docs: TenderDoc[],
  cancelled: () => boolean = () => false,
  chunkSize = 1000,
): Promise<TenderIndex | null> {
  const index = createIndex();
  for (let i = 0; i < docs.length; i += chunkSize) {
    if (cancelled()) return null;
    index.addAll(docs.slice(i, i + chunkSize));
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
  }
  return cancelled() ? null : index;
}

export interface SearchHit {
  doc: TenderDoc;
  score: number;
}

const norm = (s: string | null | undefined) => (s ?? "").trim().toLowerCase();

/** Docs whose id / reference / tender number equals the whole query (case-insensitive). */
export function exactMatches(docs: Iterable<TenderDoc>, query: string): TenderDoc[] {
  const q = norm(query);
  if (q.length < 3) return [];
  const out: TenderDoc[] = [];
  for (const d of docs) {
    if (norm(d.tender_number) === q || norm(d.ref) === q || norm(d.id) === q) out.push(d);
  }
  return out;
}

export function termCount(query: string): number {
  return query.split(/[\s/\\_-]+/).filter(Boolean).length;
}

/** Ranked hits for one combination mode. Exact id/ref/number matches always come first. */
export function searchHits(
  index: TenderIndex,
  docsById: Map<string, TenderDoc>,
  query: string,
  combineWith: "AND" | "OR" = "AND",
): SearchHit[] {
  if (!query.trim()) return [];
  const results: SearchResult[] = index.search(query, { combineWith });
  const hits: SearchHit[] = [];
  const seen = new Set<string>();
  const top = Math.max(1, results[0]?.score ?? 1);
  for (const d of exactMatches(docsById.values(), query)) {
    seen.add(d.id);
    hits.push({ doc: d, score: top * 10 });
  }
  for (const r of results) {
    const doc = docsById.get(r.id as string);
    if (!doc || seen.has(doc.id)) continue;
    hits.push({ doc, score: r.score });
  }
  return hits;
}

/** AND first; when that finds nothing, degrade to OR (ranked by score). */
export function searchDocs(
  index: TenderIndex,
  docsById: Map<string, TenderDoc>,
  query: string,
): SearchHit[] {
  const strict = searchHits(index, docsById, query, "AND");
  return strict.length > 0 ? strict : searchHits(index, docsById, query, "OR");
}

/** Cheap substring search used while the index is still being built. */
export function quickSearch(docs: TenderDoc[], query: string, limit = 50): TenderDoc[] {
  const terms = norm(query).split(/\s+/).filter(Boolean);
  if (terms.length === 0) return [];
  const out: TenderDoc[] = [];
  for (const d of docs) {
    const hay = `${d.title ?? ""} ${d.authority ?? ""} ${d.category ?? ""} ${d.ref ?? ""} ${d.tender_number ?? ""} ${d.id}`.toLowerCase();
    if (terms.every((t) => hay.includes(t))) {
      out.push(d);
      if (out.length >= limit) break;
    }
  }
  return out;
}
