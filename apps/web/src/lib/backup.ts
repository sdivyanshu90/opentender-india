import type { CompanyProfile, SavedSearch, Workspace, WorkflowStatus } from "./store";

/**
 * Workspace backup restore (spec #20). The file is untrusted input: it is
 * parsed as JSON only, every field is shape-checked and copied, and nothing in
 * it is ever executed or rendered as HTML.
 */

export const MAX_BACKUP_BYTES = 5_000_000;
const STATUSES: readonly string[] = ["new", "reviewing", "interested", "bid", "skip", "submitted"];

export interface ParsedBackup {
  bookmarks: Workspace["bookmarks"];
  savedSearches: SavedSearch[];
  profile: CompanyProfile | null;
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const str = (v: unknown, max: number): string | null => (typeof v === "string" && v.length <= max ? v : null);
const strList = (v: unknown): string[] | null =>
  Array.isArray(v) && v.length <= 200 && v.every((x) => typeof x === "string" && x.length <= 200) ? (v as string[]) : null;
const num = (v: unknown): number | undefined => (typeof v === "number" && Number.isFinite(v) && v >= 0 ? v : undefined);

export function parseBackup(text: string): ParsedBackup {
  if (text.length > MAX_BACKUP_BYTES) throw new Error("File is too large to be a workspace backup.");
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    throw new Error("Not a valid JSON file.");
  }
  if (!isObj(raw) || !("bookmarks" in raw || "savedSearches" in raw || "profile" in raw))
    throw new Error("This does not look like an OpenTender workspace backup.");

  const bookmarks: ParsedBackup["bookmarks"] = {};
  if (raw.bookmarks != null) {
    if (!isObj(raw.bookmarks)) throw new Error("Backup bookmarks are malformed.");
    for (const [id, b] of Object.entries(raw.bookmarks)) {
      if (id.length > 200 || !isObj(b) || num(b.at) == null) continue;
      const status = typeof b.status === "string" && STATUSES.includes(b.status) ? (b.status as WorkflowStatus) : "new";
      bookmarks[id] = { at: b.at as number, status, notes: str(b.notes, 5000) ?? "" };
    }
  }

  const savedSearches: SavedSearch[] = [];
  if (raw.savedSearches != null) {
    if (!Array.isArray(raw.savedSearches)) throw new Error("Backup saved searches are malformed.");
    for (const s of raw.savedSearches) {
      if (!isObj(s)) continue;
      const id = str(s.id, 100);
      const name = str(s.name, 200);
      const query = str(s.query, 2000);
      if (!id || !name || query == null) continue;
      savedSearches.push({ id, name, query, createdAt: num(s.createdAt) ?? Date.now() });
    }
  }

  let profile: CompanyProfile | null = null;
  if (isObj(raw.profile)) {
    const p = raw.profile;
    const lists = ["industries", "productCategories", "services", "preferredStates", "certifications", "pastProjectKeywords"] as const;
    const out: Record<string, unknown> = {};
    let ok = true;
    for (const k of lists) {
      const l = strList(p[k] ?? []);
      if (!l) ok = false;
      else out[k] = l;
    }
    if (ok)
      profile = {
        ...(out as unknown as CompanyProfile),
        msme: p.msme === true,
        startup: p.startup === true,
        minContractSize: num(p.minContractSize),
        maxContractSize: num(p.maxContractSize),
        turnover: num(p.turnover),
        yearsInBusiness: num(p.yearsInBusiness),
      };
  }
  return { bookmarks, savedSearches, profile };
}

/** Merge: existing data is kept unless the backup's bookmark is newer; a profile is only adopted when none exists. */
export function mergeBackup(cur: Workspace, b: ParsedBackup): Workspace {
  const bookmarks = { ...cur.bookmarks };
  for (const [id, entry] of Object.entries(b.bookmarks)) {
    if (!bookmarks[id] || bookmarks[id].at < entry.at) bookmarks[id] = entry;
  }
  const seen = new Set(cur.savedSearches.map((s) => s.id));
  const savedSearches = [...cur.savedSearches];
  for (const s of b.savedSearches) {
    if (seen.has(s.id) || savedSearches.some((x) => x.query === s.query && x.name === s.name)) continue;
    seen.add(s.id);
    savedSearches.push(s);
  }
  return { ...cur, bookmarks, savedSearches, profile: cur.profile ?? b.profile };
}
