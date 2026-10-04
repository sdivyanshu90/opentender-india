import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useData } from "../App";
import { useWorkspace } from "../lib/store";
import { matchTender } from "../lib/match";
import { formatDateTime, formatINRCompact, istDateKey, relativeDeadline, timeAgo } from "../lib/format";
import { loadSourceStatus, type SourceStatusFile } from "../lib/data";
import { loadFeeds, type FeedLink } from "../lib/feeds";
import { queryToParams } from "../lib/query";

const DAY = 86_400_000;
const UNHEALTHY = new Set(["DEGRADED", "TEMPORARILY_BROKEN", "CAPTCHA_LIMITED"]);

/** Homepage: "What requires my attention today?" (spec #62). */
export default function Home() {
  const { docs, generatedAt, fixture, loading } = useData();
  const ws = useWorkspace();
  const [status, setStatus] = useState<SourceStatusFile | null | undefined>(undefined);
  const [feeds, setFeeds] = useState<FeedLink[] | null>(null);

  useEffect(() => {
    void loadSourceStatus().then(setStatus);
    void loadFeeds().then(setFeeds);
  }, []);

  const sections = useMemo(() => {
    const now = new Date();
    const todayKey = istDateKey(now);
    const active = docs.filter((d) => d.status === "active");
    const closingSoon = active
      .filter((d) => d.closing_at && new Date(d.closing_at).getTime() - now.getTime() < 7 * DAY && new Date(d.closing_at).getTime() > now.getTime())
      .sort((a, b) => (a.closing_at! < b.closing_at! ? -1 : 1));
    const closingToday = active.filter((d) => istDateKey(d.closing_at) === todayKey && new Date(d.closing_at!).getTime() > now.getTime()).length;
    const addedToday = docs.filter((d) => istDateKey(d.first_seen_at) === todayKey).length;
    const disclosed = active.filter((d) => d.value != null);
    const highValue = disclosed
      .filter((d) => d.value! >= 1e8)
      .sort((a, b) => b.value! - a.value!)
      .slice(0, 6);
    const changedAll = docs.filter((d) => d.corrigenda_count > 0).sort((a, b) => b.corrigenda_count - a.corrigenda_count);
    const matches = ws.profile
      ? active
          .map((d) => ({ doc: d, m: matchTender(d, ws.profile) }))
          .filter((x) => x.m.score >= 40)
          .sort((a, b) => b.m.score - a.m.score)
          .slice(0, 5)
      : [];
    return {
      closingSoon,
      closingToday,
      addedToday,
      activeCount: active.length,
      disclosedCount: disclosed.length,
      highValue,
      changed: changedAll.slice(0, 5),
      changedTotal: changedAll.length,
      matches,
    };
  }, [docs, ws.profile]);

  const portals = useMemo(() => {
    if (!status) return null;
    const rows = Object.values(status.sources);
    const times = rows.map((r) => r.last_success).filter((t): t is string => !!t && !Number.isNaN(Date.parse(t)));
    times.sort((a, b) => Date.parse(b) - Date.parse(a));
    return {
      healthy: rows.filter((r) => r.status === "ACTIVE").length,
      degraded: rows.filter((r) => UNHEALTHY.has(r.status)).length,
      lastSuccess: times[0] ?? null,
    };
  }, [status]);

  const ready = !loading && docs.length > 0;

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

      <HomeSearch />

      {ready && (
        <dl className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6" data-testid="home-stats">
          <Stat label="Active tenders" value={sections.activeCount} to="/discover?status=active" />
          <Stat label="Added today" value={sections.addedToday} to="/new" />
          <Stat label="Closing today" value={sections.closingToday} to="/discover?within=1" />
          <Stat label="Closing this week" value={sections.closingSoon.length} to="/closing-soon" />
          <Stat label="With corrigenda" value={sections.changedTotal} to="/changed" />
          <Stat
            label="Portals healthy"
            value={portals ? `${portals.healthy}${portals.degraded ? ` · ${portals.degraded} degraded` : ""}` : "—"}
            to="/sources"
          />
        </dl>
      )}
      {portals && (
        <p className="mt-1.5 text-xs text-ink-400">
          {portals.lastSuccess
            ? `Last successful portal refresh ${timeAgo(portals.lastSuccess)} (${formatDateTime(portals.lastSuccess)}).`
            : "No portal has recorded a successful refresh yet."}{" "}
          <Link to="/sources" className="text-accent-600 hover:underline">Source status</Link>
        </p>
      )}

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

      {sections.highValue.length > 0 ? (
        <Section title="High-value opportunities" count={undefined} href="/discover?sort=value&min=100000000">
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
      ) : (
        ready && (
          <p className="mt-6 rounded-lg border border-ink-200 bg-white p-3 text-xs leading-relaxed text-ink-500" data-testid="values-note">
            Tender values are rarely disclosed on procurement portals: {sections.disclosedCount} of {sections.activeCount} active
            tenders state one, and none is above ₹10 Cr, so there is no high-value list today. A missing value means
            “not disclosed”, never zero.
          </p>
        )
      )}

      {sections.changed.length > 0 && (
        <Section title="Recently changed" count={sections.changedTotal} href="/changed">
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
        <Link to="/sources#feeds" className="mr-3 font-medium text-accent-600 hover:underline">
          {feeds ? `Subscribe to Atom feeds (${feeds.length})` : "Atom feeds"}
        </Link>
        OpenTender India is an independent open-source project and is not affiliated with the Government of India or any
        procurement authority. Always verify tender information on the linked official portal before making procurement
        decisions or submitting a bid.
      </p>
    </div>
  );
}

function HomeSearch() {
  const navigate = useNavigate();
  const [text, setText] = useState("");
  return (
    <form
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        navigate(`/discover?${queryToParams(text.trim()).toString()}`);
      }}
      className="mt-4 flex gap-2"
    >
      <input
        type="search"
        aria-label="Search all tenders"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Search by keyword, tender number or ask e.g. “road repair Kerala under 50 lakh”"
        className="input w-full"
      />
      <button type="submit" className="btn btn-primary">
        Search
      </button>
    </form>
  );
}

function Stat({ label, value, to }: { label: string; value: number | string; to: string }) {
  return (
    <Link to={to} className="card block px-3 py-2 hover:border-accent-400">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-ink-400">{label}</dt>
      <dd className="mt-0.5 text-lg font-bold tabular-nums text-ink-900">{typeof value === "number" ? value.toLocaleString("en-IN") : value}</dd>
    </Link>
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
