import { daysRemaining, relativeDeadline } from "../lib/format";

export function SourceBadge({ source }: { source: string }) {
  const label = source.replace(/_/g, " ").replace(/^gepnic /, "").toUpperCase();
  return (
    <span className="chip border-ink-300 bg-white font-mono text-[10px] tracking-wide" title={`Source portal: ${source}`}>
      {label}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active: "border-emerald-200 bg-emerald-50 text-emerald-700",
    awarded: "border-sky-200 bg-sky-50 text-sky-700",
    closed: "border-ink-200 bg-ink-100 text-ink-500",
    cancelled: "border-red-200 bg-red-50 text-red-700",
    retendered: "border-violet-200 bg-violet-50 text-violet-700",
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium capitalize ${styles[status] ?? styles.closed}`}>
      {status}
    </span>
  );
}

export function DeadlineBadge({ closingAt }: { closingAt: string | null }) {
  const days = daysRemaining(closingAt);
  let cls = "border-ink-200 bg-ink-100 text-ink-600";
  if (days != null) {
    if (days < 0) cls = "border-ink-200 bg-ink-100 text-ink-400";
    else if (days <= 3) cls = "border-red-200 bg-red-50 text-red-700";
    else if (days <= 7) cls = "border-amber-200 bg-amber-50 text-amber-700";
    else cls = "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}>
      ⏱ {relativeDeadline(closingAt)}
    </span>
  );
}

export function NewBadge() {
  return (
    <span className="rounded-full border border-accent-200 bg-accent-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-accent-700">
      New
    </span>
  );
}

export function ChangedBadge({ count }: { count: number }) {
  if (count === 0) return null;
  return (
    <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-700">
      ⟳ {count} corrigendum{count > 1 ? "da" : ""}
    </span>
  );
}

export function MatchScore({ score, reasons }: { score: number; reasons: string[] }) {
  if (score <= 0) return <span className="text-xs text-ink-300">—</span>;
  const tone = score >= 70 ? "text-emerald-600" : score >= 40 ? "text-amber-600" : "text-ink-400";
  return (
    <span className="group relative inline-flex cursor-help items-baseline gap-0.5">
      <span className={`text-sm font-bold ${tone}`}>{score}%</span>
      <span className="text-[10px] uppercase tracking-wide text-ink-400">match</span>
      <span className="pointer-events-none absolute bottom-full left-0 z-20 mb-1 hidden w-56 rounded-md border border-ink-200 bg-white p-2 text-xs leading-snug text-ink-600 shadow-lg group-hover:block">
        {reasons.length ? reasons.map((r, i) => <div key={i}>• {r}</div>) : "Set up your profile to see why this matches."}
      </span>
    </span>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="card mx-auto mt-16 max-w-md p-8 text-center">
      <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-ink-100 text-ink-400">⌕</div>
      <p className="font-semibold text-ink-800">{title}</p>
      {hint && <p className="mt-1 text-sm text-ink-500">{hint}</p>}
    </div>
  );
}

export function SkeletonRows({ rows = 8 }: { rows?: number }) {
  return (
    <div className="space-y-2 p-4" aria-hidden>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-12 animate-pulse rounded-md bg-ink-100" />
      ))}
    </div>
  );
}
