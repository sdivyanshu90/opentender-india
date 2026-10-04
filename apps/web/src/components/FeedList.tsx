import type { FeedLink } from "../lib/feeds";

/** feeds: undefined = still loading, null = not published (yet). */
export function FeedList({ feeds }: { feeds: FeedLink[] | null | undefined }) {
  if (feeds === undefined) return <p className="text-xs text-ink-400">Loading feeds…</p>;
  if (feeds === null) return <p className="text-xs text-ink-400">Feeds have not been published yet.</p>;
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
      {feeds.map((f) => (
        <li key={f.href}>
          <a href={f.href} className="text-accent-600 hover:underline" type="application/atom+xml">
            {f.title}
          </a>
        </li>
      ))}
    </ul>
  );
}
