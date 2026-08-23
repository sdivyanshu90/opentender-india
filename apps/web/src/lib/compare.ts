import { useSyncExternalStore } from "react";

/** Ephemeral cross-page compare-selection state (max 5 tenders, spec #29). */

const MAX_COMPARE = 5;

let ids: string[] = [];
const listeners = new Set<() => void>();

function emit() {
  for (const fn of listeners) fn();
}

export function toggleCompare(id: string): void {
  ids = ids.includes(id)
    ? ids.filter((x) => x !== id)
    : [...ids, id].slice(-MAX_COMPARE);
  emit();
}

export function clearCompare(): void {
  ids = [];
  emit();
}

export function getCompareIds(): string[] {
  return ids;
}

export function useCompareIds(): string[] {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => ids,
    () => ids,
  );
}
