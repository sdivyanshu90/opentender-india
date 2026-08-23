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

  it("plain keyword queries pass through", () => {
    expect(parseQuery("hospital equipment maintenance").keywords).toBe(
      "hospital equipment maintenance",
    );
  });
});
