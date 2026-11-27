import { useEffect, useRef } from 'react';
import type { Category, Severity } from '../../api/types';
import { SeverityDot, VerificationBadge } from '../../components/ui';
import { CATEGORY_CHIPS, CATEGORY_LABELS, SEVERITY_LABELS, SEVERITY_ORDER } from '../../lib/labels';
import { basename, isApplicable, type Filters, type FindingRow } from './model';

interface FindingListProps {
  rows: FindingRow[];
  totalCount: number;
  filters: Filters;
  selectedId: string | null;
  checked: ReadonlySet<string>;
  applied: ReadonlySet<string>;
  onToggleCategory: (c: Category) => void;
  onToggleSeverity: (s: Severity) => void;
  onClearFilters: () => void;
  onSelect: (findingId: string) => void;
  onToggleChecked: (suggestionId: string) => void;
}

export function FindingList(props: FindingListProps) {
  const { rows, totalCount, filters, onToggleCategory, onToggleSeverity, onClearFilters } = props;
  return (
    <section className="flex h-full flex-col">
      <div className="flex shrink-0 flex-wrap items-center gap-1.5 border-b border-border px-3 py-2">
        {CATEGORY_CHIPS.map((chip) => (
          <Chip
            key={chip.value}
            active={filters.categories.has(chip.value)}
            onClick={() => onToggleCategory(chip.value)}
          >
            {chip.label}
          </Chip>
        ))}
        <span className="mx-1 h-4 w-px bg-border" />
        {SEVERITY_ORDER.map((s) => (
          <Chip key={s} active={filters.severities.has(s)} onClick={() => onToggleSeverity(s)}>
            <SeverityDot severity={s} />
            {SEVERITY_LABELS[s]}
          </Chip>
        ))}
        <span className="ml-auto font-mono text-[11px] text-muted">
          {rows.length}/{totalCount}
        </span>
      </div>
      {rows.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-sm text-muted">
          Filtreyle eşleşen bulgu yok.
          <button type="button" onClick={onClearFilters} className="text-accent hover:underline">
            Filtreleri temizle
          </button>
        </div>
      ) : (
        <Rows {...props} />
      )}
    </section>
  );
}

function Rows({ rows, filters, selectedId, checked, applied, onSelect, onToggleChecked }: FindingListProps) {
  const selectedRef = useRef<HTMLLIElement>(null);
  useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: 'nearest' });
  }, [selectedId]);

  return (
    <ul className="min-h-0 flex-1 overflow-auto py-1" role="listbox" aria-label="Bulgular">
      {rows.map(({ finding, suggestion }) => {
        const active = finding.id === selectedId;
        const canApply = isApplicable(suggestion, applied);
        const wasApplied = suggestion !== null && applied.has(suggestion.id);
        return (
          <li
            key={finding.id}
            ref={active ? selectedRef : undefined}
            role="option"
            aria-selected={active}
            onClick={() => onSelect(finding.id)}
            className={`group relative mx-1.5 flex cursor-pointer items-start gap-2.5 rounded-md px-2.5 py-2 transition-colors ${active ? 'bg-panel-2' : 'hover:bg-panel-2/50'}`}
          >
            {active && <span className="absolute top-2 bottom-2 left-0 w-0.5 rounded-full bg-accent" />}
            <input
              type="checkbox"
              aria-label="Uygulamak için seç"
              className="mt-0.5 size-3.5 shrink-0 cursor-pointer accent-[var(--color-accent)] disabled:cursor-not-allowed disabled:opacity-25"
              disabled={!canApply}
              checked={suggestion !== null && checked.has(suggestion.id)}
              onClick={(e) => e.stopPropagation()}
              onChange={() => suggestion && onToggleChecked(suggestion.id)}
              tabIndex={-1}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-[11.5px]">
                <SeverityDot severity={finding.severity} />
                <span className="font-mono text-muted">
                  {filters.file === null && `${basename(finding.file)}:`}
                  {finding.line_start}
                </span>
                <span className="font-mono font-medium text-text">{finding.rule_code}</span>
                {suggestion && (
                  <span className="rounded bg-panel px-1 text-[10px] font-semibold tracking-wide text-muted">
                    {CATEGORY_LABELS[suggestion.category]}
                  </span>
                )}
                <span className="ml-auto">
                  {wasApplied ? (
                    <span className="text-[11px] text-accent">uygulandı</span>
                  ) : (
                    <VerificationBadge status={suggestion?.verification.status ?? null} compact />
                  )}
                </span>
              </div>
              <p className="mt-0.5 truncate text-[13px] text-muted group-hover:text-text/90">
                {finding.message}
              </p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`inline-flex h-6 items-center gap-1.5 rounded-md border px-2 text-[11px] font-medium transition-colors ${active ? 'border-accent/50 bg-accent-soft text-text' : 'border-border text-muted hover:border-muted/50 hover:text-text'}`}
    >
      {children}
    </button>
  );
}
