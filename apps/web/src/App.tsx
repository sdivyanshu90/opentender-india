import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { Link, Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import type { TenderDoc } from "./lib/types";
import { loadDataset } from "./lib/data";
import { buildIndex } from "./lib/search";
import { updateWorkspace, useWorkspace } from "./lib/store";
import { clearCompare, toggleCompare, useCompareIds } from "./lib/compare";
import CommandPalette from "./components/CommandPalette";
import AiPanel from "./components/AiPanel";
import Home from "./pages/Home";
import Discover from "./pages/Discover";
import ForYou from "./pages/ForYou";
import Saved from "./pages/Saved";
import SourcesPage from "./pages/SourcesPage";
import TenderDetail from "./pages/TenderDetail";
import Compare from "./pages/Compare";
import Settings from "./pages/Settings";

interface Ctx {
  docs: TenderDoc[];
  index: ReturnType<typeof buildIndex> | null;
  byId: Map<string, TenderDoc>;
  loading: boolean;
  fixture: boolean;
  generatedAt: string | null;
}
const DataContext = createContext<Ctx>({
  docs: [],
  index: null,
  byId: new Map(),
  loading: true,
  fixture: false,
  generatedAt: null,
});
export const useData = () => useContext(DataContext);

export default function App() {
  const [docs, setDocs] = useState<TenderDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [fixture, setFixture] = useState(false);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [copilotOpen, setCopilotOpen] = useState(false);
  const compareIds = useCompareIds();
  const ws = useWorkspace();

  useEffect(() => {
    loadDataset().then((d) => {
      setDocs(d.docs);
      setFixture(d.fixture);
      setGeneratedAt(d.generatedAt);
      setLoading(false);
    });
  }, []);

  const ctx = useMemo<Ctx>(() => {
    const byId = new Map(docs.map((d) => [d.id, d]));
    return { docs, index: docs.length ? buildIndex(docs) : null, byId, loading, fixture, generatedAt };
  }, [docs, loading, fixture, generatedAt]);

  // keyboard shortcuts (spec #53/#54)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const typing = /input|textarea|select/i.test(target.tagName) || target.isContentEditable;
      if ((e.key === "/" && !typing) || ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k")) {
        e.preventDefault();
        setPaletteOpen(true);
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "j") {
        e.preventDefault();
        setCopilotOpen((v) => !v);
      }
      if (e.key === "Escape") setPaletteOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <DataContext.Provider value={ctx}>
      <div className="flex min-h-screen">
        {/* Left nav rail (desktop) */}
        <aside className="hidden lg:flex w-56 shrink-0 flex-col border-r border-ink-200 bg-white">
          <Brand />
          <nav className="flex-1 px-2 py-4 space-y-0.5">
            <NavItem to="/" icon="◎" label="Discover" end />
            <NavItem to="/for-you" icon="✦" label="For You" />
            <NavItem to="/new" icon="✧" label="New Today" />
            <NavItem to="/closing-soon" icon="⌛" label="Closing Soon" />
            <NavItem to="/changed" icon="⟳" label="Changed" />
            <NavItem to="/saved" icon="★" label="Saved" />
            <NavItem to="/sources" icon="⛁" label="Sources" />
            <NavItem to="/settings" icon="⚙" label="Settings" />
          </nav>
          <div className="border-t border-ink-200 p-3 text-[11px] leading-relaxed text-ink-400">
            Independent open-source project.
            <br />
            Not affiliated with the Government of India.
          </div>
        </aside>

        {/* Center workspace */}
        <div className="flex min-w-0 flex-1 flex-col">
          {fixture && (
            <div className="bg-amber-100 border-b border-amber-300 px-4 py-1.5 text-center text-xs font-medium text-amber-800">
              Development mode — showing clearly-labelled synthetic fixture data. Run the ingestion
              pipeline to populate real tender datasets.
            </div>
          )}
          <TopBar onOpenPalette={() => setPaletteOpen(true)} compareCount={compareIds.length} />

          <main className="min-w-0 flex-1 pb-20 lg:pb-6">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/discover" element={<Discover mode="all" />} />
              <Route path="/for-you" element={<ForYou />} />
              <Route path="/new" element={<Discover mode="new" />} />
              <Route path="/closing-soon" element={<Discover mode="closing" />} />
              <Route path="/changed" element={<Discover mode="changed" />} />
              <Route
                path="/tender/:id"
                element={
                  <TenderDetail
                    copilotOpen={copilotOpen}
                    setCopilotOpen={setCopilotOpen}
                    compareIds={compareIds}
                    toggleCompare={toggleCompare}
                  />
                }
              />
              <Route path="/saved" element={<Saved />} />
              <Route path="/compare" element={<Compare compareIds={compareIds} toggleCompare={toggleCompare} />} />
              <Route path="/sources" element={<SourcesPage />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/home" element={<Navigate to="/" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>

        {/* Right Copilot panel (desktop, contextual) */}
        <AiPanel open={copilotOpen} onClose={() => setCopilotOpen(false)} />

        {/* Mobile bottom nav */}
        <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-ink-200 bg-white/95 backdrop-blur lg:hidden pb-safe">
          <MobileItem to="/" icon="◎" label="Discover" end />
          <MobileItem to="/for-you" icon="✦" label="For You" />
          <MobileItem to="/saved" icon="★" label="Saved" />
          <button
            onClick={() => setCopilotOpen(true)}
            className="flex flex-col items-center gap-0.5 py-2 text-xs text-ink-500"
          >
            <span className="text-base">✦</span>
            AI
          </button>
          <MobileItem to="/more" icon="⋯" label="More" hidden />
        </nav>

        {paletteOpen && <CommandPalette onClose={() => setPaletteOpen(false)} />}
        {compareIds.length > 0 && (
          <CompareBar ids={compareIds} clear={clearCompare} />
        )}
        {!ws.prefs.onboarded && !loading && <OnboardingHint />}
      </div>
    </DataContext.Provider>
  );
}

function Brand() {
  return (
    <div className="border-b border-ink-200 px-4 py-4">
      <NavLink to="/" className="block">
        <div className="text-sm font-bold tracking-tight text-ink-900">OpenTender</div>
        <div className="text-xs font-semibold uppercase tracking-widest text-accent-600">India</div>
      </NavLink>
    </div>
  );
}

function TopBar({ onOpenPalette, compareCount }: { onOpenPalette: () => void; compareCount: number }) {
  return (
    <header className="sticky top-0 z-20 border-b border-ink-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-2.5">
        <button onClick={onOpenPalette} className="input flex w-full items-center gap-2 text-left text-ink-400 hover:border-accent-400">
          <span aria-hidden>⌕</span>
          <span className="truncate">Search tenders or ask AI…</span>
          <kbd className="ml-auto hidden rounded border border-ink-200 bg-ink-50 px-1.5 py-0.5 text-[10px] font-medium text-ink-400 sm:block">
            /
          </kbd>
        </button>
        {compareCount > 0 && (
          <Link to="/compare" className="btn whitespace-nowrap">
            Compare ({compareCount})
          </Link>
        )}
      </div>
    </header>
  );
}

function NavItem({
  to,
  icon,
  label,
  end,
}: {
  to: string;
  icon: string;
  label: string;
  end?: boolean;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
          isActive ? "bg-accent-50 text-accent-700" : "text-ink-600 hover:bg-ink-50"
        }`
      }
    >
      <span aria-hidden className="w-4 text-center opacity-70">{icon}</span>
      {label}
    </NavLink>
  );
}

function MobileItem({
  to,
  icon,
  label,
  end,
  hidden,
}: {
  to: string;
  icon: string;
  label: string;
  end?: boolean;
  hidden?: boolean;
}) {
  if (hidden) return <MoreLink />;
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `flex flex-col items-center gap-0.5 py-2 text-xs ${isActive ? "font-semibold text-accent-600" : "text-ink-500"}`
      }
    >
      <span aria-hidden className="text-base">{icon}</span>
      {label}
    </NavLink>
  );
}

function MoreLink() {
  return (
    <NavLink to="/settings" className="flex flex-col items-center gap-0.5 py-2 text-xs text-ink-500">
      <span aria-hidden className="text-base">⋯</span>
      More
    </NavLink>
  );
}

function CompareBar({ ids, clear }: { ids: string[]; clear: () => void }) {
  return (
    <div className="fixed bottom-16 left-1/2 z-40 -translate-x-1/2 lg:bottom-4">
      <div className="flex items-center gap-3 rounded-full border border-ink-200 bg-ink-900 py-2 pl-4 pr-2 text-white shadow-lg">
        <span className="text-sm">{ids.length} selected</span>
        <Link to="/compare" className="rounded-full bg-accent-500 px-3 py-1 text-sm font-medium hover:bg-accent-600">
          Compare →
        </Link>
        <button onClick={clear} className="rounded-full px-2 text-ink-300 hover:text-white" aria-label="Clear selection">
          ✕
        </button>
      </div>
    </div>
  );
}

function OnboardingHint() {
  const location = useLocation();
  if (location.pathname !== "/") return null;
  return (
    <div className="fixed bottom-24 left-1/2 z-40 w-[92%] max-w-md -translate-x-1/2 rounded-lg border border-ink-200 bg-white p-4 shadow-xl lg:bottom-6 lg:left-auto lg:right-6 lg:translate-x-0">
      <p className="text-sm font-semibold text-ink-900">Welcome to OpenTender India</p>
      <p className="mt-1 text-sm text-ink-600">
        Optionally tell us your industry and states to see matched opportunities — or just start searching.
        Everything stays in your browser.
      </p>
      <div className="mt-3 flex justify-end gap-2">
        <SkipButton />
        <Link to="/for-you" className="btn btn-primary">Set up profile</Link>
      </div>
    </div>
  );
}

function SkipButton() {
  return (
    <button className="btn" onClick={() => updateWorkspace((ws) => ({ ...ws, prefs: { ...ws.prefs, onboarded: true } }))}>
      Skip setup
    </button>
  );
}
