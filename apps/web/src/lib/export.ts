/** Local .ics generation (spec #65) and safe CSV export (spec #66). */

function icsEscape(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");
}

function toIcsStamp(d: Date): string {
  // floating local time is acceptable; portals publish IST times
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}` +
    `T${pad(d.getHours())}${pad(d.getMinutes())}00`
  );
}

export function buildIcs(events: { uid: string; title: string; start: Date; url?: string }[]): Blob {
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//OpenTender India//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
  ];
  for (const ev of events) {
    lines.push(
      "BEGIN:VEVENT",
      `UID:${ev.uid}@opentender`,
      `DTSTAMP:${toIcsStamp(new Date())}`,
      `DTSTART:${toIcsStamp(ev.start)}`,
      `SUMMARY:${icsEscape(ev.title)}`,
      ...(ev.url ? [`URL:${ev.url}`] : []),
      "END:VEVENT",
    );
  }
  lines.push("END:VCALENDAR");
  return new Blob([lines.join("\r\n")], { type: "text/calendar;charset=utf-8" });
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** CSV with formula-injection protection (=, +, -, @ prefixes neutralized). */
export function buildCsv(rows: Record<string, unknown>[], columns: string[]): Blob {
  const esc = (v: unknown): string => {
    let s = v == null ? "" : String(v);
    if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
    if (/[",\n\r]/.test(s)) s = `"${s.replace(/"/g, '""')}"`;
    return s;
  };
  const head = columns.join(",");
  const body = rows.map((r) => columns.map((c) => esc(r[c])).join(",")).join("\r\n");
  return new Blob(["\uFEFF" + head + "\r\n" + body], { type: "text/csv;charset=utf-8" });
}

export const TENDER_EXPORT_COLUMNS = [
  "id",
  "tender_number",
  "title",
  "authority",
  "state",
  "category",
  "type",
  "value",
  "emd",
  "fee",
  "published_at",
  "closing_at",
  "status",
  "source",
  "corrigenda_count",
  "url",
] as const;

type ExportableTender = { [K in (typeof TENDER_EXPORT_COLUMNS)[number]]?: unknown };

/** Flat export rows; undisclosed values stay empty (null), never 0. */
export function tenderExportRows(docs: ExportableTender[]): Record<string, unknown>[] {
  return docs.map((d) => Object.fromEntries(TENDER_EXPORT_COLUMNS.map((c) => [c, d[c] ?? null])));
}

export function buildTendersCsv(docs: ExportableTender[]): Blob {
  return buildCsv(tenderExportRows(docs), [...TENDER_EXPORT_COLUMNS]);
}

export function buildTendersJson(docs: ExportableTender[]): Blob {
  return new Blob([JSON.stringify(tenderExportRows(docs), null, 1)], { type: "application/json" });
}
