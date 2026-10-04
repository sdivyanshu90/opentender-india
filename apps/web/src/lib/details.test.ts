import { describe, expect, it } from "vitest";
import { mergeDetails, shardKey } from "./details";
import type { TenderDoc } from "./types";

const base = { id: "9FA3c0ffee", title: "t", value: null } as unknown as TenderDoc;

describe("detail shards", () => {
  it("keys by first two chars, lowercased", () => {
    expect(shardKey("9FA3abc")).toBe("9f");
    expect(shardKey("fixture0001")).toBe("fi");
  });

  it("merges detail fields without overriding present ones", () => {
    const m = mergeDetails(base, { documents: [{ title: "d" }], portal: "p", fee: 5, city: "X" });
    expect(m.documents).toHaveLength(1);
    expect(m.fee).toBe(5);
    const keep = mergeDetails({ ...base, fee: 1 }, { fee: 9 });
    expect(keep.fee).toBe(1);
  });

  it("is a no-op without details", () => {
    expect(mergeDetails(base, null)).toBe(base);
  });
});
