/**
 * Deterministic natural-language query parsing (spec #14).
 * AI is only used as an optional fallback client-side; this parser handles the
 * common Indian procurement query patterns offline and instantly.
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

const STATES = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
  "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
  "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
  "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh",
  "Uttarakhand", "West Bengal", "Delhi", "Jammu", "Kashmir", "Ladakh", "Puducherry",
];

const SOURCES: [RegExp, string][] = [
  [/\bgem\b|ge\s?marketplace/i, "gem_bids"],
  [/cppp|epublish|central public procurement/i, "cppp_epublish"],
  [/ireps|railway/i, "ireps"],
];

/** Remove a consumed span so it cannot leak into the keyword stream. */
function cut(text: string, match: RegExpMatchArray | null): string {
  if (!match || match.index === undefined) return text;
  return text.slice(0, match.index) + " " + text.slice(match.index + match[0].length) + " ";
}

function firstNumber(s: string): string {
  return s.match(/[\d.,]+/)![0];
}

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
  const minCr = text.match(
    /(?:above|over|>|more\s+than|min(?:imum)?)\s*(?:₹|rs\.?|inr)?\s*[\d.,]+\s*cr(?:ore)?s?\b/i,
  );
  if (minCr) {
    q.minValue = toNumber(firstNumber(minCr[0])) * 1e7;
    text = cut(text, minCr);
  }
  if (!q.minValue) {
    const minL = text.match(
      /(?:above|over|>|more\s+than|min(?:imum)?)\s*(?:₹|rs\.?|inr)?\s*[\d.,]+\s*(?:lakh|lac)s?\b/i,
    );
    if (minL) {
      q.minValue = toNumber(firstNumber(minL[0])) * 1e5;
      text = cut(text, minL);
    }
  }
  const maxCr = text.match(
    /(?:below|under|<|less\s+than|max(?:imum)?)\s*(?:₹|rs\.?|inr)?\s*[\d.,]+\s*cr(?:ore)?s?\b/i,
  );
  if (maxCr) {
    q.maxValue = toNumber(firstNumber(maxCr[0])) * 1e7;
    text = cut(text, maxCr);
  }

  // ---- state -----------------------------------------------------------------
  for (const st of STATES) {
    const re = new RegExp(`\\b${st.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i");
    const m = text.match(re);
    if (m) {
      q.state = st;
      text = cut(text, m);
      break;
    }
  }

  // ---- source hints ------------------------------------------------------------
  for (const [re, source] of SOURCES) {
    if (re.test(text)) {
      q.sourceHint = source;
      break;
    }
  }

  // ---- residual filler never belongs in keyword search -------------------------
  q.keywords = text
    .replace(/\b(closing|open|with|for|from|the|and|of|in)\b/gi, " ")
    .replace(/\b\d+(?:[.,]\d+)*\b/g, " ") // bare numbers left over from consumed phrases
    .replace(/\b(cr|lakh|lac|rs)\b/gi, " ") // stray unit fragments
    .replace(/\s+/g, " ")
    .trim();
  return q;
}

function toNumber(s: string): number {
  return parseFloat(s.replace(/,/g, ""));
}
