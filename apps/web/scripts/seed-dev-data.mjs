#!/usr/bin/env node
/**
 * Generates clearly-labelled synthetic dev fixtures (spec #98: fixtures must be
 * visibly identifiable in development). NEVER used in production builds.
 */
import { writeFileSync } from "node:fs";

const now = Date.now();
const DAY = 86_400_000;
const iso = (offsetDays, hour = 12) => {
  const d = new Date(now + offsetDays * DAY);
  d.setUTCHours(hour - 5, 30, 0, 0);
  return d.toISOString();
};

const mk = (
  n,
  title,
  authority,
  state,
  category,
  valueCr,
  emdCr,
  closeInDays,
  source,
  extra = {},
) => ({
  id: `fixture${String(n).padStart(4, "0")}`,
  title,
  authority,
  state,
  city: null,
  category,
  type: "works",
  value: Math.round(valueCr * 1e7),
  emd: Math.round(emdCr * 1e7),
  fee: 5900,
  published_at: iso(-3),
  closing_at: iso(closeInDays, 15),
  opening_at: iso(closeInDays + 2, 11),
  pre_bid_meeting_at: iso(2, 12),
  status: closeInDays > 0 ? "active" : "closed",
  source,
  portal: `https://${source}.example.gov.in`,
  ref: `REF/2026/${1000 + n}`,
  tender_number: `2026_TEST_${900000 + n}_1`,
  url: `https://${source}.example.gov.in/tender/${n}`,
  first_seen_at: iso(-2),
  documents: [
    { title: "NIT Document.pdf", url: `https://${source}.example.gov.in/docs/${n}/nit.pdf`, type: "nit" },
    { title: "BOQ.xls", url: `https://${source}.example.gov.in/docs/${n}/boq.xls`, type: "boq" },
  ],
  corrigenda_count: extra.corrigenda ?? 0,
  award: null,
  ai: extra.ai ?? null,
});

const docs = [
  mk(1, "Design and construction of 25 MW grid-connected solar photovoltaic power plant at Solapur", "Maharashtra Energy Development Agency", "Maharashtra", "Solar Power Systems", 112.5, 2.24, 12, "cppp_epublish", {
    corrigenda: 1,
    ai: {
      summary: {
        opportunity: { value: "25 MW grid-connected solar PV plant including five-year O&M", confidence: 0.92, citation: { document_title: "NIT Document.pdf", page: 4 } },
        buyer: { value: "Maharashtra Energy Development Agency (MEDA)", confidence: 0.99 },
        contract_value: { value: "1125000000", confidence: 0.85 },
        deadline: { value: "bid submission closes in 12 days", confidence: 0.9 },
        overall_confidence: 0.88,
      },
      eligibility: {
        requirements: [
          { requirement: "Average annual turnover", operator: ">=", value: "224000000", period: "last 3 financial years", mandatory: true, source_page: 38, source_clause: "4.2", confidence: 0.94 },
          { requirement: "Similar completed work", operator: ">=", value: "one single work of 20 MW or two works of 10 MW", period: "last 7 years", mandatory: true, source_page: 37, source_clause: "4.1", confidence: 0.91 },
          { requirement: "ISO 9001 certification", operator: "present", value: null, period: null, mandatory: true, source_page: 41, source_clause: "6.3", confidence: 0.72 },
        ],
        exemptions_noted: ["EMD exemption for MSMEs registered with NSIC"],
      },
      risk: {
        flags: [
          { label: "IMPORTANT", risk: "High performance security (5%) with aggressive commissioning schedule", basis: "Clause 8.1 requires commissioning within 9 months; delay damages 0.5%/week capped at 5%." },
          { label: "REVIEW", risk: "Tariff-linked payment security depends on state discom health", basis: "PSA annexure references MSEDCL as offtaker." },
        ],
      },
    },
  }),
  mk(2, "Supply installation testing and commissioning of 11 kV HT lines and distribution transformers", "Madhya Pradesh Poorv Kshetra Vidyut Vitaran", "Madhya Pradesh", "Electrical Works", 24.5, 0.49, 4, "gepnic_madhya_pradesh"),
  mk(3, "Comprehensive maintenance of HVAC systems at district hospital for three years", "Kerala Medical Services Corporation", "Kerala", "Maintenance Services", 3.2, 0.064, 21, "gepnic_kerala"),
  mk(4, "Widening and strengthening of SH-98 from km 14 to km 32 (EPC mode)", "Rajasthan State Highways Development Corporation", "Rajasthan", "Road Works", 187.4, 3.74, 26, "gepnic_rajasthan"),
  mk(5, "Procurement of 50000 numbers of smart electricity meters under RDSS", "Jammu & Kashmir Power Distribution Corporation", "Jammu and Kashmir", "Smart Meters", 65.0, 1.3, 18, "gepnic_jammu_kashmir", { corrigenda: 2 }),
  mk(6, "Construction of two-lane bridge across river Chandrabhaga including approaches", "Uttarakhand Public Works Department", "Uttarakhand", "Bridge Works", 48.9, 0.97, 33, "gepnic_uttarakhand"),
  mk(7, "Reverse auction for annual rate contract of desktop computers", "GeM — Ministry of Electronics and IT", null, "IT Hardware", 2.1, 0.042, 6, "gem_bids"),
  mk(8, "Manpower outsourcing services for airport operations support staff", "Airports Authority of India", "Delhi", "Manpower Services", 15.6, 0.31, 9, "cppp_epublish"),
  mk(9, "Annual operation and maintenance of sewage treatment plant 45 MLD", "Bharat Electronics Ltd township", null, "O&M Services", 8.4, 0.168, 15, "gepnic_bel"),
  mk(10, "Design supply and erection of 220/66 kV GIS substation at Nashik MIDC", "Maharashtra State Electricity Transmission Company", "Maharashtra", "Substation Works", 94.2, 1.88, 40, "cppp_epublish"),
];

writeFileSync(
  "public/data/dev-fixtures.json",
  JSON.stringify({ generated_at: new Date().toISOString(), _synthetic: true, docs }, null, 1),
);
console.log(`wrote ${docs.length} labelled fixture tenders to public/data/dev-fixtures.json`);
