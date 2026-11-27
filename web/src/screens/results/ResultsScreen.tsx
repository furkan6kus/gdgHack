import { AnimatePresence, motion } from 'framer-motion';
import { useMemo, useState } from 'react';
import { api, toErrorPayload } from '../../api/client';
import type { AnalyzeResult, ApplyResponse, ErrorPayload, Suggestion } from '../../api/types';
import { LogoMark } from '../../components/Logo';
import { StateMessage } from '../../components/StateMessage';
import { Button } from '../../components/ui';
import { useHotkeys } from '../../hooks/useHotkeys';
import { formatNumber } from '../../lib/labels';
import { ApplyBar, ConfirmApplyModal } from './ApplyControls';
import { FileList } from './FileList';
import { FindingDetail } from './FindingDetail';
import { FindingList } from './FindingList';
import {
  EMPTY_FILTERS,
  applyFilters,
  buildRows,
  isApplicable,
  toggleIn,
  type Filters,
} from './model';

interface ResultsScreenProps {
  jobId: string;
  result: AnalyzeResult;
  onNewAnalysis: () => void;
}

export function ResultsScreen({ jobId, result, onNewAnalysis }: ResultsScreenProps) {
  const allRows = useMemo(() => buildRows(result), [result]);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [selectedId, setSelectedId] = useState<string | null>(allRows[0]?.finding.id ?? null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [applied, setApplied] = useState<Set<string>>(new Set());
  const [pending, setPending] = useState<Suggestion[]>([]);
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<ErrorPayload | null>(null);
  const [lastApply, setLastApply] = useState<ApplyResponse | null>(null);

  const rows = useMemo(() => applyFilters(allRows, filters), [allRows, filters]);
  const selectedRow = rows.find((r) => r.finding.id === selectedId) ?? null;
  const applicable = useMemo(
    () => result.suggestions.filter((s) => isApplicable(s, applied)),
    [result.suggestions, applied],
  );

  const toggleChecked = (id: string) => {
    if (applicable.some((s) => s.id === id)) setChecked((prev) => toggleIn(prev, id));
  };

  const move = (delta: number) => {
    if (rows.length === 0) return;
    const index = rows.findIndex((r) => r.finding.id === selectedId);
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
          <div className="grid min-h-0 flex-1 grid-cols-[220px_minmax(340px,1fr)_minmax(420px,1.25fr)] divide-x divide-border">
            <FileList
              files={result.files}
              selected={filters.file}
              onSelect={(file) => setFilters((f) => ({ ...f, file }))}
            />
            <FindingList
              rows={rows}
              totalCount={allRows.length}
              filters={filters}
              selectedId={selectedRow?.finding.id ?? null}
              checked={checked}
              applied={applied}
              onToggleCategory={(c) => setFilters((f) => ({ ...f, categories: toggleIn(f.categories, c) }))}
              onToggleSeverity={(s) => setFilters((f) => ({ ...f, severities: toggleIn(f.severities, s) }))}
              onClearFilters={() => setFilters(EMPTY_FILTERS)}
              onSelect={setSelectedId}
              onToggleChecked={toggleChecked}
            />
            <div className="min-w-0 bg-panel/40">
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
  const tokens = result.token_usage.input_tokens + result.token_usage.output_tokens;
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border px-4">
      <LogoMark size={22} />
      <span className="truncate font-mono text-[13px]" title={result.root}>
        {result.root}
      </span>
      <div className="ml-auto flex items-center gap-4 font-mono text-[11px] text-muted">
        <span>{result.findings.length} bulgu</span>
        <span>{result.suggestions.length} öneri</span>
        <span title={`girdi ${formatNumber(result.token_usage.input_tokens)} · çıktı ${formatNumber(result.token_usage.output_tokens)}`}>
          {formatNumber(tokens)} token
        </span>
        <Button size="sm" onClick={onNewAnalysis}>
          Yeni analiz
        </Button>
      </div>
    </header>
  );
}

function AppliedToast({ response, onClose }: { response: ApplyResponse | null; onClose: () => void }) {
  return (
    <AnimatePresence>
      {response && (
        <motion.div
          role="status"
          className="fixed right-4 bottom-18 z-40 w-96 rounded-xl border border-ok/30 bg-panel p-4 shadow-2xl shadow-black/50"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
        >
          <div className="flex items-start gap-3">
            <span className="text-ok">✓</span>
            <div className="min-w-0 flex-1 text-sm">
              <p className="font-medium">
                {response.applied_ids.length} öneri {response.changed_files.length} dosyaya uygulandı
              </p>
              <p className="mt-1 truncate font-mono text-[11px] text-muted" title={response.backup_path}>
                Yedek: {response.backup_path}
              </p>
            </div>
            <button type="button" onClick={onClose} aria-label="Kapat" className="text-muted hover:text-text">
              ✕
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
