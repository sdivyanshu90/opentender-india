/**
 * Deterministic natural-language query parsing (spec #14).
 * AI is only used as an optional fallback client-side; this parser handles the
 * common Indian procurement query patterns offline and instantly.
 *
 * Invariant: only text spans the parser consumed are removed. Everything else
 * (tender numbers such as "GEM/2026/B/8075653", "RSRDCC NIT 406/2026-27", bare
 * digits) survives verbatim into `keywords`.
 */

export interface ParsedQuery {
  keywords: string;
  state?: string;
  category?: string;
  minValue?: number;
  maxValue?: number;
  closingWithinDays?: number;
  closingThisMonth?: boolean;
  sourceHint?: string;
}

/** Canonical state names as stored in the dataset. */
const STATES = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
  "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
  "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
  "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh",
  "Uttarakhand", "West Bengal", "Delhi", "Jammu and Kashmir", "Ladakh", "Puducherry",
  "Chandigarh", "Lakshadweep", "Andaman and Nicobar Islands",
];

/** [regex source, canonical name]; longer/more specific patterns first. */
const STATE_PATTERNS: [string, string][] = [
  [String.raw`jammu\s*(?:and|&)\s*kashmir`, "Jammu and Kashmir"],
  [String.raw`j\s?&\s?k`, "Jammu and Kashmir"],
  [String.raw`jammu`, "Jammu and Kashmir"],
  [String.raw`kashmir`, "Jammu and Kashmir"],
  [String.raw`andaman\s*(?:and|&)\s*nicobar(?:\s+islands)?`, "Andaman and Nicobar Islands"],
  [String.raw`new\s+delhi`, "Delhi"],
  [String.raw`orissa`, "Odisha"],
  [String.raw`pondicherry`, "Puducherry"],
  [String.raw`uttaranchal`, "Uttarakhand"],
  ...STATES.filter((s) => s !== "Jammu and Kashmir" && s !== "Andaman and Nicobar Islands").map(
    (s) => [s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/ /g, String.raw`\s+`), s] as [string, string],
  ),
].map(([src, name]) => [src, name] as [string, string]);

const STATE_RES: [RegExp, string][] = STATE_PATTERNS.map(([src, name]) => [
  new RegExp(String.raw`(^|[^\w/-])(${src})(?![\w/-])`, "i"),
  name,
]);

/** Portal words only count when standalone, so "GEM/2026/B/1" stays a tender number. */
const SOURCES: [RegExp, string][] = [
  [/(^|\s)(?:gem|ge\s?marketplace)(?=\s|$)/i, "gem_bids"],
  [/(^|\s)(?:cppp|epublish|central\s+public\s+procurement)(?=\s|$)/i, "cppp_epublish"],
  [/(^|\s)ireps(?=\s|$)/i, "ireps"],
];

/** Canonical comparison key so "J&K", "Jammu and Kashmir" and case variants agree. */
export function stateKey(s: string | null | undefined): string {
  return (s ?? "").toLowerCase().replace(/&/g, " and ").replace(/\s+/g, " ").trim();
}

/** Remove a consumed span so it cannot leak into the keyword stream. */
function cut(text: string, match: RegExpMatchArray | null): string {
  if (!match || match.index === undefined) return text;
  return text.slice(0, match.index) + " " + text.slice(match.index + match[0].length) + " ";
}

const AMOUNT = String.raw`\s*(?:₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d+)?)\s*(crores?|crs?|lakhs?|lacs?)(?![a-z])`;
const MIN_RE = new RegExp(String.raw`(?:\b(?:above|over|more\s+than|at\s+least|min(?:imum)?)|>=?)` + AMOUNT, "i");
const MAX_RE = new RegExp(String.raw`(?:\b(?:below|under|less\s+than|up\s*to|max(?:imum)?)|<=?)` + AMOUNT, "i");

function amount(m: RegExpMatchArray): number {
  const n = parseFloat(m[1].replace(/,/g, ""));
  return /^cr/i.test(m[2]) ? n * 1e7 : n * 1e5;
}

const FILLER = /(^|\s)(?:closing|open|with|for|from|the|and|of|in)(?=\s|$)/gi;

export function parseQuery(input: string): ParsedQuery {
  const q: ParsedQuery = { keywords: "" };
  let text = ` ${input} `;

  // ---- deadline constraints first (they overlap value phrases) --------------
  const withinDays =
    text.match(/closing\s+within\s+(\d{1,3})\s*days?\b/i) ||
    text.match(/(?:within|next)\s+(\d{1,3})\s*days?\b/i);
  if (withinDays) {
    q.closingWithinDays = parseInt(withinDays[1], 10);
    text = cut(text, withinDays);
  }
  const monthM = text.match(/closing\s+this\s+month|this\s+month\b/i);
  if (monthM) {
    q.closingThisMonth = true;
    text = cut(text, monthM);
  } else {
    const weekM = text.match(/closing\s+this\s+week|this\s+week\b/i);
    if (weekM) {
      q.closingWithinDays = q.closingWithinDays ?? 7;
      text = cut(text, weekM);
    }
  }

  // ---- value constraints ----------------------------------------------------
  const minM = text.match(MIN_RE);
  if (minM) {
    q.minValue = amount(minM);
    text = cut(text, minM);
  }
  const maxM = text.match(MAX_RE);
  if (maxM) {
    q.maxValue = amount(maxM);
    text = cut(text, maxM);
  }

  // ---- state -----------------------------------------------------------------
  for (const [re, name] of STATE_RES) {
    const m = text.match(re);
    if (m && m.index !== undefined) {
      q.state = name;
      // keep the leading boundary character the pattern captured
      const start = m.index + m[1].length;
      text = text.slice(0, start) + " " + text.slice(start + m[2].length) + " ";
      break;
    }
  }

  // ---- source hints ------------------------------------------------------------
  for (const [re, source] of SOURCES) {
    const m = text.match(re);
    if (m) {
      q.sourceHint = source;
      text = cut(text, m);
      break;
    }
  }

  // ---- residual filler never belongs in keyword search -------------------------
  // Numbers, slashes and units that were NOT consumed above are real keywords.
  q.keywords = text.replace(FILLER, " ").replace(/\s+/g, " ").trim();
  return q;
}
