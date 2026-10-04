import { useEffect, useState } from "react";
import { assetUrl, decodeBody } from "./data";
import type { TenderDoc } from "./types";

/**
 * Heavy per-tender fields are not in the search index; they are sharded under
 * data/details/<first 2 id chars, lowercase>.json.gz as { id: TenderDetails }.
 */
export type TenderDetails = Pick<
  TenderDoc,
  "documents" | "ai" | "award" | "portal" | "fee" | "pre_bid_meeting_at" | "city" | "opening_at" | "last_seen_at"
>;

export function shardKey(id: string): string {
  return id.slice(0, 2).toLowerCase();
}

/** Detail fields fill gaps only; anything already on the doc (e.g. fixtures) wins. */
export function mergeDetails(doc: TenderDoc, details: Partial<TenderDetails> | null | undefined): TenderDoc {
  if (!details) return doc;
  const out: TenderDoc = { ...doc };
  const rec = out as unknown as Record<string, unknown>;
  for (const [k, v] of Object.entries(details)) {
    if (v !== undefined && rec[k] === undefined) rec[k] = v;
  }
  return out;
}

const shards = new Map<string, Promise<Record<string, TenderDetails> | null>>();

function loadShard(key: string): Promise<Record<string, TenderDetails> | null> {
  let p = shards.get(key);
  if (!p) {
    p = (async () => {
      try {
        const res = await fetch(assetUrl(`data/details/${key}.json.gz`));
        if (!res.ok) return null;
        const j: unknown = JSON.parse(await decodeBody(await res.arrayBuffer()));
        return j && typeof j === "object" && !Array.isArray(j) ? (j as Record<string, TenderDetails>) : null;
      } catch {
        return null;
      }
    })();
    shards.set(key, p);
  }
  return p;
}

export async function loadDetails(id: string): Promise<TenderDetails | null> {
  const shard = await loadShard(shardKey(id));
  const d = shard?.[id];
  return d && typeof d === "object" ? d : null;
}

export type DetailsState = "ready" | "loading" | "unavailable";

/** Merges lazily-loaded shard details into docs; docs that already carry `documents` skip the fetch. */
export function useTenderDetails(docs: (TenderDoc | undefined)[]): { docs: (TenderDoc | undefined)[]; state: DetailsState } {
  const key = docs.map((d) => d?.id ?? "").join("|");
  const [loaded, setLoaded] = useState<Record<string, TenderDetails | null>>({});

  useEffect(() => {
    let stop = false;
    for (const d of docs) {
      if (!d || d.documents !== undefined || d.id in loaded) continue;
      void loadDetails(d.id).then((details) => {
        if (!stop) setLoaded((cur) => ({ ...cur, [d.id]: details }));
      });
    }
    return () => {
      stop = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const merged = docs.map((d) => (d ? mergeDetails(d, loaded[d.id]) : d));
  const pending = docs.some((d) => d && d.documents === undefined && !(d.id in loaded));
  const missing = docs.some((d) => d && d.documents === undefined && d.id in loaded && loaded[d.id] === null);
  return { docs: merged, state: pending ? "loading" : missing ? "unavailable" : "ready" };
}
