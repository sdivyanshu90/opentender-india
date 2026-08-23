import MiniSearch, { type SearchResult } from "minisearch";
import type { TenderDoc } from "./types";

/**
 * Local search (spec #72). Weighted fields:
 * tender number / reference > title > category > authority > location.
 */
export function buildIndex(docs: TenderDoc[]): MiniSearch<TenderDoc> {
  const index = new MiniSearch<TenderDoc>({
    idField: "id",
    fields: ["tender_number", "ref", "title", "category", "authority", "state", "city"],
    storeFields: ["id"],
    searchOptions: {
      boost: { tender_number: 8, ref: 6, title: 3.5, category: 2, authority: 1.5 },
      prefix: true,
      fuzzy: 0.2,
      combineWith: "AND",
    },
    extractField: (doc, field) =>
      String((doc as unknown as Record<string, unknown>)[field] ?? ""),
  });
  index.addAll(docs);
  return index;
}

export interface SearchHit {
  doc: TenderDoc;
  score: number;
}

export function searchDocs(
  index: MiniSearch<TenderDoc>,
  docsById: Map<string, TenderDoc>,
  query: string,
): SearchHit[] {
  if (!query.trim()) return [];
  let results: SearchResult[] = index.search(query);
  if (results.length === 0) results = index.search(query, { combineWith: "OR" });
  return results.map((r) => ({ doc: docsById.get(r.id as string)!, score: r.score }));
}
