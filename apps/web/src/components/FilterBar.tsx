import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Filters } from "../lib/filters";
import { filtersToSearchParams } from "../lib/filters";
import { uniqueValues } from "../lib/data";
import { useData } from "../App";

const ALWAYS_VISIBLE = ["state", "category", "value", "closing", "source"] as const;

/** Progressive-disclosure filters (spec #57). Always-visible: state, category,
 * value, closing date, source. Advanced inside "More filters". */
export default function FilterBar({ filters, onChange }: { filters: Filters; onChange: (f: Filters) => void }) {
  const [expanded, setExpanded] = useState(false);
  const { docs } = useData();
  const states = useMemo(() => uniqueValues(docs, "state"), [docs]);
  const sources = useMemo(() => uniqueValues(docs, "source"), [docs]);

  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch });
  const [, setSearchParams] = useSearchParams();

  const activeChips: { label: string; clear: () => void }[] = [];
  if (filters.state) activeChips.push({ label: `State: ${filters.state}`, clear: () => set({ state: undefined }) });
  if (filters.category) activeChips.push({ label: `Category: ${filters.category}`, clear: () => set({ category: undefined }) });
  if (filters.minValue != null) activeChips.push({ label: `Min ₹${(filters.minValue / 1e7).toFixed(1)} Cr`, clear: () => set({ minValue: undefined }) });
  if (filters.maxValue != null) activeChips.push({ label: `Max ₹${(filters.maxValue / 1e7).toFixed(1)} Cr`, clear: () => set({ maxValue: undefined }) });
  if (filters.closingWithinDays != null) activeChips.push({ label: `≤ ${filters.closingWithinDays} days`, clear: () => set({ closingWithinDays: undefined }) });
  if (filters.closingThisMonth) activeChips.push({ label: "Closing this month", clear: () => set({ closingThisMonth: false }) });
  if (filters.source) activeChips.push({ label: `Source: ${filters.source}`, clear: () => set({ source: undefined }) });
  if (filters.status) activeChips.push({ label: `Status: ${filters.status}`, clear: () => set({ status: undefined }) });

  return (
    <div className="space-y-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="State"
          value={filters.state ?? ""}
          onChange={(e) => set({ state: e.target.value || undefined })}
          className="input !py-1.5 text-xs"
        >
          <option value="">All states</option>
          {states.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select
          aria-label="Closing window"
          value={filters.closingWithinDays ?? ""}
          onChange={(e) => set({ closingWithinDays: e.target.value ? parseInt(e.target.value, 10) : undefined })}
          className="input !py-1.5 text-xs"
        >
          <option value="">Any deadline</option>
          <option value="3">Closing in 3 days</option>
          <option value="7">Closing in 7 days</option>
          <option value="15">Closing in 15 days</option>
          <option value="30">Closing in 30 days</option>
        </select>
        <button onClick={() => setExpanded((v) => !v)} className="btn !py-1.5 text-xs">
          {expanded ? "Fewer filters" : "More filters"}
        </button>
        {activeChips.length > 0 && (
          <button
            className="text-xs font-medium text-accent-600 hover:underline"
            onClick={() => {
              onChange({ keywords: filters.keywords });
              setSearchParams(new URLSearchParams());
            }}
          >
            Clear all
          </button>
        )}
      </div>

      {expanded && (
        <div className="card grid grid-cols-2 gap-3 p-3 sm:grid-cols-4">
          <label className="text-xs font-medium text-ink-500">
            Category
            <input
              value={filters.category ?? ""}
              onChange={(e) => set({ category: e.target.value || undefined })}
              placeholder="e.g. solar"
              className="input mt-1 w-full"
            />
          </label>
          <label className="text-xs font-medium text-ink-500">
            Min value (₹ Cr)
            <input
              type="number"
              min={0}
              value={filters.minValue != null ? String(filters.minValue / 1e7) : ""}
              onChange={(e) => set({ minValue: e.target.value ? parseFloat(e.target.value) * 1e7 : undefined })}
              className="input mt-1 w-full"
            />
          </label>
          <label className="text-xs font-medium text-ink-500">
            Max value (₹ Cr)
            <input
              type="number"
              min={0}
              value={filters.maxValue != null ? String(filters.maxValue / 1e7) : ""}
              onChange={(e) => set({ maxValue: e.target.value ? parseFloat(e.target.value) * 1e7 : undefined })}
              className="input mt-1 w-full"
            />
          </label>
          <label className="text-xs font-medium text-ink-500">
            Source
            <select value={filters.source ?? ""} onChange={(e) => set({ source: e.target.value || undefined })} className="input mt-1 w-full">
              <option value="">All sources</option>
              {sources.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
        </div>
      )}

      {activeChips.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5" role="list" aria-label="Active filters">
          {activeChips.map((c) => (
            <button key={c.label} role="listitem" onClick={c.clear} className="chip hover:border-accent-300 hover:bg-accent-50">
              {c.label} ✕
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function useFilterNavigation(): (f: Filters) => void {
  const [, setSearchParams] = useSearchParams();
  return (f: Filters) => setSearchParams(filtersToSearchParams(f));
}

void ALWAYS_VISIBLE;
