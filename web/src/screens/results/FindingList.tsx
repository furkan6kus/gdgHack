import { AnimatePresence, motion } from 'framer-motion';
import { useEffect, useRef } from 'react';
import { Pill } from '../../components/ui';
import { CATEGORY_CHIPS, SEVERITY_BG, SEVERITY_LABELS } from '../../lib/labels';
import { groupByFile, isApplicable, rowTitle, type CategoryFilter, type FindingRow } from './model';

interface FindingListProps {
  rows: FindingRow[];
  orphans: FindingRow[];
  showOrphans: boolean;
  onToggleOrphans: () => void;
  category: CategoryFilter;
  counts: Record<CategoryFilter, number>;
  onCategory: (c: CategoryFilter) => void;
  selectedId: string | null;
  checked: ReadonlySet<string>;
  applied: ReadonlySet<string>;
  onSelect: (findingId: string) => void;
  onToggleChecked: (suggestionId: string) => void;
}

export function FindingList(props: FindingListProps) {
  const { rows, orphans, showOrphans, onToggleOrphans, category, counts, onCategory } = props;
  const selectedRef = useRef<HTMLLIElement>(null!);
  useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: 'nearest' });
  }, [props.selectedId]);

  return (
    <section className="flex h-full min-w-0 flex-col">
      <CategoryTabs value={category} counts={counts} onChange={onCategory} />
      <div className="min-h-0 flex-1 overflow-auto px-2 pb-4">
        {rows.length === 0 && (
          <p className="px-5 py-10 text-center text-sm text-subtle">Bu kategoride öneri yok.</p>
        )}
        {groupByFile(rows).map((group) => (
          <div key={group.file}>
            <GroupHeader file={group.file} count={group.rows.length} />
            <ul>
              {group.rows.map((row) => (
                <Row key={row.finding.id} row={row} {...props} rowRef={selectedRef} />
              ))}
            </ul>
          </div>
        ))}
        {orphans.length > 0 && category === 'all' && (
          <div className="mt-3 border-t border-border pt-2">
            <button
              type="button"
              onClick={onToggleOrphans}
              className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-xs font-semibold tracking-wider text-subtle uppercase hover:text-text focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:outline-none"
            >
              <motion.span animate={{ rotate: showOrphans ? 90 : 0 }} className="inline-block">
                ▸
              </motion.span>
              Önerisiz bulgular ({orphans.length})
            </button>
            <AnimatePresence initial={false}>
              {showOrphans && (
                <motion.ul
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  {orphans.map((row) => (
                    <Row key={row.finding.id} row={row} {...props} rowRef={selectedRef} showFile />
                  ))}
                </motion.ul>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>
    </section>
  );
}

function CategoryTabs({
  value,
  counts,
  onChange,
}: {
  value: CategoryFilter;
  counts: Record<CategoryFilter, number>;
  onChange: (c: CategoryFilter) => void;
}) {
  const tabs: { value: CategoryFilter; label: string }[] = [
    { value: 'all', label: 'Tümü' },
    ...CATEGORY_CHIPS,
  ];
  return (
    <div className="flex shrink-0 flex-wrap gap-1 border-b border-border p-3" role="tablist">
      {tabs.map((tab) => {
        const active = tab.value === value;
        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.value)}
            className={`relative h-8 rounded-lg px-3 text-xs font-semibold tracking-wide transition-colors focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:outline-none ${active ? 'text-strong' : 'text-muted hover:text-text'}`}
          >
            {active && (
              <motion.span
                layoutId="category-tab"
                className="absolute inset-0 rounded-lg bg-accent-soft ring-1 ring-accent/40"
                transition={{ duration: 0.18 }}
              />
            )}
            <span className="relative">
              {tab.label}
              <span className="ml-1.5 text-subtle">{counts[tab.value]}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

function GroupHeader({ file, count }: { file: string; count: number }) {
  return (
    <div className="sticky top-0 z-10 flex items-center justify-between gap-3 bg-panel/95 px-3 pt-4 pb-2 font-mono text-[11.5px] text-muted backdrop-blur">
      <span className="truncate" title={file}>
        {file}
      </span>
      <span className="font-sans text-xs text-subtle">{count}</span>
    </div>
  );
}

interface RowProps extends FindingListProps {
  row: FindingRow;
  rowRef: React.RefObject<HTMLLIElement>;
  showFile?: boolean;
}

function Row({ row, rowRef, showFile, selectedId, checked, applied, onSelect, onToggleChecked }: RowProps) {
  const { finding, suggestion } = row;
  const active = finding.id === selectedId;
  const canApply = isApplicable(suggestion, applied);
  return (
    <li
      ref={active ? rowRef : undefined}
      aria-selected={active}
      onClick={() => onSelect(finding.id)}
      className={`relative flex cursor-pointer items-center gap-3 rounded-xl py-2.5 pr-3 pl-4 transition-colors ${active ? 'bg-accent-soft ring-1 ring-accent/60' : 'hover:bg-white/[0.04]'}`}
    >
      <span
        title={SEVERITY_LABELS[finding.severity]}
        className={`absolute top-3 bottom-3 left-1.5 w-[3px] rounded-full ${SEVERITY_BG[finding.severity]} ${active ? '' : 'opacity-70'}`}
      />
      {canApply ? (
        <input
          type="checkbox"
          aria-label="Uygulamak için seç"
          className="size-4 shrink-0 cursor-pointer accent-[var(--color-accent)]"
          checked={checked.has(suggestion!.id)}
          onClick={(e) => e.stopPropagation()}
          onChange={() => onToggleChecked(suggestion!.id)}
          tabIndex={-1}
        />
      ) : (
        <span className="size-4 shrink-0" />
      )}
      <div className="min-w-0 flex-1">
        <p className={`truncate text-sm ${active ? 'font-medium text-strong' : 'text-text'}`}>{rowTitle(row)}</p>
        <p className="mt-0.5 font-mono text-[11px] text-subtle">
          {showFile ? `${finding.file}:` : 'L'}
          {finding.line_start} · {finding.rule_code}
        </p>
      </div>
      <StatusIcon row={row} applied={suggestion !== null && applied.has(suggestion.id)} />
    </li>
  );
}

function StatusIcon({ row, applied }: { row: FindingRow; applied: boolean }) {
  const status = row.suggestion?.verification.status;
  if (applied) return <Pill tone="info">uygulandı</Pill>;
  if (status === 'passed')
    return (
      <span title="Doğrulandı">
        <Pill tone="ok" dot={false}>✓</Pill>
      </span>
    );
  if (status === 'skipped')
    return (
      <span title="Doğrulanamadı — uygulanamaz">
        <Pill tone="warn" dot={false}>⚠</Pill>
      </span>
    );
  return null;
}
