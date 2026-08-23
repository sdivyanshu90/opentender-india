import { useMemo, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useData } from "../App";
import { useWorkspace, updateWorkspace } from "../lib/store";
import { formatINR, formatINRCompact, formatDateTime, relativeDeadline, timeAgo } from "../lib/format";
import { buildIcs, downloadBlob } from "../lib/export";
import { SourceBadge, StatusBadge, EmptyState } from "../components/Badges";
import type { TenderDoc, EvidenceField } from "../lib/types";

const TABS = ["overview", "eligibility", "documents", "corrigenda", "timeline", "ai"] as const;
type Tab = (typeof TABS)[number];

export default function TenderDetail({
  copilotOpen,
  setCopilotOpen,
  compareIds,
  toggleCompare,
}: {
  copilotOpen: boolean;
  setCopilotOpen: (v: boolean) => void;
  compareIds: string[];
  toggleCompare: (id: string) => void;
}) {
  const { id = "" } = useParams();
  const { byId, docs } = useData();
  const ws = useWorkspace();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("overview");
  const doc = byId.get(id);

  const similar = useMemo(() => {
    if (!doc) return [];
    return docs
      .filter((d) => d.id !== doc.id && d.status === "active")
      .map((d) => ({
        doc: d,
        score:
          (d.state === doc.state ? 2 : 0) +
          (d.category === doc.category ? 3 : 0) +
          (d.authority === doc.authority ? 2 : 0) +
          ((d.title ?? "").toLowerCase().split(/\s+/).filter((w) => (doc.title ?? "").toLowerCase().includes(w)).length > 2 ? 2 : 0),
      }))
      .filter((x) => x.score >= 4)
      .sort((a, b) => b.score - a.score)
      .slice(0, 5);
  }, [docs, doc]);

  if (!doc) {
    return <EmptyState title="Tender not found" hint="It may have been archived. Try searching for its title or tender number." />;
  }

  const bookmarked = !!ws.bookmarks[doc.id];
  const toggleBookmark = () =>
    updateWorkspace((cur) => {
      const bookmarks = { ...cur.bookmarks };
      if (bookmarks[doc.id]) delete bookmarks[doc.id];
      else bookmarks[doc.id] = { at: Date.now(), status: "new", notes: "" };
      return { ...cur, bookmarks };
    });

  const addToCalendar = () => {
    if (!doc.closing_at) return;
    const blob = buildIcs([
      { uid: `${doc.id}-closing`, title: `Bid closing: ${doc.title ?? doc.tender_number ?? doc.id}`, start: new Date(doc.closing_at), url: doc.url },
      ...(doc.pre_bid_meeting_at
        ? [{ uid: `${doc.id}-prebid`, title: `Pre-bid meeting: ${doc.title ?? doc.id}`, start: new Date(doc.pre_bid_meeting_at), url: doc.url }]
        : []),
    ]);
    downloadBlob(blob, `opentender-${doc.tender_number ?? doc.id.slice(0, 8)}.ics`);
  };

  const exportCsv = () => {
    const row = flattenForCsv(doc);
    const csv = [
      ["field", "value"],
      ...Object.entries(row).map(([k, v]) => [k, v] as [string, string]),
    ]
      .map((r) => r.map((c) => (/^[=+\-@\t\r]/.test(c) ? `'${c}` : /[",\n]/.test(c) ? `"${c.replace(/"/g, '""')}"` : c)).join(","))
      .join("\r\n");
    downloadBlob(new Blob(["\uFEFF" + csv], { type: "text/csv" }), `tender-${doc.tender_number ?? doc.id.slice(0, 8)}.csv`);
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-5">
      {/* Hero */}
      <div className="card p-5">
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <StatusBadge status={doc.status} />
          <SourceBadge source={doc.source} />
          {doc._fixture && <span className="chip border-amber-300 bg-amber-50 text-amber-700">FIXTURE DATA</span>}
        </div>
        <h1 className="mt-2 text-lg font-bold leading-snug text-ink-900">{doc.title ?? "Untitled tender"}</h1>
        <p className="mt-1 text-sm text-ink-600">{doc.authority}</p>
        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
          <Fact label="Value">{formatINRCompact(doc.value)}{doc.value != null && <span className="ml-1 text-[11px] font-normal text-ink-400">{formatINR(doc.value)}</span>}</Fact>
          <Fact label="EMD">{formatINRCompact(doc.emd)}</Fact>
          <Fact label="Tender fee">{formatINRCompact(doc.fee)}</Fact>
          <Fact label="Closing"><span className="block">{relativeDeadline(doc.closing_at)}</span><span className="text-xs font-normal text-ink-500">{formatDateTime(doc.closing_at)}</span></Fact>
        </dl>
        <div className="mt-4 flex flex-wrap gap-2 border-t border-ink-100 pt-4">
          <button onClick={toggleBookmark} className={`btn ${bookmarked ? "!border-amber-300 !bg-amber-50 !text-amber-700" : ""}`}>
            {bookmarked ? "★ Bookmarked" : "☆ Bookmark"}
          </button>
          <button onClick={() => toggleCompare(doc.id)} disabled={!compareIds.includes(doc.id) && compareIds.length >= 5} className="btn">
            {compareIds.includes(doc.id) ? "✓ In compare list" : "Compare"}
          </button>
          <button onClick={addToCalendar} disabled={!doc.closing_at} className="btn">Add to calendar</button>
          <button onClick={exportCsv} className="btn">Export</button>
          <button onClick={() => setCopilotOpen(!copilotOpen)} className="btn btn-primary">Ask AI about this tender</button>
          <a href={doc.url} target="_blank" rel="noopener noreferrer nofollow" className="btn ml-auto !border-accent-200 !bg-accent-50 !text-accent-700">
            View official tender ↗
          </a>
        </div>
      </div>

      {/* Tabs */}
      <div className="sticky top-[57px] z-10 -mx-4 mt-4 bg-ink-50/95 px-4 py-2 backdrop-blur">
        <div role="tablist" aria-label="Tender sections" className="flex gap-1 overflow-x-auto">
          {TABS.map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              aria-label={
                t === "corrigenda" && doc.corrigenda_count > 0
                  ? `Corrigenda (${doc.corrigenda_count} recorded)`
                  : undefined
              }
              onClick={() => setTab(t)}
              className={`whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium capitalize ${
                tab === t ? "bg-white text-ink-900 shadow-sm ring-1 ring-ink-200" : "text-ink-500 hover:text-ink-800"
              }`}
            >
              {t === "ai" ? "AI Analysis" : t}
              {t === "corrigenda" && doc.corrigenda_count > 0 && (
                <span className="ml-1 rounded-full bg-amber-100 px-1.5 text-[11px] font-bold text-amber-700">{doc.corrigenda_count}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 min-h-64">
        {tab === "overview" && <Overview doc={doc} />}
        {tab === "eligibility" && <Eligibility doc={doc} />}
        {tab === "documents" && <Documents doc={doc} />}
        {tab === "corrigenda" && <CorrigendaNote count={doc.corrigenda_count} />}
        {tab === "timeline" && <Timeline doc={doc} />}
        {tab === "ai" && <AiAnalysis doc={doc} />}
      </div>

      {similar.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-500">Similar opportunities</h2>
          <ul className="card divide-y divide-ink-100">
            {similar.map(({ doc: s }) => (
              <li key={s.id}>
                <Link to={`/tender/${s.id}`} className="flex items-center justify-between px-4 py-2.5 hover:bg-accent-50/40">
                  <span className="truncate text-sm font-medium text-ink-700">{s.title ?? s.id}</span>
                  <span className="shrink-0 pl-3 text-xs tabular-nums text-ink-500">{formatINRCompact(s.value)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Sticky action bar */}
      <div className="fixed inset-x-0 bottom-14 z-20 border-t border-ink-200 bg-white/95 backdrop-blur lg:hidden">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-2 px-4 py-2">
          <span className="text-sm font-semibold text-red-600">{relativeDeadline(doc.closing_at)}</span>
          <div className="flex gap-2">
            <button onClick={toggleBookmark} className="btn">{bookmarked ? "★" : "☆"}</button>
            <button onClick={() => setCopilotOpen(true)} className="btn btn-primary">Ask AI</button>
            <a href={doc.url} target="_blank" rel="noopener noreferrer nofollow" className="btn">Official ↗</a>
          </div>
        </div>
      </div>

      <p className="mt-10 text-xs leading-relaxed text-ink-400">
        Discovered {timeAgo(doc.first_seen_at)} · Source portal {doc.portal}. OpenTender India is an independent
        open-source project and is not affiliated with the Government of India or any procurement authority. Always
        verify on the official portal before bidding.{" "}
        <button className="text-accent-600 hover:underline" onClick={() => navigate("/")}>Back to briefing</button>
      </p>
    </div>
  );
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">{label}</dt>
      <dd className="mt-0.5 text-sm font-semibold text-ink-800">{children}</dd>
    </div>
  );
}

function Overview({ doc }: { doc: TenderDoc }) {
  const rows: [string, string | null][] = [
    ["Reference number", doc.ref],
    ["Tender number", doc.tender_number],
    ["Category", doc.category],
    ["Type", doc.type],
    ["Location", [doc.city, doc.state].filter(Boolean).join(", ")],
    ["Published", formatDateTime(doc.published_at)],
    ["Bid opening", formatDateTime(doc.opening_at)],
    ["Pre-bid meeting", formatDateTime(doc.pre_bid_meeting_at)],
    ["Award", doc.award?.winning_bidder ?? null],
  ];
  return (
    <div className="card divide-y divide-ink-100">
      {rows.filter(([, v]) => v).map(([k, v]) => (
        <div key={k} className="grid grid-cols-[9rem_1fr] gap-3 px-4 py-2.5 text-sm">
          <span className="font-medium capitalize text-ink-500">{k}</span>
          <span className="break-words text-ink-800">{v}</span>
        </div>
      ))}
      {!rows.some(([, v]) => v) && <p className="px-4 py-3 text-sm text-ink-400">No structured fields were published on the listing page.</p>}
    </div>
  );
}

function Eligibility({ doc }: { doc: TenderDoc }) {
  const reqs = doc.ai?.eligibility?.requirements;
  if (!reqs || reqs.length === 0) {
    return (
      <EmptyState
        title="No eligibility extraction yet"
        hint="Structured requirements are produced by the nightly AI enrichment within budget. Check the documents tab and the official NIT for authoritative criteria."
      />
    );
  }
  return (
    <div className="card overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-ink-200 bg-ink-100/60 text-left text-xs font-semibold uppercase tracking-wide text-ink-500">
            <th className="px-4 py-2.5">Requirement</th>
            <th className="px-3 py-2.5">Value</th>
            <th className="px-3 py-2.5 hidden sm:table-cell">Period</th>
            <th className="px-3 py-2.5">Mandatory</th>
            <th className="px-3 py-2.5 hidden md:table-cell">Source</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-100">
          {reqs.map((r, i) => (
            <tr key={i}>
              <td className="px-4 py-2.5 text-ink-800">{r.requirement}</td>
              <td className="px-3 py-2.5 font-medium tabular-nums text-ink-700">{r.operator ? `${r.operator} ` : ""}{r.value ?? "—"}</td>
              <td className="hidden px-3 py-2.5 text-ink-600 sm:table-cell">{r.period ?? "—"}</td>
              <td className="px-3 py-2.5">{r.mandatory !== false ? <span className="chip border-red-200 bg-red-50 text-red-600">Yes</span> : <span className="chip">No</span>}</td>
              <td className="hidden px-3 py-2.5 text-xs text-ink-500 md:table-cell">
                {r.source_page != null ? <>Page {r.source_page}{r.source_clause ? `, clause ${r.source_clause}` : ""}</> : "—"}
                <span className="ml-1 text-ink-300">{Math.round((r.confidence ?? 0) * 100)}%</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {doc.ai?.eligibility?.exemptions_noted?.length ? (
        <p className="border-t border-ink-100 bg-emerald-50/50 px-4 py-2.5 text-xs text-emerald-700">
          Exemptions noted: {doc.ai.eligibility.exemptions_noted.join("; ")}
        </p>
      ) : null}
    </div>
  );
}

function Documents({ doc }: { doc: TenderDoc }) {
  if (!doc.documents.length)
    return <EmptyState title="No documents indexed" hint="Document downloads are CAPTCHA-gated on some portals; links are provided on the official page." />;
  return (
    <ul className="card divide-y divide-ink-100">
      {doc.documents.map((d, i) => (
        <li key={i}>
          <a href={d.url} target="_blank" rel="noopener noreferrer nofollow" className="flex items-center justify-between px-4 py-3 text-sm hover:bg-accent-50/40">
            <span className="truncate font-medium text-ink-700">{d.title}</span>
            <span className="chip shrink-0 uppercase">{d.type ?? "file"} ↗</span>
          </a>
        </li>
      ))}
    </ul>
  );
}

function CorrigendaNote({ count }: { count: number }) {
  return (
    <EmptyState
      title={count > 0 ? `${count} corrigendum${count > 1 ? "da" : ""} detected` : "No corrigenda detected"}
      hint={
        count > 0
          ? "Deterministic field-level differences are tracked in the timeline tab. Detailed change summaries are generated during AI enrichment."
          : "This tender has not changed since discovery."
      }
    />
  );
}

function Timeline({ doc }: { doc: TenderDoc }) {
  const events: { when: string | null; what: string; tone?: string }[] = [
    { when: doc.published_at, what: "Published" },
    { when: doc.pre_bid_meeting_at, what: "Pre-bid meeting" },
    { when: doc.first_seen_at, what: "Discovered by OpenTender", tone: "accent" },
    ...(doc.corrigenda_count > 0 ? [{ when: null as string | null, what: `${doc.corrigenda_count} corrigendum revision(s) recorded`, tone: "amber" }] : []),
    { when: doc.closing_at, what: "Bid submission closes", tone: "red" },
    { when: doc.opening_at, what: "Bids opened" },
  ].filter((e) => e.when);
  events.sort((a, b) => new Date(a.when!).getTime() - new Date(b.when!).getTime());
  return (
    <ol className="card space-y-0 divide-y divide-ink-100">
      {events.map((e, i) => (
        <li key={i} className="flex items-baseline gap-4 px-4 py-3">
          <span className="w-44 shrink-0 text-xs tabular-nums text-ink-500">{formatDateTime(e.when)}</span>
          <span className={`text-sm ${e.tone === "red" ? "font-semibold text-red-600" : e.tone === "amber" ? "font-medium text-amber-700" : e.tone === "accent" ? "text-accent-600" : "text-ink-800"}`}>
            {e.what}
          </span>
        </li>
      ))}
    </ol>
  );
}

function AiAnalysis({ doc }: { doc: TenderDoc }) {
  const summary = doc.ai?.summary;
  if (!summary)
    return (
      <EmptyState
        title="AI analysis pending"
        hint="Summaries are generated nightly within the free-tier request budget, prioritising corrigenda and high-value tenders. Use “Ask AI” with your own key for instant analysis."
      />
    );
  const fields: [string, EvidenceField][] = (
    [
      ["Opportunity", summary.opportunity],
      ["Buyer", summary.buyer],
      ["Contract value", summary.contract_value],
      ["Deadline", summary.deadline],
    ] as [string, EvidenceField | undefined][]
  ).filter((pair): pair is [string, EvidenceField] => !!pair[1]);
  return (
    <div className="space-y-4">
      <div className="card divide-y divide-ink-100">
        {fields.map(([label, f]) => (
          <EvidenceRow key={label} label={label} field={f} />
        ))}
      </div>
      <p className="text-xs text-ink-400">
        Overall confidence: {Math.round((summary.overall_confidence ?? 0) * 100)}%. Every value links to document
        evidence; NOT_FOUND means evidence was absent — never guessed.
      </p>
    </div>
  );
}

function EvidenceRow({ label, field }: { label: string; field: EvidenceField }) {
  return (
    <div className="px-4 py-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <span className="font-medium capitalize text-ink-500">{label}</span>
        <span className="text-right text-xs text-ink-300">{Math.round(field.confidence * 100)}% confident</span>
      </div>
      <p className={`mt-1 break-words ${field.value === "NOT_FOUND" ? "italic text-ink-400" : "text-ink-900"}`}>
        {field.value === "NOT_FOUND" ? "Source evidence not located." : field.value}
      </p>
      {field.citation && (
        <p className="mt-1 text-xs text-accent-600">
          — {field.citation.document_title}
          {field.citation.page ? `, page ${field.citation.page}` : ""}
          {field.citation.clause ? `, clause ${field.citation.clause}` : ""}
        </p>
      )}
    </div>
  );
}

function flattenForCsv(d: TenderDoc): Record<string, string> {
  return {
    title: d.title ?? "",
    authority: d.authority ?? "",
    state: d.state ?? "",
    city: d.city ?? "",
    category: d.category ?? "",
    reference: d.ref ?? "",
    tender_number: d.tender_number ?? "",
    value_inr: d.value != null ? String(Math.round(d.value)) : "",
    emd_inr: d.emd != null ? String(Math.round(d.emd)) : "",
    fee_inr: d.fee != null ? String(Math.round(d.fee)) : "",
    published_at: d.published_at ?? "",
    closing_at: d.closing_at ?? "",
    status: d.status,
    source_portal: d.portal,
    official_url: d.url,
  };
}
