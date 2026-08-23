import { Link } from "react-router-dom";
import { formatINRCompact, formatDate } from "../lib/format";
import type { TenderDoc } from "../lib/types";
import { DeadlineBadge, SourceBadge, StatusBadge } from "./Badges";

interface RowProps {
  doc: TenderDoc;
  isNew: boolean;
  bookmarked: boolean;
  selected: boolean;
  match?: { score: number; reasons: string[] };
  onToggleBookmark: () => void;
  onToggleCompare: () => void;
}

export function TenderRow({ doc, isNew, bookmarked, selected, match, onToggleBookmark, onToggleCompare }: RowProps) {
  return (
    <tr className="border-b border-ink-100 text-sm hover:bg-accent-50/40">
      <td className="px-3 py-2.5">
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-ink-300 text-accent-600 focus:ring-accent-500"
          checked={selected}
          onChange={onToggleCompare}
          aria-label={`Select ${doc.title ?? "tender"} for comparison`}
        />
      </td>
      <td className="max-w-md px-3 py-2.5">
        <Link to={`/tender/${doc.id}`} className="group block">
          <div className="flex items-start gap-1.5">
            {isNew && (
              <span className="mt-0.5 shrink-0 rounded bg-accent-100 px-1 py-px text-[9px] font-bold uppercase tracking-wider text-accent-700">
                New
              </span>
            )}
            <span className="line-clamp-1 font-medium text-ink-900 group-hover:text-accent-700" title={doc.title ?? ""}>
              {doc.title ?? "Untitled tender"}
            </span>
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-ink-500">
            {doc.tender_number && <span className="font-mono">{doc.tender_number}</span>}
            {doc.ref && !doc.tender_number && <span className="font-mono">{doc.ref}</span>}
            <span className="truncate max-w-[16rem]">{doc.authority}</span>
          </div>
        </Link>
      </td>
      <td className="hidden whitespace-nowrap px-3 py-2.5 text-xs text-ink-600 md:table-cell">{doc.state ?? "—"}</td>
      <td className="whitespace-nowrap px-3 py-2.5 text-right font-medium tabular-nums text-ink-800">
        {formatINRCompact(doc.value)}
      </td>
      <td className="whitespace-nowrap px-3 py-2.5 text-xs text-ink-600">
        <div>{formatDate(doc.closing_at)}</div>
        <DeadlineBadge closingAt={doc.closing_at} />
      </td>
      <td className="hidden px-3 py-2.5 lg:table-cell">
        {match ? (
          <span className="text-sm font-semibold text-ink-700">{match.score > 0 ? `${match.score}%` : "—"}</span>
        ) : null}
      </td>
      <td className="hidden px-3 py-2.5 md:table-cell"><StatusBadge status={doc.status} /></td>
      <td className="hidden whitespace-nowrap px-3 py-2.5 xl:table-cell"><SourceBadge source={doc.source} /></td>
      <td className="px-2 py-2.5 text-right">
        <button
          onClick={onToggleBookmark}
          aria-label={bookmarked ? "Remove bookmark" : "Bookmark"}
          className={`rounded p-1.5 hover:bg-ink-100 ${bookmarked ? "text-amber-500" : "text-ink-300"}`}
        >
          {bookmarked ? "★" : "☆"}
        </button>
      </td>
    </tr>
  );
}

export function TenderCard({ doc, isNew, bookmarked, match, onToggleBookmark }: Omit<RowProps, "onToggleCompare" | "selected">) {
  return (
    <article className="card min-w-0 p-4 transition-shadow hover:shadow-md">
      <div className="flex min-w-0 items-start justify-between gap-2">
        <Link to={`/tender/${doc.id}`} className="min-w-0 flex-1">
          <h3 className="flex items-start gap-1.5 text-sm font-medium leading-snug text-ink-900">
            {isNew && <NewTag />}
            <span className="line-clamp-2">{doc.title ?? "Untitled tender"}</span>
          </h3>
          <p className="mt-1 truncate text-xs text-ink-500">{doc.authority}</p>
        </Link>
        <button
          onClick={onToggleBookmark}
          aria-label={bookmarked ? "Remove bookmark" : "Bookmark"}
          className={`shrink-0 rounded p-1 text-lg leading-none ${bookmarked ? "text-amber-500" : "text-ink-300"}`}
        >
          {bookmarked ? "★" : "☆"}
        </button>
      </div>
      <dl className="mt-3 grid min-w-0 grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
        <div><dt className="text-ink-400">Value</dt><dd className="font-semibold text-ink-800">{formatINRCompact(doc.value)}</dd></div>
        <div><dt className="text-ink-400">EMD</dt><dd className="text-ink-700">{formatINRCompact(doc.emd)}</dd></div>
        <div><dt className="text-ink-400">Location</dt><dd className="text-ink-700">{[doc.city, doc.state].filter(Boolean).join(", ") || "—"}</dd></div>
        <div><dt className="text-ink-400">Closes</dt><dd className="text-ink-700"><DeadlineBadge closingAt={doc.closing_at} /></dd></div>
      </dl>
      <div className="mt-3 flex items-center justify-between border-t border-ink-100 pt-2">
        <SourceBadge source={doc.source} />
        {match && match.score > 0 && (
          <span className="text-xs font-semibold text-emerald-600">{match.score}% match</span>
        )}
      </div>
    </article>
  );
}

function NewTag() {
  return (
    <span className="mt-0.5 shrink-0 rounded bg-accent-100 px-1 py-px text-[9px] font-bold uppercase tracking-wider text-accent-700">
      New
    </span>
  );
}
