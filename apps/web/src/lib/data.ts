import type { TenderDoc } from "./types";

/**
 * Loads the generated dataset. Production: data/indexes/search-docs.json.gz
 * (decompressed in-browser). Development fallback: /data/dev-fixtures.json,
 * which contains clearly-labelled synthetic records (spec #98).
 */
export interface LoadedDataset {
  docs: TenderDoc[];
  fixture: boolean;
  generatedAt: string | null;
}

export async function loadDataset(): Promise<LoadedDataset> {
  try {
    const res = await fetch("/data/index/search-docs.json.gz");
    if (!res.ok) throw new Error(`dataset HTTP ${res.status}`);
    const buf = await res.arrayBuffer();
    const text = await gunzip(buf);
    const docs = JSON.parse(text) as TenderDoc[];
    return { docs, fixture: false, generatedAt: latest(docs) };
  } catch {
    const res = await fetch("/data/dev-fixtures.json");
    if (!res.ok)
      return { docs: [], fixture: false, generatedAt: null };
    const payload = (await res.json()) as { docs?: TenderDoc[]; generated_at?: string };
    return {
      docs: (payload.docs ?? []).map((d) => ({ ...d, _fixture: true })),
      fixture: true,
      generatedAt: payload.generated_at ?? null,
    };
  }
}

async function gunzip(buf: ArrayBuffer): Promise<string> {
  // DecompressionStream is available in all modern browsers.
  const stream = new Blob([buf]).stream().pipeThrough(new DecompressionStream("gzip"));
  return await new Response(stream).text();
}

function latest(docs: TenderDoc[]): string | null {
  let max: string | null = null;
  for (const d of docs) if (!max || d.first_seen_at > max) max = d.first_seen_at;
  return max;
}

// ---- derived selectors ------------------------------------------------------

export function uniqueValues(docs: TenderDoc[], key: "state" | "source" | "category"): string[] {
  // typed accessor keeps call sites simple
  const set = new Set<string>();
  for (const d of docs) {
    const v = d[key];
    if (v) set.add(v);
  }
  return [...set].sort();
}
