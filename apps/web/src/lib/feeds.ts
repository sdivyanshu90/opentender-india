import { assetUrl } from "./data";

export interface FeedLink {
  title: string;
  /** resolved against the site base, ready for href */
  href: string;
}

/** Resolves an index.json path ("all.xml", "feeds/all.xml" or "data/feeds/all.xml") under data/feeds. */
function feedHref(path: string): string | null {
  const p = path.trim().replace(/^\/+/, "");
  if (!p || /^[a-z][a-z0-9+.-]*:/i.test(p) || p.includes("..")) return null;
  if (p.startsWith("data/")) return assetUrl(p);
  if (p.startsWith("feeds/")) return assetUrl(`data/${p}`);
  return assetUrl(`data/feeds/${p}`);
}

/** data/feeds/index.json ({title, path}[]); null when the pipeline has not published feeds. */
export async function loadFeeds(): Promise<FeedLink[] | null> {
  try {
    const res = await fetch(assetUrl("data/feeds/index.json"));
    if (!res.ok) return null;
    const j: unknown = await res.json();
    const list = Array.isArray(j) ? j : (j as { feeds?: unknown } | null)?.feeds;
    if (!Array.isArray(list)) return null;
    const out: FeedLink[] = [];
    for (const item of list) {
      const rec = item as { title?: unknown; path?: unknown };
      if (typeof rec?.title !== "string" || typeof rec.path !== "string") continue;
      const href = feedHref(rec.path);
      if (href) out.push({ title: rec.title, href });
    }
    return out.length > 0 ? out : null;
  } catch {
    return null;
  }
}
