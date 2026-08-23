import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useData } from "../App";
import { useWorkspace } from "../lib/store";
import { askTender, type AIAnswer } from "../lib/ai";

function useTenderContext(): string | undefined {
  const { id } = useParams();
  return id;
}

const SUGGESTED: Record<string, string[]> = {
  overview: ["What is being procured?", "What are the important deadlines?", "Is there a pre-bid meeting?"],
  eligibility: ["Can an MSME participate without previous government experience?", "What turnover is required?"],
  documents: ["What documents are mandatory?"],
  corrigenda: ["What changed?"],
  default: ["Summarise the key requirements.", "What are the major risks?", "Is a joint venture allowed?"],
};

/** Tender Copilot (spec #15/#60/#61): BYOK, evidence-first, structured answer. */
export default function AiPanel({
  open,
  onClose,
  contextId: contextIdProp,
}: {
  open: boolean;
  onClose: () => void;
  contextId?: string;
}) {
  const routeContext = useTenderContext();
  const contextId = contextIdProp ?? routeContext;
  const ws = useWorkspace();
  const { byId, docs } = useData();
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AIAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  if (!open) return null;

  const hasKey = !!ws.prefs.apiKey;
  const mode = ws.prefs.aiMode;
  const suggestions = SUGGESTED[contextId ?? "default"] ?? SUGGESTED.default;

  const ask = async (q: string) => {
    if (!q.trim() || !ws.prefs.apiKey) return;
    setBusy(true);
    setError(null);
    try {
      // In the full app the tender's document chunks come from
      // data/indexes/chunks/<id>.json.gz; here metadata + title provide context.
      const doc = contextId ? byId.get(contextId) : undefined;
      const tenderMeta: Record<string, unknown> = doc
        ? {
            title: doc.title,
            authority: doc.authority,
            state: doc.state,
            value_inr: doc.value,
            emd_inr: doc.emd,
            closing_at: doc.closing_at,
            category: doc.category,
            official_url: doc.url,
          }
        : {};
      void docs;
      const result = await askTender(ws.prefs.apiKey, {
        question: q,
        tenderMeta,
        chunks: [],
        model: ws.prefs.model,
      });
      setAnswer(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "AI request failed");
    } finally {
      setBusy(false);
      listRef.current?.scrollTo({ top: 0 });
    }
  };

  return (
    <aside className="fixed inset-0 z-40 flex flex-col bg-white lg:relative lg:inset-auto lg:w-[380px] lg:shrink-0 lg:border-l lg:border-ink-200" aria-label="Tender Copilot">
      <div className="flex items-center justify-between border-b border-ink-200 px-4 py-3">
        <h2 className="text-sm font-bold text-ink-900">Tender Copilot</h2>
        <div className="flex items-center gap-2">
          <PrivacyBadge mode={mode} />
          <button onClick={onClose} className="rounded p-1 text-ink-400 hover:bg-ink-100" aria-label="Close panel">✕</button>
        </div>
      </div>

      {!hasKey ? (
        <div className="flex-1 overflow-y-auto p-4">
          <p className="text-sm leading-relaxed text-ink-600">
            Live AI answers use <b>your own</b> OpenRouter API key stored only in this browser — OpenTender’s key never
            ships to clients. Precomputed AI summaries still appear on tender pages without any key.
          </p>
          <Link to="/settings" className="btn btn-primary mt-3 w-full">Add your API key in Settings</Link>
          <p className="mt-3 text-xs leading-relaxed text-ink-400">
            Without AI, everything else keeps working: search, filters, bookmarks, calendar exports and deterministic
            change tracking.
          </p>
        </div>
      ) : (
        <>
          <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto p-4">
            {!answer && !busy && (
              <>
                <p className="text-xs font-semibold uppercase tracking-wide text-ink-400">Suggested questions</p>
                {suggestions.map((s) => (
                  <button key={s} onClick={() => ask(s)} className="card block w-full px-3 py-2 text-left text-sm text-ink-700 hover:border-accent-300">
                    “{s}”
                  </button>
                ))}
              </>
            )}
            {busy && <p className="animate-pulse text-sm text-ink-400">Reading the tender evidence…</p>}
            {error && (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {error}
                <p className="mt-1 text-xs text-red-500">AI temporarily unavailable — core features keep working.</p>
              </div>
            )}
            {answer && <AnswerCard answer={answer} />}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void ask(question);
              setQuestion("");
            }}
            className="border-t border-ink-200 p-3"
          >
            <div className="flex gap-2">
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask about this tender…"
                aria-label="Ask about this tender"
                className="input min-w-0 flex-1"
              />
              <button type="submit" disabled={busy || !question.trim()} className="btn btn-primary shrink-0">
                Ask
              </button>
            </div>
          </form>
        </>
      )}
    </aside>
  );
}

function AnswerCard({ answer }: { answer: AIAnswer }) {
  return (
    <div className="card p-3">
      <p className="text-sm leading-relaxed text-ink-800">{cleanAnswer(answer.answer)}</p>
      {answer.citations.length > 0 && (
        <div className="mt-2 border-t border-ink-100 pt-2">
          <p className="text-[10px] font-bold uppercase tracking-wide text-ink-400">Evidence</p>
          <ul className="mt-1 space-y-1">
            {answer.citations.map((c, i) => (
              <li key={i} className="text-xs text-accent-700">
                📄 {c.document_title}
                {c.page ? `, p.${c.page}` : ""}
                {c.quote ? ` — “${c.quote.slice(0, 140)}”` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}
      {answer.important && (
        <p className="mt-2 rounded bg-amber-50 p-2 text-xs text-amber-800"><b>Important:</b> {answer.important}</p>
      )}
      {answer.next_action && (
        <p className="mt-2 text-xs text-ink-500"><b>Next action:</b> {answer.next_action}</p>
      )}
      <p className="mt-2 text-right text-[10px] text-ink-300">{answer.model}</p>
    </div>
  );
}

function cleanAnswer(text: string): string {
  // If the model wrapped prose in JSON despite instructions, show raw gracefully.
  const t = text.trim();
  if ((t.startsWith("{") || t.startsWith("```")) ) {
    try {
      const parsed = JSON.parse(t.replace(/```json|```/g, ""));
      if (typeof parsed?.answer === "string") return parsed.answer;
    } catch {
      /* fall through */
    }
  }
  return t;
}

function PrivacyBadge({ mode }: { mode: string }) {
  const labels: Record<string, [string, string]> = {
    local: ["Local only", "bg-emerald-50 text-emerald-700 border-emerald-200"],
    public: ["Public tender AI", "bg-sky-50 text-sky-700 border-sky-200"],
    personal: ["Personalised AI", "bg-violet-50 text-violet-700 border-violet-200"],
  };
  const [label, cls] = labels[mode] ?? labels.local;
  return <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${cls}`}>{label}</span>;
}
