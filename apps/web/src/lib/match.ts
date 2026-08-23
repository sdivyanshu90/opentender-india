/**
 * Local company-profile matching (spec #20). Fully deterministic, fully local:
 * profile data never leaves the device in "local"/"public" privacy modes.
 */

import type { CompanyProfile } from "./store";
import type { TenderDoc } from "./types";

export interface MatchResult {
  score: number; // 0-100
  reasons: string[];
}

export function matchTender(tender: TenderDoc, profile: CompanyProfile | null): MatchResult {
  if (!profile) return { score: 0, reasons: [] };
  const reasons: string[] = [];
  let score = 0;

  // industry / category relevance (max 30)
  const cat = (tender.category ?? "").toLowerCase();
  const title = (tender.title ?? "").toLowerCase();
  const interests = [...profile.industries, ...profile.productCategories, ...profile.services].map((s) => s.toLowerCase());
  const hit = interests.find((i) => i && (cat.includes(i) || title.includes(i)));
  if (hit) {
    score += 30;
    reasons.push(`Matches your interest "${hit}"`);
  }

  // geographic relevance (max 20)
  if (profile.preferredStates.length === 0) {
    score += 10;
  } else if (tender.state && profile.preferredStates.includes(tender.state)) {
    score += 20;
    reasons.push(`In your preferred state (${tender.state})`);
  }

  // contract size fit (max 25)
  if (tender.value != null) {
    const min = profile.minContractSize ?? 0;
    const max = profile.maxContractSize ?? Infinity;
    if (tender.value >= min && tender.value <= max) {
      score += 25;
      reasons.push("Contract size fits your range");
    } else if (tender.value < min) {
      reasons.push("Below your minimum contract size");
    } else {
      reasons.push("Above your maximum contract size");
    }
  }

  // certification fit (max 15): unknown certifications required -> neutral;
  // MSME exemption noted + MSME status = bonus
  if (profile.msme || profile.startup) {
    score += 7;
    reasons.push(profile.msme ? "MSME status may earn exemptions" : "Startup status may earn exemptions");
  }

  // deadline feasibility (max 10)
  if (tender.closing_at) {
    const days = (new Date(tender.closing_at).getTime() - Date.now()) / 86_400_000;
    if (days >= 7) {
      score += 10;
    } else if (days >= 3) {
      score += 5;
      reasons.push("Deadline is tight (<7 days)");
    } else if (days >= 0) {
      reasons.push("Closes very soon — review immediately");
    }
  }

  return { score: Math.min(100, Math.round(score)), reasons };
}
