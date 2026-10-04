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

/** Resolves a public asset against Vite's base (e.g. "/opentender-india/" on GitHub Pages). */
export function assetUrl(path: string): string {
  return import.meta.env.BASE_URL + path.replace(/^\//, "");
}

export async function loadDataset(): Promise<LoadedDataset> {
  try {
    const res = await fetch(assetUrl("data/index/search-docs.json.gz"));
    if (!res.ok) throw new Error(`dataset HTTP ${res.status}`);
    const buf = await res.arrayBuffer();
    const text = await gunzip(buf);
    const docs = (JSON.parse(text) as TenderDoc[]).map(withCurrentStatus);
    return { docs, fixture: false, generatedAt: latest(docs) };
  } catch {
    const res = await fetch(assetUrl("data/dev-fixtures.json"));
    if (!res.ok)
      return { docs: [], fixture: false, generatedAt: null };
    const payload = (await res.json()) as { docs?: TenderDoc[]; generated_at?: string };
    // Fixture dates are relative to when the seed ran; shift them so the
    // committed file never goes stale (every deadline in the past).
    const shift = payload.generated_at ? Date.now() - Date.parse(payload.generated_at) : 0;
    return {
      docs: (payload.docs ?? []).map((d) => withCurrentStatus({ ...shiftDates(d, shift), _fixture: true })),
      fixture: true,
      generatedAt: payload.generated_at ? new Date(Date.parse(payload.generated_at) + shift).toISOString() : null,
    };
  }
}

const DATE_FIELDS = ["published_at", "closing_at", "opening_at", "pre_bid_meeting_at", "first_seen_at"] as const;

function shiftDates(d: TenderDoc, ms: number): TenderDoc {
  if (!ms) return d;
  const out = { ...d };
  for (const k of DATE_FIELDS) {
    const v = out[k];
    if (v) (out as Record<string, unknown>)[k] = new Date(Date.parse(v) + ms).toISOString();
  }
  return out;
}

/** Status is snapshotted at ingestion; a deadline that has since passed means closed. */
function withCurrentStatus(d: TenderDoc): TenderDoc {
  if (d.status === "active" && d.closing_at && Date.parse(d.closing_at) < Date.now())
    return { ...d, status: "closed" };
  return d;
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
