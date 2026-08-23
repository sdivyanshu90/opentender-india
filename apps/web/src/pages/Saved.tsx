import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useData } from "../App";
import { updateWorkspace, useWorkspace } from "../lib/store";
import { formatINRCompact, formatDate } from "../lib/format";
import { EmptyState } from "../components/Badges";
import { buildCsv, downloadBlob } from "../lib/export";

const STATUSES = ["new", "reviewing", "interested", "bid", "skip", "submitted"] as const;

export default function Saved() {
  const { byId } = useData();
  const ws = useWorkspace();

  const savedDocs = useMemo(
    () =>
      Object.entries(ws.bookmarks)
        .map(([id, meta]) => ({ doc: byId.get(id), meta }))
        .filter((x) => x.doc)
        .sort((a, b) => b.meta.at - a.meta.at) as { doc: NonNullable<ReturnType<typeof byId.get>>; meta: (typeof ws.bookmarks)[string] }[],
    [ws.bookmarks, byId],
  );

  if (savedDocs.length === 0 && ws.savedSearches.length === 0) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-6">
        <h1 className="mb-1 text-lg font-bold text-ink-900">Saved</h1>
        <EmptyState
          title="No bookmarks yet"
          hint="Bookmark tenders from search results to build your workspace. Everything is stored locally in this browser."
        />
      </div>
    );
  }

  const setStatus = (id: string, status: string) =>
    updateWorkspace((cur) => ({
      ...cur,
      bookmarks: { ...cur.bookmarks, [id]: { ...cur.bookmarks[id], status: status as never } },
    }));

  const setNotes = (id: string, notes: string) =>
    updateWorkspace((cur) => ({
      ...cur,
      bookmarks: { ...cur.bookmarks, [id]: { ...cur.bookmarks[id], notes } },
    }));

  const exportJson = () =>
    downloadBlob(
      new Blob([JSON.stringify({ bookmarks: ws.bookmarks, savedSearches: ws.savedSearches, profile: ws.profile }, null, 1)], {
        type: "application/json",
      }),
      `opentender-workspace-${new Date().toISOString().slice(0, 10)}.json`,
    );

  const exportCsvAll = () => {
    downloadBlob(
      buildCsv(
        savedDocs.map(({ doc }) => ({
          title: doc.title ?? "",
          authority: doc.authority ?? "",
          value: doc.value != null ? Math.round(doc.value) : "",
          closing_at: doc.closing_at ?? "",
          status: doc.status,
          url: doc.url,
        })),
        ["title", "authority", "value", "closing_at", "status", "url"],
      ),
      "opentender-bookmarks.csv",
    );
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <h1 className="text-lg font-bold text-ink-900">Saved</h1>
      <p className="mt-0.5 text-sm text-ink-500">{savedDocs.length} bookmarked tenders · stored locally</p>

      <div className="mt-3 flex gap-2">
        <button onClick={exportJson} className="btn">Backup JSON</button>
        <button onClick={exportCsvAll} className="btn">Export CSV</button>
      </div>

      <ul className="card mt-4 divide-y divide-ink-100">
        {savedDocs.map(({ doc, meta }) => (
          <li key={doc.id} className="px-4 py-3">
            <div className="flex items-start justify-between gap-3">
              <Link to={`/tender/${doc.id}`} className="min-w-0">
                <span className="block truncate font-medium text-ink-800 hover:text-accent-700">{doc.title ?? doc.id}</span>
                <span className="text-xs text-ink-500">
                  {doc.authority} · {formatINRCompact(doc.value)} · closes {formatDate(doc.closing_at)}
                </span>
              </Link>
              <button
                onClick={() => updateWorkspace((cur) => {
                  const bookmarks = { ...cur.bookmarks };
                  delete bookmarks[doc.id];
                  return { ...cur, bookmarks };
                })}
                className="shrink-0 rounded p-1 text-xs text-ink-400 hover:bg-red-50 hover:text-red-600"
                aria-label={`Remove ${doc.title} from saved`}
              >
                Remove
              </button>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <select
                value={meta.status}
                onChange={(e) => setStatus(doc.id, e.target.value)}
                aria-label="Workflow status"
                className="input !py-1 text-xs"
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s[0].toUpperCase() + s.slice(1)}
                  </option>
                ))}
              </select>
              <input
                value={meta.notes}
                onChange={(e) => setNotes(doc.id, e.target.value)}
                placeholder="Private notes (never uploaded)…"
                className="input min-w-0 flex-1 !py-1 text-xs"
              />
            </div>
          </li>
        ))}
      </ul>

      {ws.savedSearches.length > 0 && (
        <>
          <h2 className="mt-8 mb-2 text-sm font-semibold uppercase tracking-wide text-ink-500">Saved searches</h2>
          <ul className="card divide-y divide-ink-100">
            {ws.savedSearches.map((s) => (
              <li key={s.id} className="flex items-center justify-between px-4 py-2.5">
                <Link to={`/discover?${s.query}`} className="min-w-0 truncate text-sm font-medium text-accent-700 hover:underline">
                  {s.name}
                </Link>
                <button
                  onClick={() => updateWorkspace((cur) => ({ ...cur, savedSearches: cur.savedSearches.filter((x) => x.id !== s.id) }))}
                  className="ml-3 shrink-0 text-xs text-ink-400 hover:text-red-600"
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
