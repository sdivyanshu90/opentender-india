import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useData } from "../App";
import { parseQuery } from "../lib/nlq";
import { mergeParsed, queryToParams, runQuery } from "../lib/query";
import { uniqueValues } from "../lib/data";
import { formatAuthority, formatINRCompact } from "../lib/format";

const SUGGESTIONS = [
  "solar EPC Maharashtra",
  "closing this week above ₹1 Cr",
  "IREPS signalling tenders",
  "road works Rajasthan",
];

/** Command palette / global search (spec #53, #54). */
export default function CommandPalette({ onClose }: { onClose: () => void }) {
  const { docs, index, byId } = useData();
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const parsed = useMemo(() => (query.trim() ? parseQuery(query) : null), [query]);

  const sources = useMemo(() => new Set(uniqueValues(docs, "source")), [docs]);

  // Same pipeline as the Discover page (relevance first, then structured filters),
  // so the palette and the results page never disagree.
  const hits = useMemo(() => {
    if (!parsed?.keywords) return [];
    const f = mergeParsed({ keywords: "" }, parsed, sources);
    return runQuery(docs, f, { index, byId }).docs.slice(0, 6).map((doc) => ({ doc }));
  }, [docs, index, byId, parsed, sources]);

  const commands = useMemo(
    () =>
      [
        { label: "Go to saved tenders", action: () => navigate("/saved") },
        { label: "Show closing soon", action: () => navigate("/closing-soon") },
        { label: "Show new today", action: () => navigate("/new") },
        { label: "View source health", action: () => navigate("/sources") },
        { label: "Open settings", action: () => navigate("/settings") },
      ].filter((c) => !query || c.label.toLowerCase().includes(query.toLowerCase())),
    [navigate, query],
  );

  const go = (rawQuery: string) => {
    navigate(`/discover?${queryToParams(rawQuery, undefined, sources).toString()}`);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-ink-900/40 p-4 pt-[12vh]" onClick={onClose} role="dialog" aria-modal="true" aria-label="Command palette">
      <div className="mx-auto max-w-xl overflow-hidden rounded-xl border border-ink-200 bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") go(query);
          }}
          placeholder="Search tenders or ask AI…"
          className="w-full border-b border-ink-100 px-4 py-3.5 text-base outline-none placeholder:text-ink-400"
        />
        {!query && (
          <div className="border-b border-ink-100 px-4 py-2">
            <p className="px-1 pb-1 text-[10px] font-semibold uppercase tracking-wider text-ink-400">Try</p>
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => setQuery(s)} className="block w-full rounded-md px-2 py-1.5 text-left text-sm text-ink-600 hover:bg-ink-50">
                ⌕ {s}
              </button>
            ))}
          </div>
        )}
        {parsed && (
          <div className="border-b border-ink-100 bg-accent-50/50 px-4 py-2.5">
            <p className="text-xs text-ink-500">
              Interpreted as:
              {parsed.keywords && <> keywords <b>{parsed.keywords}</b> ·</>}
              {parsed.state && <> state <b>{parsed.state}</b> ·</>}
              {parsed.minValue != null && <> above <b>{formatINRCompact(parsed.minValue)}</b> ·</>}
              {parsed.maxValue != null && <> below <b>{formatINRCompact(parsed.maxValue)}</b> ·</>}
              {parsed.sourceHint && <> portal <b>{parsed.sourceHint}</b> ·</>}
              {parsed.closingThisMonth && <> closing <b>this month</b> ·</>}
              {parsed.closingWithinDays != null && <> closing within <b>{parsed.closingWithinDays} days</b></>}
              {!parsed.keywords && !parsed.state && parsed.minValue == null && parsed.maxValue == null && !parsed.sourceHint && !parsed.closingThisMonth && parsed.closingWithinDays == null && <i> plain keyword search</i>}
            </p>
            <button onClick={() => go(query)} className="btn btn-primary mt-2 w-full">Search →</button>
          </div>
        )}
        {hits.length > 0 && (
          <div className="px-2 py-2">
            {hits.map(({ doc }) => (
              <button
                key={doc.id}
                onClick={() => {
                  navigate(`/tender/${doc.id}`);
                  onClose();
                }}
                className="block w-full truncate rounded-md px-2 py-2 text-left text-sm hover:bg-ink-50"
              >
                <span className="font-medium text-ink-800">{doc.title ?? doc.tender_number ?? doc.id}</span>
                <span className="ml-2 text-xs text-ink-400">{formatAuthority(doc.authority)}</span>
              </button>
            ))}
          </div>
        )}
        {commands.length > 0 && (
          <div className="px-2 py-2">
            <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-ink-400">Commands</p>
            {commands.map((c) => (
              <button key={c.label} onClick={() => { c.action(); onClose(); }} className="block w-full rounded-md px-2 py-1.5 text-left text-sm text-ink-600 hover:bg-ink-50">
                → {c.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
