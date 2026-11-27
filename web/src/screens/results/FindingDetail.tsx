import { motion } from 'framer-motion';
import { lazy, Suspense } from 'react';
import { SeverityDot, Spinner, VerificationBadge } from '../../components/ui';
import { CATEGORY_LABELS, SEVERITY_LABELS, SEVERITY_TEXT, formatDuration } from '../../lib/labels';
import { languageFor, type FindingRow } from './model';

const DiffView = lazy(() => import('../../components/DiffView'));

interface FindingDetailProps {
  row: FindingRow | null;
  applied: boolean;
}

export function FindingDetail({ row, applied }: FindingDetailProps) {
  if (row === null) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted">
        Ayrıntı için bir bulgu seçin.
      </div>
    );
  }
  // Only the text fades between findings; the diff editor stays mounted so Monaco
  // can swap models instead of being torn down on every selection.
  return (
    <div className="flex h-full flex-col">
      <motion.div
        key={row.finding.id}
        initial={{ opacity: 0, x: 6 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.12 }}
      >
        <DetailHeader row={row} />
      </motion.div>
      {row.suggestion ? (
        <SuggestionBody row={row} applied={applied} />
      ) : (
        <div className="flex flex-1 items-center justify-center px-8 text-center text-sm text-muted">
          Bu bulgu için doğrulanmış bir öneri yok. Kural ihlali yukarıda; düzeltmeyi elle yapabilirsiniz.
        </div>
      )}
    </div>
  );
}

function DetailHeader({ row }: { row: FindingRow }) {
  const { finding } = row;
  const lines =
    finding.line_end > finding.line_start
      ? `${finding.line_start}–${finding.line_end}`
      : `${finding.line_start}`;
  return (
    <header className="shrink-0 border-b border-border px-5 py-3.5">
      <div className="flex items-center gap-2 text-xs">
        <SeverityDot severity={finding.severity} />
        <span className={SEVERITY_TEXT[finding.severity]}>{SEVERITY_LABELS[finding.severity]}</span>
        <span className="font-mono font-semibold">{finding.rule_code}</span>
        <span className="text-muted">· {finding.tool}</span>
        {row.suggestion && (
          <span className="ml-auto rounded bg-panel-2 px-1.5 py-px text-[10px] font-semibold tracking-wide text-muted">
            {CATEGORY_LABELS[row.suggestion.category]}
          </span>
        )}
      </div>
      <p className="mt-1.5 text-sm">{finding.message}</p>
      <p className="mt-1 font-mono text-[11.5px] text-muted">
        {finding.file}:{lines}
      </p>
    </header>
  );
}

function SuggestionBody({ row, applied }: { row: FindingRow; applied: boolean }) {
  const suggestion = row.suggestion!;
  const { verification, patch } = suggestion;
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <section className="shrink-0 px-5 pt-4 pb-3">
        <h3 className="mb-1.5 text-[11px] font-semibold tracking-wide text-muted uppercase">Açıklama</h3>
        <p className="max-h-36 overflow-auto text-[13.5px] leading-relaxed text-text/90">
          {suggestion.explanation}
        </p>
      </section>

      <section className="mx-5 mb-3 flex shrink-0 items-start gap-3 rounded-lg border border-border bg-panel-2/50 px-3 py-2.5">
        <VerificationBadge status={verification.status} />
        <div className="min-w-0 flex-1 text-xs">
          <p className="text-text/90">{verification.detail}</p>
          {verification.status === 'skipped' && (
            <p className="mt-1 text-warn">Doğrulanamadığı için bu öneri uygulanamaz.</p>
          )}
          {applied && <p className="mt-1 text-accent">Bu öneri uygulandı.</p>}
        </div>
        <span className="shrink-0 font-mono text-[11px] text-muted">
          {formatDuration(verification.duration_ms)}
        </span>
      </section>

      <section className="flex min-h-0 flex-1 flex-col border-t border-border">
        <div className="flex h-8 shrink-0 items-center justify-between px-5 font-mono text-[11px] text-muted">
          <span>önce</span>
          <span>{patch.file}</span>
          <span>sonra</span>
        </div>
        <div className="min-h-0 flex-1">
          <Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-muted">
                <Spinner className="size-5" />
              </div>
            }
          >
            <DiffView
              modelKey={suggestion.id}
              original={patch.original_text}
              modified={patch.new_text}
              language={languageFor(patch.file)}
            />
          </Suspense>
        </div>
      </section>
    </div>
  );
}
