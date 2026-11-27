import { AnimatePresence, motion } from 'framer-motion';
import { useMemo, useState } from 'react';
import { api, toErrorPayload } from '../../api/client';
import type { AnalyzeResult, ApplyResponse, ErrorPayload, Suggestion } from '../../api/types';
import { LogoMark } from '../../components/Logo';
import { StateMessage } from '../../components/StateMessage';
import { Button, CARD, Callout, StatBadge } from '../../components/ui';
import { useHotkeys } from '../../hooks/useHotkeys';
import { formatNumber } from '../../lib/labels';
import { ApplyBar, ConfirmApplyModal } from './ApplyControls';
import { FindingDetail } from './FindingDetail';
import { FindingList } from './FindingList';
import {
  buildRows,
  countByCategory,
  isApplicable,
  orphanRows,
  suggestionRows,
  toggleIn,
  type CategoryFilter,
} from './model';

interface ResultsScreenProps {
  jobId: string;
  result: AnalyzeResult;
  onNewAnalysis: () => void;
}

export function ResultsScreen({ jobId, result, onNewAnalysis }: ResultsScreenProps) {
  const allRows = useMemo(() => buildRows(result), [result]);
  const [category, setCategory] = useState<CategoryFilter>('all');
  const [showOrphans, setShowOrphans] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(
    () => suggestionRows(allRows, 'all')[0]?.finding.id ?? null,
  );
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [applied, setApplied] = useState<Set<string>>(new Set());
  const [pending, setPending] = useState<Suggestion[]>([]);
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<ErrorPayload | null>(null);
  const [lastApply, setLastApply] = useState<ApplyResponse | null>(null);

  const rows = useMemo(() => suggestionRows(allRows, category), [allRows, category]);
  const orphans = useMemo(() => orphanRows(allRows), [allRows]);
  const counts = useMemo(() => countByCategory(allRows), [allRows]);
  // Navigation order matches what is visible: suggestion rows, then expanded orphans.
  const visible = useMemo(
    () => (showOrphans && category === 'all' ? [...rows, ...orphans] : rows),
    [rows, orphans, showOrphans, category],
  );
  const selectedRow = visible.find((r) => r.finding.id === selectedId) ?? null;
  const applicable = useMemo(
    () => result.suggestions.filter((s) => isApplicable(s, applied)),
    [result.suggestions, applied],
  );

  const toggleChecked = (id: string) => {
    if (applicable.some((s) => s.id === id)) setChecked((prev) => toggleIn(prev, id));
  };

  const move = (delta: number) => {
    if (visible.length === 0) return;
    const index = visible.findIndex((r) => r.finding.id === selectedId);
    const next = Math.min(visible.length - 1, Math.max(0, index + delta));
    setSelectedId(visible[index === -1 ? 0 : next].finding.id);
  };

  const changeCategory = (next: CategoryFilter) => {
    setCategory(next);
    const first = suggestionRows(allRows, next)[0];
    if (first) setSelectedId(first.finding.id);
  };

  useHotkeys(
    {
      j: () => move(1),
      k: () => move(-1),
      ArrowDown: () => move(1),
      ArrowUp: () => move(-1),
      ' ': () => selectedRow?.suggestion && toggleChecked(selectedRow.suggestion.id),
    },
    pending.length === 0,
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

  return (
    <div className="flex h-full flex-col">
      <ResultsHeader result={result} onNewAnalysis={onNewAnalysis} />
      {(result.warnings?.length ?? 0) > 0 && (
        <div className="shrink-0 px-4 pt-3 sm:px-6">
          <Callout tone="warn">
            <ul className="space-y-1 text-sm">
              {result.warnings?.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </Callout>
        </div>
      )}
      {result.findings.length === 0 ? (
        <div className="flex flex-1 items-center justify-center">
          <StateMessage
            icon="✓"
            tone="ok"
            title="Hiç bulgu yok"
            actions={<Button onClick={onNewAnalysis}>Yeni analiz</Button>}
          >
            Statik analiz {result.files.length} dosyada sorun bulmadı.
          </StateMessage>
        </div>
      ) : (
        <>
          <div className="grid min-h-0 flex-1 grid-cols-1 grid-rows-[minmax(0,1fr)_minmax(0,1fr)] gap-6 p-4 sm:p-6 lg:grid-cols-[minmax(340px,2fr)_3fr] lg:grid-rows-[minmax(0,1fr)]">
            <div className={`${CARD} min-h-0 min-w-0 overflow-hidden`}>
            <FindingList
              rows={rows}
              orphans={orphans}
              showOrphans={showOrphans}
              onToggleOrphans={() => setShowOrphans((v) => !v)}
              category={category}
              counts={counts}
              onCategory={changeCategory}
              selectedId={selectedRow?.finding.id ?? null}
              checked={checked}
              applied={applied}
              onSelect={setSelectedId}
              onToggleChecked={toggleChecked}
            />
            </div>
            <div className={`${CARD} min-h-0 min-w-0 overflow-hidden`}>
              <FindingDetail
                row={selectedRow}
                applied={selectedRow?.suggestion ? applied.has(selectedRow.suggestion.id) : false}
              />
            </div>
          </div>
          <ApplyBar
            checkedCount={checked.size}
            applicableCount={applicable.length}
            onApplySelected={() => openConfirm(applicable.filter((s) => checked.has(s.id)))}
            onApplyAll={() => openConfirm(applicable)}
            onSelectNone={() => setChecked(new Set())}
          />
        </>
      )}
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

function ResultsHeader({ result, onNewAnalysis }: { result: AnalyzeResult; onNewAnalysis: () => void }) {
  const { input_tokens, output_tokens } = result.token_usage;
  const cost = result.estimated_cost_usd;
  const costText = cost != null ? ` · tahmini maliyet ${formatUsd(cost)}` : '';
  const tokens = `${formatNumber(input_tokens + output_tokens)} token (girdi ${formatNumber(input_tokens)}, çıktı ${formatNumber(output_tokens)})${costText}`;
  return (
    <header className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-3 border-b border-border/80 px-4 py-4 sm:px-6">
      <LogoMark size={28} />
      <h1 className="min-w-0 flex-1 basis-48 truncate font-mono text-base font-semibold text-strong" title={result.root}>
        {result.root}
      </h1>
      <div className="flex flex-wrap items-center gap-2" title={tokens}>
        <StatBadge dot="bg-err">
          Bulgular: <b className="font-semibold text-strong">{result.findings.length}</b>
        </StatBadge>
        <StatBadge dot="bg-ok">
          Öneriler: <b className="font-semibold text-strong">{result.suggestions.length}</b>
        </StatBadge>
        {cost != null && (
          <StatBadge>
            Tahmini maliyet: <b className="font-semibold text-strong">{formatUsd(cost)}</b>
          </StatBadge>
        )}
      </div>
      <Button size="sm" onClick={onNewAnalysis}>
        Yeni analiz
      </Button>
    </header>
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
          className="fixed right-4 bottom-20 z-40 w-[min(24rem,calc(100vw-2rem))] rounded-2xl border border-ok/20 bg-panel p-4 shadow-2xl shadow-black/50"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
        >
          <div className="flex items-start gap-3">
            <span className="text-emerald-300">✓</span>
            <div className="min-w-0 flex-1 text-sm">
              <p className="font-semibold text-strong">
                {response.applied_ids.length} öneri {response.changed_files.length} dosyaya uygulandı
              </p>
              <p className="mt-1 truncate font-mono text-[11px] text-subtle" title={response.backup_path}>
                Yedek: {response.backup_path}
              </p>
            </div>
            <button type="button" onClick={onClose} aria-label="Kapat" className="rounded-lg text-muted hover:text-text focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:outline-none">
              ✕
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
