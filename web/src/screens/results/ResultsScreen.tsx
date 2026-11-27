import { AnimatePresence, motion } from 'framer-motion';
import { lazy, Suspense, useMemo, useState } from 'react';
import { api, toErrorPayload } from '../../api/client';
import type { AnalyzeResult, ApplyResponse, ErrorPayload, LLMChoice, Suggestion } from '../../api/types';
import type { LineMark } from '../../components/CodeView';
import { StateMessage } from '../../components/StateMessage';
import { Button, CARD, Callout, Pill, Spinner } from '../../components/ui';
import { useHotkeys } from '../../hooks/useHotkeys';
import { ConfirmApplyModal } from './ApplyControls';
import { ChatPanel, type ChatEntry } from './ChatPanel';
import { FindingCards } from './FindingCards';
import { buildRows, isApplicable, languageFor, orphanRows, suggestionRows, toggleIn } from './model';

const CodeView = lazy(() => import('../../components/CodeView'));

interface ResultsScreenProps {
  jobId: string;
  result: AnalyzeResult;
  onNewAnalysis: () => void;
  /** Only the visible tab reacts to keyboard shortcuts. */
  active?: boolean;
  /** Called after a successful apply (the app re-analyzes the same path). */
  onApplied?: (response: ApplyResponse) => void;
  /** One-line message shown above the results, e.g. what the last apply did. */
  notice?: string;
  /** Run the same path again (the "Yeniden analiz et" button). */
  onReanalyze?: () => void;
  /** The tab's analyzed path, used by the chat. */
  path?: string;
  chat?: ChatEntry[];
  onChat?: (entries: ChatEntry[]) => void;
  onChatBusy?: (busy: boolean) => void;
  onChatApplied?: (response: ApplyResponse, explanation: string) => void;
  llm?: LLMChoice | null;
  onCost?: (cost: number | null | undefined) => void;
}

export function ResultsScreen({
  jobId,
  result,
  onNewAnalysis,
  active = true,
  onApplied,
  notice,
  onReanalyze,
  path,
  chat = [],
  onChat,
  onChatBusy,
  onChatApplied,
  llm,
  onCost,
}: ResultsScreenProps) {
  const [panel, setPanel] = useState<'findings' | 'chat'>(chat.length > 0 ? 'chat' : 'findings');
  const allRows = useMemo(() => buildRows(result), [result]);
  // Ready fixes first, then findings that need a manual fix.
  const rows = useMemo(() => [...suggestionRows(allRows, 'all'), ...orphanRows(allRows)], [allRows]);
  const labels = useMemo(() => {
    const map = new Map<string, string>();
    suggestionRows(allRows, 'all').forEach((row, i) => map.set(row.finding.id, `Öneri ${i + 1}`));
    return map;
  }, [allRows]);
  const [selectedId, setSelectedId] = useState<string | null>(() => rows[0]?.finding.id ?? null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [applied, setApplied] = useState<Set<string>>(new Set());
  const [pending, setPending] = useState<Suggestion[]>([]);
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<ErrorPayload | null>(null);
  const [lastApply, setLastApply] = useState<ApplyResponse | null>(null);

  const selectedRow = rows.find((r) => r.finding.id === selectedId) ?? rows[0] ?? null;
  const file = selectedRow?.finding.file ?? result.files[0]?.path ?? '';
  const chatPanel =
    path && onChat && file ? (
      <ChatPanel
        path={path}
        file={file}
        entries={chat}
        onEntries={onChat}
        onBusy={(busy) => onChatBusy?.(busy)}
        onApplied={(response, explanation) => onChatApplied?.(response, explanation)}
        llm={llm ?? undefined}
        onCost={(cost) => onCost?.(cost)}
      />
    ) : null;
  const applicable = useMemo(
    () => result.suggestions.filter((s) => isApplicable(s, applied)),
    [result.suggestions, applied],
  );
  const ready = result.suggestions.filter((s) => s.verification.status === 'passed').length;

  const toggleChecked = (id: string) => {
    if (applicable.some((s) => s.id === id)) setChecked((prev) => toggleIn(prev, id));
  };

  const move = (delta: number) => {
    if (rows.length === 0) return;
    const index = rows.findIndex((r) => r.finding.id === selectedRow?.finding.id);
    const next = Math.min(rows.length - 1, Math.max(0, index + delta));
    setSelectedId(rows[index === -1 ? 0 : next].finding.id);
  };

  useHotkeys(
    {
      j: () => move(1),
      k: () => move(-1),
      ArrowDown: () => move(1),
      ArrowUp: () => move(-1),
      ' ': () => selectedRow?.suggestion && toggleChecked(selectedRow.suggestion.id),
    },
    active && pending.length === 0,
  );

  const confirmApply = async () => {
    setApplying(true);
    setApplyError(null);
    try {
      const response = await api.apply(jobId, pending.map((s) => s.id));
      setApplied((prev) => new Set([...prev, ...response.applied_ids]));
      setChecked((prev) => new Set([...prev].filter((id) => !response.applied_ids.includes(id))));
      setLastApply(response);
      setPending([]);
      onApplied?.(response);
    } catch (err) {
      setApplyError(toErrorPayload(err));
    } finally {
      setApplying(false);
    }
  };

  const openConfirm = (suggestions: Suggestion[]) => {
    setApplyError(null);
    setPending(suggestions);
  };

  const marks = useMemo<LineMark[]>(
    () =>
      rows
        .filter((r) => r.finding.file === file)
        .map((r) => ({
          line: r.finding.line_start,
          kind: r.suggestion ? 'suggestion' : 'warn',
          label: labels.get(r.finding.id) ?? 'Bulgu',
        })),
    [rows, file, labels],
  );

  const messages = (
    <>
      {notice && (
        <Callout tone="ok" className="!py-3 text-sm">
          {notice}
        </Callout>
      )}
      {(result.warnings?.length ?? 0) > 0 && (
        <Callout tone="warn">
          <ul className="space-y-1 text-sm">
            {result.warnings?.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </Callout>
      )}
    </>
  );

  if (result.findings.length === 0) {
    return (
      <div className="flex h-full flex-col gap-3 p-4 sm:p-6">
        {messages}
        <div className="flex flex-1 items-center justify-center">
          <StateMessage
            icon="✓"
            tone="ok"
            title="Sorun bulunmadı"
            actions={<Button onClick={onNewAnalysis}>Başka dosya analiz et</Button>}
          >
            Statik analiz {result.files.length} dosyada sorun bulmadı.
          </StateMessage>
        </div>
        {chatPanel && <div className={`${CARD} h-[45%] min-h-0 overflow-hidden`}>{chatPanel}</div>}
      </div>
    );
  }

  return (
    <div className="relative flex h-full flex-col">
      {(notice || (result.warnings?.length ?? 0) > 0) && (
        <div className="shrink-0 space-y-2 px-4 pt-4 sm:px-6">{messages}</div>
      )}
      <div className="grid min-h-0 flex-1 grid-cols-1 grid-rows-[minmax(0,1fr)_minmax(0,1fr)] gap-5 p-4 pb-28 sm:p-6 sm:pb-28 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:grid-rows-[minmax(0,1fr)]">
        <CodePane
          file={file}
          source={result.sources?.[file]}
          marks={marks}
          focusLine={selectedRow?.finding.file === file ? selectedRow.finding.line_start : null}
          onReanalyze={onReanalyze}
        />
        <section className={`${CARD} flex min-h-0 min-w-0 flex-col`}>
          <header className="flex shrink-0 items-start gap-4 border-b border-border px-5 py-4">
            <div className="min-w-0 flex-1">
              <div className="inline-flex rounded-[var(--radius-control)] bg-sunken p-0.5" role="tablist">
                {(
                  [
                    ['findings', 'Bulgular ve İyileştirmeler'],
                    ['chat', 'Claude'],
                  ] as const
                ).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    role="tab"
                    aria-selected={panel === value}
                    onClick={() => setPanel(value)}
                    className={`rounded-[8px] px-3 py-1.5 text-[13px] font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-accent ${panel === value ? 'bg-panel text-strong shadow-sm' : 'text-subtle hover:text-strong'}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <p className="mt-1.5 text-[13px] text-subtle">
                {panel === 'findings'
                  ? 'Uygulamak istediğiniz düzeltmeleri seçin.'
                  : 'İstediğiniz değişikliği yazın; Claude kodu önerir, siz uygularsınız.'}
                {result.estimated_cost_usd != null && panel === 'findings' && (
                  <span className="text-hint"> Analiz maliyeti {formatUsd(result.estimated_cost_usd)}.</span>
                )}
              </p>
            </div>
            <Pill tone={ready > 0 ? 'ok' : 'neutral'} dot={false}>
              {ready} Hazır
            </Pill>
          </header>
          {panel === 'chat' ? (
            <div className="min-h-0 flex-1">{chatPanel}</div>
          ) : (
          <div className="min-h-0 flex-1 overflow-auto p-4">
            <FindingCards
              rows={rows}
              labels={labels}
              selectedId={selectedRow?.finding.id ?? null}
              checked={checked}
              applied={applied}
              onSelect={setSelectedId}
              onToggleChecked={toggleChecked}
              onApplyOne={(row) => row.suggestion && openConfirm([row.suggestion])}
            />
          </div>
          )}
        </section>
      </div>
      <FloatingApplyBar
        checked={applicable.filter((s) => checked.has(s.id))}
        applicableCount={applicable.length}
        onSelectAll={() => setChecked(new Set(applicable.map((s) => s.id)))}
        onApply={() => openConfirm(applicable.filter((s) => checked.has(s.id)))}
      />
      <ConfirmApplyModal
        suggestions={pending}
        root={result.root}
        applying={applying}
        error={applyError}
        onConfirm={confirmApply}
        onClose={() => setPending([])}
      />
      <AppliedToast response={lastApply} onClose={() => setLastApply(null)} />
    </div>
  );
}

function CodePane({
  file,
  source,
  marks,
  focusLine,
  onReanalyze,
}: {
  file: string;
  source: string | undefined;
  marks: LineMark[];
  focusLine: number | null;
  onReanalyze?: () => void;
}) {
  const name = file.split(/[\\/]/).filter(Boolean).pop() ?? file;
  const language = languageFor(file);
  const lineCount = source === undefined ? null : source.split('\n').length - (source.endsWith('\n') ? 1 : 0);
  return (
    <section className={`${CARD} flex min-h-0 min-w-0 flex-col overflow-hidden`}>
      <header className="flex shrink-0 items-baseline gap-3 border-b border-border px-5 py-3.5">
        <h2 className="truncate font-mono text-[15px] font-medium text-strong" title={file}>
          {name}
        </h2>
        <span className="text-[13px] text-subtle">{LANGUAGE_NAMES[language] ?? language}</span>
        {lineCount !== null && <span className="text-[13px] text-subtle">{lineCount} satır</span>}
      </header>
      <div className="min-h-0 flex-1">
        {source === undefined ? (
          <p className="p-8 text-center text-sm text-subtle">Bu dosyanın içeriği gösterilemiyor.</p>
        ) : (
          <Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-subtle">
                <Spinner className="size-5" />
              </div>
            }
          >
            <CodeView path={file} source={source} language={language} marks={marks} focusLine={focusLine} />
          </Suspense>
        )}
      </div>
      <footer className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-2 border-t border-border px-5 py-3">
        {onReanalyze && (
          <Button variant="primary" size="sm" onClick={onReanalyze}>
            ▶ Yeniden analiz et
          </Button>
        )}
        <span className="text-[13px] text-hint">Tüm testler ve kontroller yerel ortamda yürütülür.</span>
      </footer>
    </section>
  );
}

const LANGUAGE_NAMES: Record<string, string> = {
  python: 'Python',
  typescript: 'TypeScript',
  javascript: 'JavaScript',
  markdown: 'Markdown',
  plaintext: 'Metin',
};

function FloatingApplyBar({
  checked,
  applicableCount,
  onSelectAll,
  onApply,
}: {
  checked: Suggestion[];
  applicableCount: number;
  onSelectAll: () => void;
  onApply: () => void;
}) {
  const files = [...new Set(checked.map((s) => s.patch.file.split(/[\\/]/).pop() ?? s.patch.file))];
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-4 flex justify-center px-4">
      <div className="pointer-events-auto flex w-full max-w-3xl flex-wrap items-center gap-3 rounded-[var(--radius-sheet)] border border-border bg-panel/95 px-4 py-3 shadow-lg shadow-strong/10 backdrop-blur">
        <p className="min-w-0 flex-1 text-sm text-muted">
          {checked.length > 0 ? (
            <>
              <span aria-hidden className="mr-2 inline-block size-2 rounded-full bg-ok" />
              <span className="font-semibold text-strong">{checked.length} iyileştirme seçildi</span>
              <span className="text-subtle"> • {files.join(', ')} güncellenmeye hazır</span>
            </>
          ) : applicableCount > 0 ? (
            'Uygulamak istediğiniz düzeltmeleri işaretleyin.'
          ) : (
            'Uygulanmaya hazır düzeltme yok.'
          )}
        </p>
        <Button size="sm" onClick={onSelectAll} disabled={applicableCount === 0}>
          Tümünü seç
        </Button>
        <Button size="sm" variant="primary" onClick={onApply} disabled={checked.length === 0}>
          Seçilenleri uygula →
        </Button>
      </div>
    </div>
  );
}

function formatUsd(value: number): string {
  return '$' + value.toFixed(value < 0.01 ? 4 : 2);
}

function AppliedToast({ response, onClose }: { response: ApplyResponse | null; onClose: () => void }) {
  return (
    <AnimatePresence>
      {response && (
        <motion.div
          role="status"
          className="fixed right-4 bottom-20 z-40 w-[min(24rem,calc(100vw-2rem))] rounded-[var(--radius-sheet)] border border-border border-l-[3px] border-l-ok bg-panel p-4 shadow-lg shadow-strong/10"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
        >
          <div className="flex items-start gap-3">
            <span className="text-ok-ink">✓</span>
            <div className="min-w-0 flex-1 text-sm">
              <p className="font-semibold text-strong">
                {response.applied_ids.length} öneri {response.changed_files.length} dosyaya uygulandı
              </p>
              <p className="mt-1 truncate font-mono text-[11px] text-subtle" title={response.backup_path}>
                Yedek: {response.backup_path}
              </p>
            </div>
            <button type="button" onClick={onClose} aria-label="Kapat" className="rounded-[var(--radius-control)] text-muted hover:text-text focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:outline-none">
              ✕
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
