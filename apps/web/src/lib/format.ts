/** India-specific formatting (spec #71). Raw numbers in; display strings out. */

export function formatINR(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatINRCompact(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  if (value >= 1e7) return `₹${trimZeros(value / 1e7)} Cr`;
  if (value >= 1e5) return `₹${trimZeros(value / 1e5)} L`;
  return formatINR(value);
}

function trimZeros(n: number): string {
  const s = n.toFixed(2);
  return s.endsWith(".00") ? s.slice(0, -3) : s.replace(/0$/, "");
}

const ist = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const istTime = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  hour: "2-digit",
  minute: "2-digit",
  hour12: true,
});

export function parseISO(s: string | null | undefined): Date | null {
  if (!s) return null;
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDate(s: string | null | undefined): string {
  const d = parseISO(s);
  return d ? ist.format(d) : "—";
}

export function formatDateTime(s: string | null | undefined): string {
  const d = parseISO(s);
  if (!d) return "—";
  return `${ist.format(d)}, ${istTime.format(d)}`;
}

const istDay = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Kolkata",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/** Calendar day in IST as YYYY-MM-DD (never use UTC slices: India is UTC+5:30). */
export function istDateKey(v: Date | string | number | null | undefined): string | null {
  if (v == null) return null;
  const d = v instanceof Date ? v : new Date(v);
  return Number.isNaN(d.getTime()) ? null : istDay.format(d);
}

/** Last millisecond of the current IST month. */
export function istMonthEnd(now: Date): number {
  const [y, m] = istDay.format(now).split("-").map(Number);
  return Date.UTC(y, m, 1) - 19_800_000 - 1;
}

/** Tenders first seen in the last 48 hours count as new. */
export const NEW_WINDOW_MS = 48 * 3_600_000;

export function isRecentlyDiscovered(firstSeen: string | null | undefined, now = Date.now()): boolean {
  const d = parseISO(firstSeen);
  if (!d) return false;
  const age = now - d.getTime();
  return age >= -3_600_000 && age <= NEW_WINDOW_MS;
}

/** "Dept › District › Office" (also accepts the legacy "||" separator). */
export function authorityParts(a: string | null | undefined): string[] {
  if (!a) return [];
  return a
    .split(/\s*(?:›|\|\|+|\|)\s*/)
    .map((p) => p.trim())
    .filter(Boolean);
}

export function formatAuthority(a: string | null | undefined): string {
  return authorityParts(a).join(" › ");
}

/** Days remaining until a deadline (negative = passed). */
export function daysRemaining(s: string | null | undefined): number | null {
  const d = parseISO(s);
  if (!d) return null;
  return Math.ceil((d.getTime() - Date.now()) / 86_400_000);
}

export function relativeDeadline(s: string | null | undefined): string {
  const days = daysRemaining(s);
  if (days == null) return "no deadline";
  if (days < 0) return `closed ${-days}d ago`;
  if (days === 0) return "closes today";
  if (days === 1) return "closes tomorrow";
  return `${days} days left`;
}

export function timeAgo(s: string | null | undefined): string {
  const d = parseISO(s);
  if (!d) return "";
  const secs = Math.floor((Date.now() - d.getTime()) / 1000);
  if (secs < 90) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}
