import { useState } from "react";
import { updateWorkspace, useWorkspace } from "../lib/store";
import type { CompanyProfile } from "../lib/store";

/** Settings: BYOK AI, privacy mode, company profile (all local). */
export default function Settings() {
  const ws = useWorkspace();
  const [keyInput, setKeyInput] = useState("");

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4 py-6">
      <div>
        <h1 className="text-lg font-bold text-ink-900">Settings</h1>
        <p className="mt-0.5 text-sm text-ink-500">Everything on this page lives in your browser only.</p>
      </div>

      {/* Privacy + AI */}
      <section className="card p-4">
        <h2 className="font-semibold text-ink-900">AI &amp; privacy</h2>
        <p className="mt-1 text-xs leading-relaxed text-ink-500">
          OpenTender never ships the project’s API key to your browser. For live Q&amp;A you can add <b>your own</b>{" "}
          OpenRouter key; it is stored locally and used only for requests you trigger.
        </p>

        <fieldset className="mt-3">
          <legend className="text-xs font-semibold uppercase tracking-wide text-ink-400">Privacy mode</legend>
          {(
            [
              ["local", "Local only", "No tender or profile data is ever sent to external AI."],
              ["public", "Public tender AI", "Only public tender/document data may be sent to AI providers."],
              ["personal", "Personalised AI", "Additionally allows profile-derived context, after you opt in."],
            ] as const
          ).map(([value, label, hint]) => (
            <label key={value} className={`mt-2 flex cursor-pointer items-start gap-2.5 rounded-md border p-2.5 ${ws.prefs.aiMode === value ? "border-accent-400 bg-accent-50/60" : "border-ink-200"}`}>
              <input
                type="radio"
                name="aiMode"
                checked={ws.prefs.aiMode === value}
                onChange={() => updateWorkspace((cur) => ({ ...cur, prefs: { ...cur.prefs, aiMode: value } }))}
                className="mt-0.5"
              />
              <span>
                <span className="block text-sm font-medium text-ink-800">{label}</span>
                <span className="block text-xs text-ink-500">{hint}</span>
              </span>
            </label>
          ))}
        </fieldset>

        <div className="mt-4 flex items-end gap-2">
          <label className="min-w-0 flex-1 text-xs font-medium text-ink-500">
            Your OpenRouter API key
            <input
              type="password"
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              placeholder="sk-or-v1-…"
              autoComplete="off"
              className="input mt-1 w-full font-mono"
            />
          </label>
          <button
            className="btn btn-primary"
            onClick={() =>
              updateWorkspace((cur) => ({
                ...cur,
                prefs: { ...cur.prefs, apiKey: keyInput.trim() || undefined },
              }))
            }
          >
            Save key
          </button>
          {ws.prefs.apiKey && (
            <button
              className="btn !border-red-200 !text-red-600"
              onClick={() => {
                setKeyInput("");
                updateWorkspace((cur) => ({ ...cur, prefs: { ...cur.prefs, apiKey: undefined } }));
              }}
            >
              Remove
            </button>
          )}
        </div>
        {ws.prefs.apiKey && <p className="mt-1 text-xs text-emerald-600">✓ Key stored locally (sk-or-v1-…{ws.prefs.apiKey.slice(-6)})</p>}
      </section>

      <ProfileSection />
    </div>
  );
}

function ProfileSection() {
  const ws = useWorkspace();
  return (
    <section className="card p-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-ink-900">Company capability profile</h2>
        {ws.profile && (
          <button onClick={() => updateWorkspace((cur) => ({ ...cur, profile: null }))} className="text-xs font-medium text-red-600 hover:underline">
            Delete profile
          </button>
        )}
      </div>
      <p className="mt-1 text-xs leading-relaxed text-ink-500">
        Used only on this device to rank “For You” matches. In Local/Public modes it is never included in AI requests.
      </p>
      <ProfileFields />
    </section>
  );
}

export function ProfileFields() {
  const ws = useWorkspace();
  const [form, setForm] = useState<CompanyProfile>(
    () =>
      ws.profile ?? {
        industries: [],
        productCategories: [],
        services: [],
        preferredStates: [],
        certifications: [],
        msme: false,
        startup: false,
        pastProjectKeywords: [],
      },
  );

  const listField = (name: keyof CompanyProfile, label: string, placeholder: string) => (
    <label className="block text-xs font-medium text-ink-500">
      {label}
      <input
        value={(form[name] as string[]).join(", ")}
        onChange={(e) =>
          setForm((f) => ({ ...f, [name]: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) }))
        }
        placeholder={placeholder}
        className="input mt-1 w-full"
      />
    </label>
  );

  const numField = (name: keyof CompanyProfile, label: string) => (
    <label className="block text-xs font-medium text-ink-500">
      {label} (₹)
      <input
        type="number"
        min={0}
        value={form[name] != null ? String(form[name]) : ""}
        onChange={(e) => setForm((f) => ({ ...f, [name]: e.target.value ? Number(e.target.value) : undefined }))}
        className="input mt-1 w-full"
      />
    </label>
  );

  const save = () => updateWorkspace((cur) => ({ ...cur, profile: form, prefs: { ...cur.prefs, onboarded: true } }));

  return (
    <div className="mt-3 space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        {listField("industries", "Industries", "e.g. solar, roads, medical equipment")}
        {listField("productCategories", "Product categories", "comma separated")}
        {listField("services", "Services", "e.g. EPC, O&M, installation")}
        {listField("preferredStates", "Preferred states", "e.g. Maharashtra, Gujarat")}
        {numField("minContractSize", "Minimum contract size")}
        {numField("maxContractSize", "Maximum contract size")}
      </div>
      <div className="flex flex-wrap items-center gap-4 pt-1">
        <label className="flex items-center gap-2 text-sm text-ink-700">
          <input type="checkbox" checked={form.msme} onChange={(e) => setForm((f) => ({ ...f, msme: e.target.checked }))} />
          MSME registered
        </label>
        <label className="flex items-center gap-2 text-sm text-ink-700">
          <input type="checkbox" checked={form.startup} onChange={(e) => setForm((f) => ({ ...f, startup: e.target.checked }))} />
          DPIIT startup
        </label>
      </div>
      <button onClick={save} className="btn btn-primary">Save profile</button>
    </div>
  );
}
