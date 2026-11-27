import { AnimatePresence, motion } from 'framer-motion';
import type { VerificationResult } from '../../api/types';
import { useEffect, useRef, useState } from 'react';
import { InlineCode } from '../../components/InlineCode';
import { Pill } from '../../components/ui';
import { formatDuration } from '../../lib/labels';
import { lineDiff } from './lineDiff';
import { isApplicable, rowTitle, type FindingRow } from './model';

interface FindingCardsProps {
  rows: FindingRow[];
  /** "Öneri N" label of each suggestion row, keyed by finding id (matches the code pane). */
  labels: ReadonlyMap<string, string>;
  selectedId: string | null;
  checked: ReadonlySet<string>;
  applied: ReadonlySet<string>;
  onSelect: (findingId: string) => void;
  onToggleChecked: (suggestionId: string) => void;
  onApplyOne: (row: FindingRow) => void;
}

export function FindingCards(props: FindingCardsProps) {
  const { rows, selectedId } = props;
  const selectedRef = useRef<HTMLLIElement>(null);
  useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [selectedId]);

  if (rows.length === 0) {
    return <p className="p-8 text-center text-sm text-subtle">Bu dosyada sorun bulunmadı.</p>;
  }
  return (
    <ul className="space-y-3">
      {rows.map((row) => (
        <Card
          key={row.finding.id}
          row={row}
          {...props}
          selected={row.finding.id === selectedId}
          cardRef={row.finding.id === selectedId ? selectedRef : undefined}
        />
      ))}
    </ul>
  );
}

interface CardProps extends FindingCardsProps {
  row: FindingRow;
  selected: boolean;
  cardRef?: React.RefObject<HTMLLIElement>;
}

function Card({
  row,
  labels,
  selected,
  checked,
  applied,
  onSelect,
  onToggleChecked,
  onApplyOne,
  cardRef,
}: CardProps) {
  const { finding, suggestion } = row;
  const canApply = isApplicable(suggestion, applied);
  const isApplied = suggestion !== null && applied.has(suggestion.id);
  const label = labels.get(finding.id);
  return (
    <li
      ref={cardRef}
      className={`overflow-hidden rounded-[var(--radius-sheet)] border bg-panel transition-colors ${selected ? 'border-accent/50 ring-1 ring-accent/20' : 'border-border hover:border-border-strong'}`}
    >
      <div
        role="button"
        tabIndex={0}
        aria-expanded={selected}
        onClick={() => onSelect(finding.id)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') onSelect(finding.id);
        }}
        className="flex cursor-pointer items-start gap-3 px-4 py-3.5 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent"
      >
        <span className="pt-0.5">
          {canApply ? (
            <input
              type="checkbox"
              aria-label="Uygulamak için seç"
              className="size-[18px] cursor-pointer rounded accent-[var(--color-accent)]"
              checked={checked.has(suggestion!.id)}
              onClick={(e) => e.stopPropagation()}
              onChange={() => onToggleChecked(suggestion!.id)}
            />
          ) : (
            <span className="block size-[18px] rounded border border-border bg-sunken" aria-hidden />
          )}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[15px] leading-snug font-semibold text-strong">
            <InlineCode text={rowTitle(row)} />
          </p>
          <p className={`mt-0.5 text-[13px] text-subtle ${selected ? '' : 'truncate'}`}>
            <span className="font-mono text-[12px]">
              {finding.file}:{finding.line_start}
            </span>
            {label && <span className="ml-2 font-medium text-accent">{label}</span>}
            {suggestion && !selected && (
              <span className="ml-2">
                <InlineCode text={firstSentence(suggestion.explanation)} />
              </span>
            )}
          </p>
        </div>
        <StatusBadge row={row} applied={isApplied} />
        <motion.span
          aria-hidden
          animate={{ rotate: selected ? 90 : 0 }}
          className="pt-0.5 text-lg leading-none text-hint"
        >
          ›
        </motion.span>
      </div>
      <AnimatePresence initial={false}>
        {selected && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            <Expanded row={row} canApply={canApply} applied={isApplied} onApplyOne={onApplyOne} />
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  );
}

function Expanded({
  row,
  canApply,
  applied,
  onApplyOne,
}: {
  row: FindingRow;
  canApply: boolean;
  applied: boolean;
  onApplyOne: (row: FindingRow) => void;
}) {
  const { finding, suggestion } = row;
  const [showDetail, setShowDetail] = useState(false);
  if (!suggestion) {
    return (
      <div className="border-t border-border px-4 py-3.5 pl-[46px] text-sm leading-relaxed text-muted">
        <InlineCode text={finding.message} />. Bu bulgu için denenmiş bir düzeltme yok; soldaki kodda{' '}
        {finding.line_start}. satırı elle düzeltin.
      </div>
    );
  }
  const v = suggestion.verification;
  const diff = lineDiff(suggestion.patch.original_text, suggestion.patch.new_text);
  return (
    <div className="space-y-3 px-4 pb-4 pl-[46px]">
      <p className="max-w-[64ch] text-sm leading-relaxed text-muted">
        <InlineCode text={suggestion.explanation} />
      </p>
      <pre className="overflow-x-auto rounded-[var(--radius-control)] border border-border bg-panel-2 py-2 font-mono text-[12.5px] leading-[1.7]">
        {diff.map((line, i) => (
          <div
            key={i}
            className={
              line.kind === 'del'
                ? 'bg-err-wash px-3 text-err-ink'
                : line.kind === 'add'
                  ? 'bg-ok-wash px-3 text-ok-ink'
                  : 'px-3 text-subtle'
            }
          >
            <span aria-hidden className="mr-3 inline-block w-2 select-none">
              {line.kind === 'del' ? '-' : line.kind === 'add' ? '+' : ' '}
            </span>
            {line.text || ' '}
          </div>
        ))}
      </pre>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-[13px]">
        <span className={v.status === 'passed' ? 'text-ok-ink' : 'text-subtle'}>{verificationText(v, applied)}</span>
        <button
          type="button"
          onClick={() => setShowDetail((d) => !d)}
          className="font-medium text-accent hover:underline focus-visible:outline-2 focus-visible:outline-accent"
        >
          {showDetail ? 'Detayı gizle' : 'Detay'}
        </button>
        {canApply && (
          <button
            type="button"
            onClick={() => onApplyOne(row)}
            className="ml-auto rounded-[var(--radius-control)] border border-border px-3 py-1 font-medium text-strong hover:bg-hover focus-visible:outline-2 focus-visible:outline-accent"
          >
            Yalnız bunu uygula
          </button>
        )}
      </div>
      {showDetail && (
        <div className="rounded-[var(--radius-control)] bg-sunken p-3 text-[13px] leading-relaxed text-muted">
          <p>
            <span className="font-medium text-strong">Doğrulama: </span>
            {v.detail || 'Ayrıntı yok.'}
          </p>
          <p className="mt-1">
            <span className="font-medium text-strong">Statik analiz ({finding.rule_code}): </span>
            <InlineCode text={finding.message} />
          </p>
        </div>
      )}
    </div>
  );
}

function verificationText(v: VerificationResult, applied: boolean): string {
  if (applied) return 'Bu düzeltme uygulandı.';
  if (v.status === 'passed' && v.tested === false) return 'Kod derleniyor; projede test olmadığı için testle denenmedi.';
  if (v.status === 'passed') return `Projenin testleri bu düzeltmeyle geçti (${formatDuration(v.duration_ms)}).`;
  return 'Bu düzeltme denenemedi, bu yüzden uygulanamaz.';
}

function StatusBadge({ row, applied }: { row: FindingRow; applied: boolean }) {
  const v = row.suggestion?.verification;
  if (applied) return <Pill tone="info" dot={false}>Uygulandı</Pill>;
  if (!v) return <Pill tone="warn" dot={false}>Elle düzeltin</Pill>;
  if (v.status === 'passed' && v.tested === false) return <Pill tone="ok" dot={false}>✓ Hazır</Pill>;
  if (v.status === 'passed') return <Pill tone="ok" dot={false}>✓ Doğrulandı</Pill>;
  return <Pill dot={false}>İsteğe bağlı</Pill>;
}

function firstSentence(text: string): string {
  const end = text.search(/[.!?](\s|$)/);
  return end === -1 ? text : text.slice(0, end + 1);
}
