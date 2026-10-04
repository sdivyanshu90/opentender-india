import { describe, expect, it } from "vitest";
import { parseQuery } from "./nlq";

describe("parseQuery (spec #14)", () => {
  it("parses the flagship query without leaking consumed phrases", () => {
    const q = parseQuery("solar EPC Maharashtra above ₹1 Cr closing within 30 days");
    expect(q.keywords).toBe("solar EPC");
    expect(q.state).toBe("Maharashtra");
    expect(q.minValue).toBe(1e7);
    expect(q.closingWithinDays).toBe(30);
  });

  it("handles lakh bounds and this week", () => {
    const q = parseQuery("road works Gujarat above ₹50 lakh closing this week");
    expect(q.minValue).toBe(5_000_000);
    expect(q.closingWithinDays).toBe(7);
    expect(q.state).toBe("Gujarat");
    expect(q.keywords).toBe("road works");
  });

  it("keeps GeM bid numbers and bare digits as keywords", () => {
    expect(parseQuery("GEM/2026/B/8075653").keywords).toBe("GEM/2026/B/8075653");
    expect(parseQuery("GEM/2026/B/8075653").sourceHint).toBeUndefined();
    expect(parseQuery("8075653").keywords).toBe("8075653");
    expect(parseQuery("2026_LSGD_875715_6").keywords).toBe("2026_LSGD_875715_6");
  });

  it("keeps NIT references intact", () => {
    const q = parseQuery("RSRDCC NIT 406/2026-27");
    expect(q.keywords).toBe("RSRDCC NIT 406/2026-27");
    expect(q.minValue).toBeUndefined();
  });

  it("only strips the numbers a value phrase consumed", () => {
    const q = parseQuery("road 4075 under 50 lakh");
    expect(q.maxValue).toBe(5_000_000);
    expect(q.keywords).toBe("road 4075");
  });

  it("parses under/below crore and lakh as maxValue", () => {
    expect(parseQuery("bridge works below ₹2 crore").maxValue).toBe(2e7);
    expect(parseQuery("under Rs. 1.5 cr repair").maxValue).toBe(1.5e7);
    expect(parseQuery("repair under 10 lakh").keywords).toBe("repair");
    expect(parseQuery("above 5 lakh below 20 lakh")).toMatchObject({ minValue: 5e5, maxValue: 2e6, keywords: "" });
  });

  it("maps Jammu and Kashmir variants to the canonical state", () => {
    for (const s of ["Jammu and Kashmir", "J&K", "Jammu & Kashmir", "kashmir"]) {
      const q = parseQuery(`road repair ${s}`);
      expect(q.state).toBe("Jammu and Kashmir");
      expect(q.keywords).toBe("road repair");
    }
  });

  it("detects a state typed alone and keeps the rest", () => {
    const q = parseQuery("Kerala");
    expect(q.state).toBe("Kerala");
    expect(q.keywords).toBe("");
  });

  it("recognises standalone portal words only", () => {
    expect(parseQuery("GeM laptop").sourceHint).toBe("gem_bids");
    expect(parseQuery("GeM laptop").keywords).toBe("laptop");
    expect(parseQuery("IREPS signalling tenders").sourceHint).toBe("ireps");
    expect(parseQuery("railway track").sourceHint).toBeUndefined();
  });

  it("plain keyword queries pass through", () => {
    expect(parseQuery("hospital equipment maintenance").keywords).toBe(
      "hospital equipment maintenance",
    );
  });
});
