import { useRef, useState } from "react";
import { MAX_BACKUP_BYTES, mergeBackup, parseBackup } from "../lib/backup";
import { updateWorkspace } from "../lib/store";

/** "Restore from backup": validates the chosen JSON file and merges it into the local workspace. */
export default function RestoreBackup() {
  const input = useRef<HTMLInputElement>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    try {
      if (file.size > MAX_BACKUP_BYTES) throw new Error("File is too large to be a workspace backup.");
      const parsed = parseBackup(await file.text());
      updateWorkspace((cur) => mergeBackup(cur, parsed));
      setMsg({
        ok: true,
        text: `Restored ${Object.keys(parsed.bookmarks).length} bookmarks and ${parsed.savedSearches.length} saved searches (merged with existing data).`,
      });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Could not read that file." });
    }
    if (input.current) input.current.value = "";
  };

  return (
    <>
      <button type="button" className="btn" onClick={() => input.current?.click()}>
        Restore from backup
      </button>
      <input
        ref={input}
        type="file"
        accept="application/json,.json"
        aria-label="Backup file"
        className="hidden"
        onChange={(e) => void onFile(e.target.files?.[0])}
      />
      {msg && (
        <p role="status" className={`basis-full text-xs ${msg.ok ? "text-emerald-700" : "text-red-600"}`}>
          {msg.text}
        </p>
      )}
    </>
  );
}
