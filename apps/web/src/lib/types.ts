/** Canonical tender document as shipped by the pipeline (data/indexes/search-docs.json.gz). */

export interface EvidenceCitation {
  document_title: string;
  page?: number | null;
  clause?: string | null;
  quote?: string | null;
}

export interface EvidenceField {
  value: string;
  confidence: number;
  citation?: EvidenceCitation | null;
}

export interface AISummary {
  opportunity?: EvidenceField;
  buyer?: EvidenceField;
  contract_value?: EvidenceField;
  deadline?: EvidenceField;
  eligibility?: EvidenceField[];
  critical_clauses?: EvidenceField[];
  overall_confidence?: number;
}

export interface EligibilityRequirement {
  requirement: string;
  operator?: string | null;
  value?: string | null;
  period?: string | null;
  mandatory?: boolean;
  source_page?: number | null;
  source_clause?: string | null;
  confidence?: number;
}

export interface RiskFlag {
  label: "INFO" | "REVIEW" | "IMPORTANT" | "CRITICAL";
  risk: string;
  basis: string;
}

export interface TenderDoc {
  id: string;
  title: string | null;
  authority: string | null;
  state: string | null;
  /** detail field: lives in data/details shards in production (see lib/details.ts) */
  city?: string | null;
  category: string | null;
  type: string | null;
  value: number | null;
  emd: number | null;
  fee?: number | null;
  published_at: string | null;
  closing_at: string | null;
  pre_bid_meeting_at?: string | null;
  /** detail shard only (not in the search index) */
  opening_at?: string | null;
  status: string;
  source: string;
  portal?: string;
  ref: string | null;
  tender_number: string | null;
  url: string;
  first_seen_at: string;
  /** last time the pipeline observed the tender on its portal (ISO); absent in older datasets */
  last_seen_at?: string | null;
  /** pipeline emits `source_url`; legacy/dev fixtures used `url` */
  documents?: { title: string; source_url?: string | null; url?: string | null; type?: string | null }[];
  corrigenda_count: number;
  award?: { winning_bidder?: string | null; award_value?: number | null } | null;
  ai?: {
    summary?: AISummary | null;
    eligibility?: { requirements?: EligibilityRequirement[]; exemptions_noted?: string[] } | null;
    risk?: { flags?: RiskFlag[] } | null;
  };
  /** present only on dev fixture data */
  _fixture?: boolean;
}

export interface SourceHealth {
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

export interface DatasetManifest {
  generated_at: string;
  total_tenders: number;
  shards: { source: string; file: string; count: number; sha256: string }[];
}
