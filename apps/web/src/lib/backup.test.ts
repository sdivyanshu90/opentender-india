import { describe, expect, it } from "vitest";
import { emptyWorkspace } from "./store";
import { mergeBackup, parseBackup } from "./backup";

describe("workspace backup restore", () => {
  it("rejects non-backup input", () => {
    expect(() => parseBackup("nope")).toThrow();
    expect(() => parseBackup("[1,2]")).toThrow();
    expect(() => parseBackup('{"hello":1}')).toThrow();
  });

  it("keeps only well-formed entries", () => {
    const b = parseBackup(
      JSON.stringify({
        bookmarks: { a: { at: 5, status: "bid", notes: "n" }, b: { at: "x" }, c: 7 },
        savedSearches: [{ id: "1", name: "Roads", query: "q=road" }, { id: 2 }],
        profile: { industries: ["roads"], msme: true },
      }),
    );
    expect(Object.keys(b.bookmarks)).toEqual(["a"]);
    expect(b.savedSearches).toHaveLength(1);
    expect(b.profile?.industries).toEqual(["roads"]);
  });

  it("merges without duplicating or overwriting a profile", () => {
    const cur = emptyWorkspace();
    cur.bookmarks.a = { at: 10, status: "new", notes: "mine" };
    cur.savedSearches.push({ id: "1", name: "Roads", query: "q=road", createdAt: 1 });
    const b = parseBackup(
      JSON.stringify({
        bookmarks: { a: { at: 5, status: "bid", notes: "old" }, z: { at: 1, status: "skip", notes: "" } },
        savedSearches: [{ id: "9", name: "Roads", query: "q=road" }, { id: "2", name: "Solar", query: "q=solar" }],
      }),
    );
    const m = mergeBackup(cur, b);
    expect(m.bookmarks.a.notes).toBe("mine");
    expect(m.bookmarks.z.status).toBe("skip");
    expect(m.savedSearches.map((s) => s.id)).toEqual(["1", "2"]);
  });
});
