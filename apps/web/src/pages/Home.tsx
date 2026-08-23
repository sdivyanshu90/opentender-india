import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useData } from "../App";
import { useWorkspace } from "../lib/store";
import { matchTender } from "../lib/match";
import { formatINRCompact, relativeDeadline, timeAgo } from "../lib/format";

/** Homepage: "What requires my attention today?" (spec #62). */
export default function Home() {
  const { docs, generatedAt, fixture, loading } = useData();
  const ws = useWorkspace();

  const sections = useMemo(() => {
    const now = new Date();
    const today = now.toISOString().slice(0, 10);
    const active = docs.filter((d) => d.status === "active");
    const closingSoon = active
      .filter((d) => d.closing_at && new Date(d.closing_at).getTime() - now.getTime() < 7 * 86_400_000 && new Date(d.closing_at).getTime() > now.getTime())
      .sort((a, b) => (a.closing_at! < b.closing_at! ? -1 : 1));
    const newToday = docs.filter((d) => d.first_seen_at?.slice(0, 10) === today);
    const highValue = [...active]
      .filter((d) => (d.value ?? 0) >= 1e8)
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0))
      .slice(0, 6);
    const changed = docs.filter((d) => d.corrigenda_count > 0).slice(0, 5);
    const matches = ws.profile
      ? active
          .map((d) => ({ doc: d, m: matchTender(d, ws.profile) }))
          .filter((x) => x.m.score >= 40)
          .sort((a, b) => b.m.score - a.m.score)
          .slice(0, 5)
      : [];
    return { closingSoon, newToday, highValue, changed, matches };
  }, [docs, ws.profile]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <h1 className="text-xl font-bold text-ink-900">Today’s briefing</h1>
      <p className="mt-0.5 text-sm text-ink-500">
        {generatedAt
          ? `Dataset updated ${timeAgo(generatedAt)} · ${docs.length} tenders tracked`
          : loading
            ? "Loading dataset…"
            : "No dataset published yet"}
        {fixture && " · synthetic demo data"}
      </p>

      {ws.profile && (
        <Section title="Best matches for you" count={sections.matches.length} href="/for-you">
          <TenderList
            items={sections.matches.map(({ doc, m }) => ({
              id: doc.id,
              title: doc.title,
              authority: doc.authority,
              right: `${m.score}% match`,
              meta: formatINRCompact(doc.value),
            }))}
          />
        </Section>
      )}

      <Section title="Closing soon" count={sections.closingSoon.length} href="/closing-soon">
        <TenderList
          items={sections.closingSoon.slice(0, 5).map((d) => ({
            id: d.id,
            title: d.title,
            authority: d.authority,
            right: relativeDeadline(d.closing_at),
            rightTone: /3 days|today|tomorrow/.test(relativeDeadline(d.closing_at)) ? "text-red-600" : "text-amber-600",
            meta: formatINRCompact(d.value),
          }))}
        />
      </Section>

      <Section title="New high-value opportunities" count={undefined} href="/discover?sort=value">
        <TenderList
          items={sections.highValue.map((d) => ({
            id: d.id,
            title: d.title,
            authority: d.authority,
            right: formatINRCompact(d.value),
            rightTone: "text-emerald-600",
          }))}
        />
      </Section>

      {sections.changed.length > 0 && (
        <Section title="Recently changed" count={sections.changed.length} href="/changed">
          <TenderList
            items={sections.changed.map((d) => ({
              id: d.id,
              title: d.title,
              authority: `${d.corrigenda_count} corrigenda · ${d.authority}`,
            }))}
          />
        </Section>
      )}

      <p className="mt-10 rounded-lg border border-ink-200 bg-white p-3 text-xs leading-relaxed text-ink-500">
        OpenTender India is an independent open-source project and is not affiliated with the Government of India or any
        procurement authority. Always verify tender information on the linked official portal before making procurement
        decisions or submitting a bid.
      </p>
    </div>
  );
}

function Section({ title, count, href, children }: { title: string; count?: number; href: string; children: React.ReactNode }) {
  return (
    <section className="mt-6">
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-500">
          {title}
          {count != null && <span className="ml-1.5 rounded-full bg-ink-100 px-1.5 py-px text-xs font-bold text-ink-600">{count}</span>}
        </h2>
        <Link to={href} className="text-xs font-medium text-accent-600 hover:underline">
          View all →
        </Link>
      </div>
      {children}
    </section>
  );
}

interface Item {
  id: string;
  title: string | null;
  authority: string | null;
  meta?: string;
  right?: string;
  rightTone?: string;
}

function TenderList({ items }: { items: Item[] }) {
  if (items.length === 0)
    return <p className="card p-3 text-sm text-ink-400">Nothing here yet.</p>;
  return (
    <ul className="card divide-y divide-ink-100">
      {items.map((item) => (
        <li key={item.id}>
          <Link to={`/tender/${item.id}`} className="flex items-center justify-between gap-3 px-4 py-2.5 hover:bg-accent-50/40">
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium text-ink-800">{item.title ?? item.id}</span>
              <span className="block truncate text-xs text-ink-500">{item.authority}</span>
            </span>
            <span className="shrink-0 text-right text-xs">
              {item.meta && <span className="block font-semibold tabular-nums text-ink-700">{item.meta}</span>}
              {item.right && (
                <span className={`block font-medium ${item.rightTone ?? "text-ink-500"}`}>{item.right}</span>
              )}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
