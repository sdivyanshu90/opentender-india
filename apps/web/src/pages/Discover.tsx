import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import ResultsList from "../components/ResultsList";

export default function Discover({ mode }: { mode: "all" | "new" | "closing" | "changed" }) {
  const [sp] = useSearchParams();
  const navigate = useNavigate();

  // Preset sensible params for special modes (once, only when empty).
  useEffect(() => {
    if (sp.toString()) return;
    if (mode === "closing") navigate("?within=7", { replace: true });
    else if (mode === "new") navigate("?sort=newest", { replace: true });
  }, [mode, sp, navigate]);

  const titles: Record<typeof mode, string> = {
    all: "Discover",
    new: "New Today",
    closing: "Closing Soon",
    changed: "Recently Changed",
  };
  const hints: Record<typeof mode, string> = {
    all: "All opportunities across connected official portals.",
    new: "Tenders discovered by the daily ingestion runs.",
    closing: "Deadlines in the next 7 days — act fast.",
    changed: "Corrigenda and revisions detected since first publication.",
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-5">
      <h1 className="mb-1 text-lg font-bold text-ink-900">{titles[mode]}</h1>
      <p className="mb-4 text-sm text-ink-500">{hints[mode]}</p>
      <ResultsList />
    </div>
  );
}
