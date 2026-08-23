import { Link } from "react-router-dom";
import { useData } from "../App";
import { formatINRCompact, relativeDeadline } from "../lib/format";
import { EmptyState } from "../components/Badges";
import { matchTender } from "../lib/match";
import { useWorkspace } from "../lib/store";

/** Side-by-side comparison of 2–5 tenders (spec #29). */
export default function Compare({ compareIds, toggleCompare }: { compareIds: string[]; toggleCompare: (id: string) => void }) {
  const { byId } = useData();
  const ws = useWorkspace();

  const docs = compareIds.map((id) => byId.get(id)).filter(Boolean) as NonNullable<ReturnType<typeof byId.get>>[];

  if (docs.length < 2) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-6">
        <h1 className="text-lg font-bold text-ink-900">Compare</h1>
        <EmptyState
          title={docs.length === 0 ? "No tenders selected" : "Select at least one more tender"}
          hint="Use the checkbox column in Discover or the Compare button on a tender page. Select 2–5 tenders."
        />
      </div>
    );
  }

  const rows: { label: string; get: (d: (typeof docs)[number]) => string; highlight?: boolean }[] = [
    { label: "Authority", get: (d) => d.authority ?? "—" },
    { label: "Location", get: (d) => [d.city, d.state].filter(Boolean).join(", ") || "—" },
    { label: "Scope", get: (d) => d.category ?? d.type ?? "—" },
    { label: "Value", get: (d) => formatINRCompact(d.value), highlight: true },
    { label: "EMD", get: (d) => formatINRCompact(d.emd), highlight: true },
    { label: "Fee", get: (d) => formatINRCompact(d.fee) },
    { label: "Deadline", get: (d) => `${formatDateSafe(d.closing_at)} (${relativeDeadline(d.closing_at)})`, highlight: true },
    { label: "Status", get: (d) => d.status },
    {
      label: "Eligibility",
      get: (d) =>
        d.ai?.eligibility?.requirements?.length
          ? `${d.ai.eligibility.requirements.length} extracted requirement(s)`
          : "not yet extracted",
    },
    {
      label: "Turnover req.",
      get: (d) => findReq(d, /turnover/i) ?? "—",
    },
    {
      label: "Experience req.",
      get: (d) => findReq(d, /experience|similar work/i) ?? "—",
    },
    {
      label: "Certifications",
      get: (d) => findReq(d, /(iso|certif|licen[cs])/i) ?? "—",
    },
    {
      label: "Major risks",
      get: (d) => (d.ai?.risk?.flags?.length ? d.ai.risk.flags.map((f) => f.label).join(", ") : "not yet analysed"),
    },
    { label: "Match with profile", get: (d) => (ws.profile ? `${matchTender(d, ws.profile).score}%` : "set up profile") },
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-ink-900">Compare ({docs.length})</h1>
        <button onClick={() => docs.forEach((d) => toggleCompare(d.id))} className="btn">Clear all</button>
      </div>

      <div className="card mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-ink-200">
              <th className="table-header w-40">Attribute</th>
              {docs.map((d) => (
                <th key={d.id} className="table-header min-w-48 align-top">
                  <Link to={`/tender/${d.id}`} className="block max-w-56 whitespace-normal font-semibold leading-snug !normal-case hover:text-accent-700">
                    {d.title ?? d.tender_number ?? d.id}
                  </Link>
                  <button onClick={() => toggleCompare(d.id)} className="mt-1 text-[10px] font-medium text-ink-400 hover:text-red-600">
                    remove
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-100">
            {rows.map((row) => (
              <tr key={row.label}>
                <th scope="row" className="bg-ink-50/60 px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-ink-500">
                  {row.label}
                </th>
                {docs.map((d) => (
                  <td key={d.id} className={`px-3 py-2.5 align-top ${row.highlight ? "font-semibold text-ink-800" : "text-ink-700"}`}>
                    {row.get(d)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-ink-400">
        Differences in value, EMD and deadline are highlighted rows. Eligibility rows come from AI extraction where
        available and are marked “not yet extracted” otherwise — always verify against official documents.
      </p>
    </div>
  );
}

function formatDateSafe(v: string | null): string {
  if (!v) return "—";
  return new Date(v).toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata", day: "2-digit", month: "short" });
}

function findReq(d: { ai?: { eligibility?: { requirements?: { requirement: string; value?: string | null }[] } | null } | null }, re: RegExp): string | null {
  const reqs = d.ai?.eligibility?.requirements;
  if (!reqs) return null;
  const r = reqs.find((x) => re.test(x.requirement));
  return r ? [r.requirement, r.value].filter(Boolean).join(": ") : null;
}
