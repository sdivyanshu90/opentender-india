import { useEffect, useState } from "react";

interface SourceRow {
  status: string;
  last_success?: string | null;
  last_attempt?: string | null;
  discovered_last_run?: number | null;
  new_last_run?: number | null;
  changed_last_run?: number | null;
  http_failures_total?: number;
  parser_failures_total?: number;
  latency_ms?: number | null;
  parser_version?: string | null;
}

/** Public source-health dashboard (spec #48). Data: status/sources.json. */
export default function SourcesPage() {
  const [sources, setSources] = useState<Record<string, SourceRow> | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);

  useEffect(() => {
    fetch("/data/status-sources.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("no status file"))))
      .then((j) => {
        setSources(j.sources);
        setGeneratedAt(j.generated_at);
      })
      .catch(() => setSources(null));
  }, []);

  const declared = [
    { id: "cppp_epublish", name: "CPPP ePublishing", region: "Central", note: "CAPTCHA-free closing-date window; listings gated" },
    { id: "gem_bids", name: "GeM BidPlus", region: "All-India", note: "Public bid JSON + public documents; no official API" },
    { id: "gepnic_rajasthan", name: "Rajasthan eProcurement", region: "Rajasthan", note: "" },
    { id: "gepnic_kerala", name: "Kerala eTenders", region: "Kerala", note: "" },
    { id: "gepnic_madhya_pradesh", name: "MP Tenders", region: "Madhya Pradesh", note: "" },
    { id: "gepnic_uttarakhand", name: "Uttarakhand eProcurement", region: "Uttarakhand", note: "" },
    { id: "gepnic_jammu_kashmir", name: "J&K eTenders", region: "Jammu & Kashmir", note: "" },
    { id: "gepnic_bel", name: "BEL eProcurement", region: "PSU (MoD)", note: "" },
    { id: "mahatenders", name: "MahaTenders", region: "Maharashtra", note: "robots.txt disallows crawling — adapter disabled by default" },
  ];

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <h1 className="text-lg font-bold text-ink-900">Sources &amp; system health</h1>
      <p className="mt-0.5 text-sm text-ink-500">
        Coverage is published honestly. If a portal is stale or degraded you will see it here first.
        {generatedAt && ` Status generated ${new Date(generatedAt).toLocaleString("en-IN")}.`}
      </p>

      <div className="card mt-4 overflow-x-auto">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b border-ink-200 bg-ink-100/60 text-left text-xs font-semibold uppercase tracking-wide text-ink-500">
              <th className="px-4 py-2.5">Source</th>
              <th className="px-3 py-2.5">Region</th>
              <th className="px-3 py-2.5">State</th>
              <th className="px-3 py-2.5">Last success</th>
              <th className="px-3 py-2.5 text-right">Discovered</th>
              <th className="px-3 py-2.5 hidden md:table-cell">Notes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-100">
            {declared.map((s) => {
              const health = sources?.[s.id];
              const status = health?.status ?? "PENDING";
              return (
                <tr key={s.id}>
                  <td className="px-4 py-2.5 font-medium text-ink-800">{s.name}</td>
                  <td className="px-3 py-2.5 text-ink-600">{s.region}</td>
                  <td className="px-3 py-2.5"><StatusChip status={status} /></td>
                  <td className="px-3 py-2.5 text-xs text-ink-500">
                    {health?.last_success ? new Date(health.last_success).toLocaleString("en-IN") : "—"}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-ink-700">{health?.discovered_last_run ?? "—"}</td>
                  <td className="hidden px-3 py-2.5 text-xs text-ink-400 md:table-cell">{s.note}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-4 rounded-lg border border-ink-200 bg-white p-3 text-xs leading-relaxed text-ink-500">
        OpenTender India crawls politely: descriptive User-Agent, conservative delays, no CAPTCHA bypass, no login
        automation. Sources marked POLICY_RESTRICTED stay disabled until operators explicitly opt in locally after
        reviewing each portal’s terms.
      </p>
    </div>
  );
}

function StatusChip({ status }: { status: string }) {
  const map: Record<string, string> = {
    ACTIVE: "border-emerald-200 bg-emerald-50 text-emerald-700",
    EXPERIMENTAL: "border-sky-200 bg-sky-50 text-sky-700",
    DEGRADED: "border-amber-200 bg-amber-50 text-amber-700",
    TEMPORARILY_BROKEN: "border-red-200 bg-red-50 text-red-700",
    POLICY_RESTRICTED: "border-violet-200 bg-violet-50 text-violet-700",
    PENDING: "border-ink-200 bg-ink-100 text-ink-400",
  };
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-full border px-2 py-0.5 font-mono text-[10px] font-semibold ${map[status] ?? map.PENDING}`}>
      {status}
    </span>
  );
}
