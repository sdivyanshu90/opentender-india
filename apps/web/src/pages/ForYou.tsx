import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ProfileFields } from "./Settings";
import { useData } from "../App";
import { useWorkspace } from "../lib/store";
import { matchTender } from "../lib/match";
import { formatINRCompact, relativeDeadline } from "../lib/format";

/** Personal briefing (spec #33): ranked locally; profile never leaves device. */
export default function ForYou() {
  const { docs, loading } = useData();
  const ws = useWorkspace();
  const [showSetup, setShowSetup] = useState(!ws.profile);

  const ranked = useMemo(() => {
    if (!ws.profile) return [];
    return docs
      .filter((d) => d.status === "active")
      .map((d) => ({ doc: d, m: matchTender(d, ws.profile) }))
      .sort((a, b) => b.m.score - a.m.score);
  }, [docs, ws.profile]);

  const strong = ranked.filter((x) => x.m.score >= 60);
  const maybe = ranked.filter((x) => x.m.score >= 35 && x.m.score < 60);

  if (loading) return null;

  if (!ws.profile) {
    return (
      <div className="mx-auto max-w-lg px-4 py-10">
        <h1 className="text-xl font-bold text-ink-900">Opportunities for you</h1>
        <p className="mt-2 text-sm leading-relaxed text-ink-600">
          Tell us what your company does and OpenTender will rank opportunities locally — your profile stays in this
          browser and is never uploaded.
        </p>
        <ProfileForm />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-ink-900">Today’s opportunities for you</h1>
          <p className="mt-0.5 text-sm text-ink-500">
            Ranked on-device from your profile. Nothing personal is sent to any server.
          </p>
        </div>
        <button onClick={() => setShowSetup(true)} className="btn shrink-0">Edit profile</button>
      </div>

      {showSetup && (
        <div className="card mt-4 p-4">
          <ProfileForm />
          <button onClick={() => setShowSetup(false)} className="btn mt-3">Done</button>
        </div>
      )}

      <MatchGroup title={`${strong.length} strong matches`} items={strong} emptyHint="No strong matches today — check back after the next ingestion run." />
      <MatchGroup title={`${maybe.length} worth a look`} items={maybe} emptyHint="" />

      {ranked.length > 0 && (
        <>
          <h2 className="mt-8 text-sm font-semibold uppercase tracking-wide text-ink-500">Why these rankings?</h2>
          <p className="mt-1 text-xs leading-relaxed text-ink-400">
            Scores are deterministic: industry/category relevance (30), geography (20), contract size fit (25),
            MSME/startup advantages (7), deadline feasibility (10). Click any row to see per-tender reasons.
          </p>
        </>
      )}
    </div>
  );
}

function MatchGroup({ title, items, emptyHint }: { title: string; items: { doc: import("../lib/types").TenderDoc; m: ReturnType<typeof matchTender> }[]; emptyHint: string }) {
  if (items.length === 0) {
    return emptyHint ? <p className="mt-4 card p-3 text-sm text-ink-400">{emptyHint}</p> : null;
  }
  return (
    <section className="mt-5">
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-500">{title}</h2>
      <ul className="card divide-y divide-ink-100">
        {items.slice(0, 12).map(({ doc, m }) => (
          <li key={doc.id}>
            <Link to={`/tender/${doc.id}`} className="block px-4 py-3 hover:bg-accent-50/40">
              <div className="flex items-start justify-between gap-3">
                <span className="min-w-0">
                  <span className="block truncate font-medium text-ink-800">{doc.title ?? doc.id}</span>
                  <span className="text-xs text-ink-500">{doc.authority} · {formatINRCompact(doc.value)} · {relativeDeadline(doc.closing_at)}</span>
                  <span className="mt-1 block truncate text-xs text-emerald-700" title={m.reasons.join("; ")}>
                    {m.reasons[0] ?? "General fit"}
                  </span>
                </span>
                <span className="shrink-0 text-right">
                  <span className={`text-sm font-bold ${m.score >= 70 ? "text-emerald-600" : "text-amber-600"}`}>{m.score}%</span>
                  <span className="block text-[10px] uppercase tracking-wide text-ink-400">match</span>
                </span>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ProfileForm({ onDone }: { onDone?: () => void }) {
  return (
    <div className="mt-4">
      <ProfileFields />
      {onDone && (
        <button onClick={onDone} className="btn btn-primary mt-3">
          Save and show matches
        </button>
      )}
    </div>
  );
}
