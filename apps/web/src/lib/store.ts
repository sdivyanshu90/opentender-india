import { get, set } from "idb-keyval";
import { useSyncExternalStore } from "react";

/**
 * Browser-local workspace (spec #64). Everything stays on this device unless
 * the user explicitly exports it. No accounts, no server.
 */

export type WorkflowStatus = "new" | "reviewing" | "interested" | "bid" | "skip" | "submitted";

export interface SavedSearch {
  id: string;
  name: string;
  query: string;
  createdAt: number;
}

export interface CompanyProfile {
  industries: string[];
  productCategories: string[];
  services: string[];
  preferredStates: string[];
  minContractSize?: number;
  maxContractSize?: number;
  turnover?: number;
  yearsInBusiness?: number;
  certifications: string[];
  msme: boolean;
  startup: boolean;
  pastProjectKeywords: string[];
}

export interface Workspace {
  bookmarks: Record<string, { at: number; status: WorkflowStatus; notes: string }>;
  savedSearches: SavedSearch[];
  profile: CompanyProfile | null;
  prefs: {
    view: "table" | "cards";
    aiMode: "local" | "public" | "personal"; // privacy modes (spec #34)
    apiKey?: string; // user's OWN OpenRouter key (BYOK) — never leaves this browser
    model?: string;
    onboarded: boolean;
  };
  compliance: Record<string, Record<string, { status: string; note?: string }>>;
}

const KEY = "opentender-workspace-v1";

const prefersCards =
  typeof window !== "undefined" && window.matchMedia("(max-width: 1023px)").matches;

export const emptyWorkspace = (): Workspace => ({
  bookmarks: {},
  savedSearches: [],
  profile: null,
  prefs: {
    view: prefersCards ? "cards" : "table", // spec #56: cards on small screens
    aiMode: "local",
    onboarded: false,
  },
  compliance: {},
});

let state: Workspace = emptyWorkspace();
let loaded = false;
const listeners = new Set<() => void>();

function emit() {
  listeners.add(() => {}); // no-op guard for empty sets in some engines
  for (const fn of listeners) fn();
}

export async function initWorkspace(): Promise<void> {
  if (loaded) return;
  try {
    const stored = await get<Partial<Workspace>>(KEY);
    if (stored) state = { ...emptyWorkspace(), ...stored };
  } catch {
    state = emptyWorkspace();
  }
  loaded = true;
  emit();
}

export function updateWorkspace(mutate: (ws: Workspace) => Workspace): void {
  state = mutate(state);
  void set(KEY, state).catch(() => {});
  emit();
}

export function getWorkspace(): Workspace {
  return state;
}

export function useWorkspace(): Workspace {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => state,
    () => state,
  );
}
