import { AnimatePresence, motion } from 'framer-motion';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { api, toErrorPayload } from './api/client';
import {
  ERROR_CODES,
  type AnalyzeResult,
  type ApplyResponse,
  type ErrorPayload,
  type HealthResponse,
  type HistoryEntry,
  type LLMChoice,
} from './api/types';
import { HistoryPanel } from './components/HistoryPanel';
import { LogoMark } from './components/Logo';
import { APP_NAME } from './config';
import { ModelPicker } from './components/ModelPicker';
import { useLLMChoice } from './lib/llmChoice';
import type { ChatEntry } from './screens/results/ChatPanel';
import { ApiKeyMissingHelp, StateMessage } from './components/StateMessage';
import { Button } from './components/ui';
import { AnalyzingScreen } from './screens/AnalyzingScreen';
import { HomeScreen } from './screens/HomeScreen';
import { ResultsScreen } from './screens/results/ResultsScreen';
import { Splash } from './screens/Splash';

type Screen = 'splash' | 'home' | 'workspace';

/** One analyzed path; every selected file or folder gets its own tab. */
type TabState =
  | { kind: 'analyzing'; jobId: string }
  | { kind: 'results'; jobId: string; result: AnalyzeResult }
  | { kind: 'error'; error: ErrorPayload };

interface Tab {
  id: string;
  path: string;
  verify: boolean;
  state: TabState;
  /** Shown above the next results, e.g. after an apply or an undo. */
  notice?: string;
  /** Conversation with Claude about this tab's code; survives re-analysis. */
  chat?: ChatEntry[];
  /** True while Claude is answering in this tab (the tab light turns yellow). */
  chatBusy?: boolean;
}

let tabCounter = 0;

function baseName(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path;
}

function normalize(path: string): string {
  return path.replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase();
}

/** True when the history entry touched something inside the tab's path. */
function touches(tab: Tab, entry: HistoryEntry): boolean {
  const base = normalize(tab.path);
  return entry.files.some((f) => {
    const file = normalize(f.path);
    return file === base || file.startsWith(`${base}/`);
  });
}

export default function App() {
  const [screen, setScreen] = useState<Screen>('splash');
  const [tabs, setTabs] = useState<Tab[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<ErrorPayload | null>(null);
  const [startError, setStartError] = useState<ErrorPayload | null>(null);
  const [starting, setStarting] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const { choice, models, setChoice } = useLLMChoice();
  const [spent, setSpent] = useState(0);
  const addCost = useCallback((cost: number | null | undefined) => {
    if (cost) setSpent((total) => total + cost);
  }, []);
  const picker = <ModelPicker choice={choice} models={models} onChange={setChoice} spent={spent} />;

  const refreshHealth = useCallback(() => {
    api
      .health()
      .then((h) => {
        setHealth(h);
        setHealthError(null);
      })
      .catch((err: unknown) => setHealthError(toErrorPayload(err)));
  }, []);

  useEffect(refreshHealth, [refreshHealth]);

  const goHome = useCallback(() => {
    setStartError(null);
    setScreen('home');
    refreshHealth();
  }, [refreshHealth]);

  const updateTab = useCallback(
    (id: string, state: TabState) => {
      if (state.kind === 'results') addCost(state.result.estimated_cost_usd);
      setTabs((all) => all.map((t) => (t.id === id ? { ...t, state } : t)));
    },
    [addCost],
  );

  const patchTab = useCallback((id: string, patch: Partial<Tab>) => {
    setTabs((all) => all.map((t) => (t.id === id ? { ...t, ...patch } : t)));
  }, []);

  const closeTab = useCallback(
    (id: string) => {
      const index = tabs.findIndex((t) => t.id === id);
      const tab = tabs[index];
      if (!tab) return;
      if (tab.state.kind === 'analyzing') void api.cancelAnalyze(tab.state.jobId);
      const rest = tabs.filter((t) => t.id !== id);
      setTabs(rest);
      if (activeId === id) setActiveId(rest[Math.min(index, rest.length - 1)]?.id ?? null);
      if (rest.length === 0) goHome();
    },
    [tabs, activeId, goHome],
  );

  const onSplashDone = useCallback(() => setScreen('home'), []);

  /** Run the tab's path again (after an apply or undo) and keep a note for the new results. */
  const reanalyze = useCallback(
    async (id: string, notice: string) => {
      const tab = tabs.find((t) => t.id === id);
      if (!tab) return;
      try {
        const { job_id } = await api.startAnalyze(tab.path, tab.verify, choice ?? undefined);
        setTabs((all) =>
          all.map((t) => (t.id === id ? { ...t, notice, state: { kind: 'analyzing', jobId: job_id } } : t)),
        );
      } catch (err) {
        updateTab(id, { kind: 'error', error: toErrorPayload(err) });
      }
    },
    [tabs, updateTab, choice],
  );

  const onApplied = useCallback(
    (id: string, response: ApplyResponse) => {
      const files = response.changed_files.join(', ');
      void reanalyze(
        id,
        `✓ ${response.applied_ids.length} düzeltme uygulandı (${files}). Kod yeniden analiz edildi; ` +
          'değişikliği "Geçmiş" panelinden görebilir ve geri alabilirsiniz.',
      );
    },
    [reanalyze],
  );

  const onUndone = useCallback(
    (entry: HistoryEntry) => {
      for (const tab of tabs) {
        if (touches(tab, entry)) {
          void reanalyze(tab.id, `↺ Değişiklik geri alındı (${entry.files.map((f) => f.name).join(', ')}).`);
        }
      }
    },
    [tabs, reanalyze],
  );

  const start = async (paths: string[], verify: boolean) => {
    setStarting(true);
    setStartError(null);
    const started = await Promise.all(
      paths.map(async (path): Promise<Tab> => {
        const id = `tab-${++tabCounter}`;
        try {
          const { job_id } = await api.startAnalyze(path, verify, choice ?? undefined);
          return { id, path, verify, state: { kind: 'analyzing', jobId: job_id } };
        } catch (err) {
          return { id, path, verify, state: { kind: 'error', error: toErrorPayload(err) } };
        }
      }),
    );
    setStarting(false);
    // A single path that could not even start stays on the home screen, as before.
    if (started.length === 1 && started[0].state.kind === 'error') {
      setStartError(started[0].state.error);
      return;
    }
    setTabs((all) => [...all, ...started]);
    setActiveId(started[0]?.id ?? null);
    setScreen('workspace');
  };

  const active = tabs.find((t) => t.id === activeId) ?? tabs[0] ?? null;

  return (
    <div className="h-full overflow-hidden">
      <AnimatePresence mode="wait">
        {screen === 'splash' && <Splash key="splash" onDone={onSplashDone} />}
        {screen === 'home' && (
          <Fade key="home">
            <HomeScreen
              health={health}
              healthError={healthError}
              startError={startError}
              starting={starting}
              onStart={(paths, verify) => void start(paths, verify)}
              openTabs={tabs.length}
              onBackToTabs={() => setScreen('workspace')}
              onOpenHistory={() => setHistoryOpen(true)}
              picker={picker}
            />
          </Fade>
        )}
        {screen === 'workspace' && (
          <Fade key="workspace">
            <div className="flex h-full flex-col">
              <TabBar
                tabs={tabs}
                activeId={active?.id ?? null}
                onSelect={setActiveId}
                onClose={closeTab}
                onAdd={goHome}
                onOpenHistory={() => setHistoryOpen(true)}
                picker={picker}
              />
              <div className="relative min-h-0 flex-1">
                {tabs.map((tab) => (
                  <div key={tab.id} className="absolute inset-0" hidden={tab.id !== active?.id}>
                    <TabBody
                      tab={tab}
                      active={tab.id === active?.id}
                      onUpdate={updateTab}
                      onClose={closeTab}
                      onNewAnalysis={goHome}
                      onApplied={onApplied}
                      onReanalyze={(id) => void reanalyze(id, '')}
                      onPatch={patchTab}
                      llm={choice}
                      onCost={addCost}
                      onChatApplied={(id, response, explanation) =>
                        void reanalyze(
                          id,
                          `✓ Sohbetten değişiklik uygulandı (${response.changed_files.join(', ')}): ${explanation} ` +
                            'Kod yeniden analiz edildi; "Geçmiş" panelinden geri alabilirsiniz.',
                        )
                      }
                    />
                  </div>
                ))}
              </div>
            </div>
          </Fade>
        )}
      </AnimatePresence>
      <HistoryPanel open={historyOpen} onClose={() => setHistoryOpen(false)} onUndone={onUndone} />
    </div>
  );
}

function TabBody({
  tab,
  active,
  onUpdate,
  onClose,
  onNewAnalysis,
  onApplied,
  onReanalyze,
  onPatch,
  onChatApplied,
  llm,
  onCost,
}: {
  tab: Tab;
  active: boolean;
  onUpdate: (id: string, state: TabState) => void;
  onClose: (id: string) => void;
  onNewAnalysis: () => void;
  onApplied: (id: string, response: ApplyResponse) => void;
  onReanalyze: (id: string) => void;
  onPatch: (id: string, patch: Partial<Tab>) => void;
  onChatApplied: (id: string, response: ApplyResponse, explanation: string) => void;
  llm: LLMChoice | null;
  onCost: (cost: number | null | undefined) => void;
}) {
  const { id, state } = tab;
  const onResult = useCallback(
    (result: AnalyzeResult) =>
      onUpdate(id, { kind: 'results', jobId: state.kind === 'analyzing' ? state.jobId : '', result }),
    [id, onUpdate, state],
  );
  const onError = useCallback(
    (error: ErrorPayload) => {
      if (error.code === ERROR_CODES.cancelled) onClose(id);
      else onUpdate(id, { kind: 'error', error });
    },
    [id, onClose, onUpdate],
  );

  if (state.kind === 'analyzing') {
    return (
      <AnalyzingScreen
        jobId={state.jobId}
        path={tab.path}
        verify={tab.verify}
        onResult={onResult}
        onError={onError}
        onCancel={() => void api.cancelAnalyze(state.jobId)}
      />
    );
  }
  if (state.kind === 'results') {
    return (
      <ResultsScreen
        jobId={state.jobId}
        result={state.result}
        onNewAnalysis={onNewAnalysis}
        active={active}
        notice={tab.notice}
        onApplied={(response) => onApplied(id, response)}
        onReanalyze={() => onReanalyze(id)}
        path={tab.path}
        chat={tab.chat ?? []}
        onChat={(chat) => onPatch(id, { chat })}
        onChatBusy={(chatBusy) => onPatch(id, { chatBusy })}
        onChatApplied={(response, explanation) => onChatApplied(id, response, explanation)}
        llm={llm}
        onCost={onCost}
      />
    );
  }
  return <ErrorScreen error={state.error} onBack={() => onClose(id)} />;
}

function TabBar({
  tabs,
  activeId,
  onSelect,
  onClose,
  onAdd,
  onOpenHistory,
  picker,
}: {
  tabs: Tab[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onClose: (id: string) => void;
  onAdd: () => void;
  onOpenHistory: () => void;
  picker: ReactNode;
}) {
  return (
    <nav
      aria-label="Analiz sekmeleri"
      className="flex shrink-0 items-end gap-1 overflow-x-auto border-b border-border bg-panel-2 px-3 pt-2"
    >
      {tabs.map((tab) => {
        const selected = tab.id === activeId;
        return (
          <div
            key={tab.id}
            className={`group flex max-w-64 shrink-0 items-center rounded-t-[var(--radius-control)] border border-b-0 text-sm transition-colors ${selected ? '-mb-px border-border bg-bg text-strong' : 'border-transparent text-muted hover:bg-hover hover:text-strong'}`}
          >
            <button
              type="button"
              role="tab"
              aria-selected={selected}
              title={tab.path}
              onClick={() => onSelect(tab.id)}
              className="flex min-w-0 items-center gap-2 py-2 pr-1 pl-3 focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:outline-none"
            >
              <TabStatus tab={tab} />
              <span className="truncate font-mono text-[13px]">{baseName(tab.path)}</span>
            </button>
            <button
              type="button"
              aria-label={`${baseName(tab.path)} sekmesini kapat`}
              onClick={() => onClose(tab.id)}
              className="mr-1.5 rounded-md px-1.5 text-subtle opacity-60 hover:bg-hover hover:text-text hover:opacity-100 focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:outline-none"
            >
              ×
            </button>
          </div>
        );
      })}
      <button
        type="button"
        onClick={onAdd}
        title="Yeni dosya ya da klasör analiz et"
        className="mb-1 ml-1 shrink-0 rounded-[var(--radius-control)] px-2.5 py-1 text-muted hover:bg-hover hover:text-text focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:outline-none"
      >
        + Yeni
      </button>
      <div className="mb-1 ml-auto shrink-0">{picker}</div>
      <button
        type="button"
        onClick={onOpenHistory}
        title="Uygulanan değişiklikler, farkları ve geri alma"
        className="mb-1.5 ml-1 shrink-0 rounded-[var(--radius-control)] px-2.5 py-1 text-[13px] text-muted hover:bg-hover hover:text-strong focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:outline-none"
      >
        Geçmiş
      </button>
      <span className="mb-1.5 ml-2 flex shrink-0 items-center gap-2 pr-1">
        <LogoMark size={22} />
        <span className="text-[15px] font-semibold tracking-tight text-strong">{APP_NAME}</span>
      </span>
    </nav>
  );
}

/** Traffic light: yellow = working, red = something to fix, green = ready. */
function TabStatus({ tab }: { tab: Tab }) {
  const { state } = tab;
  let color = 'bg-ok';
  let label = 'Hazır: kodda hata yok';
  if (state.kind === 'analyzing' || tab.chatBusy) {
    color = 'bg-warn animate-pulse';
    label = state.kind === 'analyzing' ? 'Çalışıyor: analiz ediliyor' : 'Çalışıyor: Claude yanıtlıyor';
  } else if (state.kind === 'error') {
    color = 'bg-err';
    label = 'Hata: analiz tamamlanamadı';
  } else {
    const errors = state.result.findings.filter((f) => f.severity === 'error').length;
    const total = state.result.findings.length;
    if (errors > 0) {
      color = 'bg-err';
      label = `Hata: ${errors} ciddi sorun, toplam ${total} bulgu`;
    } else if (total > 0) {
      label = `Hazır: ${total} küçük bulgu, ciddi hata yok`;
    }
  }
  return <span role="img" aria-label={label} title={label} className={`size-2.5 shrink-0 rounded-full ${color}`} />;
}

function Fade({ children }: { children: ReactNode }) {
  return (
    <motion.div
      className="h-full"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.18, ease: [0.2, 0.8, 0.2, 1] }}
    >
      {children}
    </motion.div>
  );
}

function ErrorScreen({ error, onBack }: { error: ErrorPayload; onBack: () => void }) {
  const keyMissing = error.code === ERROR_CODES.apiKeyMissing;
  return (
    <div className="flex h-full items-center justify-center">
      <StateMessage
        icon={keyMissing ? '🔑' : '!'}
        tone={keyMissing ? 'warn' : 'err'}
        title={keyMissing ? 'API anahtarı eksik' : 'Analiz tamamlanamadı'}
        actions={
          <Button variant="primary" onClick={onBack}>
            Sekmeyi kapat
          </Button>
        }
      >
        {keyMissing ? <ApiKeyMissingHelp /> : <p>{error.message}</p>}
      </StateMessage>
    </div>
  );
}
