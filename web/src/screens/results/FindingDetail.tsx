import { motion } from 'framer-motion';
import { lazy, Suspense } from 'react';
import { Spinner } from '../../components/ui';
import { CATEGORY_LABELS, SEVERITY_LABELS, SEVERITY_TEXT, formatDuration } from '../../lib/labels';
import { languageFor, rowTitle, type FindingRow } from './model';

const DiffView = lazy(() => import('../../components/DiffView'));

interface FindingDetailProps {
  row: FindingRow | null;
  applied: boolean;
}

export function FindingDetail({ row, applied }: FindingDetailProps) {
  if (row === null) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted">
        Ayrıntı için soldan bir öneri seçin.
      </div>
    );
  }
  // Only the text fades between findings; the diff editor stays mounted so Monaco
  // can swap models instead of being torn down on every selection.
  return (
    <div className="flex h-full flex-col">
      <motion.div
        key={row.finding.id}
        className="shrink-0 px-6 pt-5 pb-4"
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.14 }}
      >
        <DetailText row={row} applied={applied} />
      </motion.div>
      {row.suggestion ? (
        <DiffSection row={row} />
      ) : (
        <div className="flex flex-1 items-center justify-center border-t border-border px-8 text-center text-sm text-muted">
          Bu bulgu için öneri yok; düzeltmeyi elle yapabilirsiniz.
        </div>
      )}
    </div>
  );
}

function DetailText({ row, applied }: { row: FindingRow; applied: boolean }) {
  const { finding, suggestion } = row;
  return (
    <>
      <h2 className="text-[17px] leading-snug font-semibold">{rowTitle(row)}</h2>
      <p className="mt-1.5 flex flex-wrap items-center gap-x-2 font-mono text-[11.5px] text-muted">
        <span>
          {finding.file}:{finding.line_start}
        </span>
        <span>·</span>
        <span className="text-text/80">{finding.rule_code}</span>
        <span>·</span>
        <span className={SEVERITY_TEXT[finding.severity]}>{SEVERITY_LABELS[finding.severity]}</span>
        {suggestion && (
          <>
            <span>·</span>
            <span>{CATEGORY_LABELS[suggestion.category]}</span>
          </>
        )}
      </p>
      {suggestion && <VerificationLine row={row} applied={applied} />}
      {suggestion && (
        <p className="mt-4 max-h-32 overflow-auto text-[14px] leading-relaxed text-text/85">
          {suggestion.explanation}
        </p>
      )}
      <p className="mt-3 text-[12px] text-muted/80">
        <span className="font-mono">{finding.tool}:</span> {finding.message}
      </p>
    </>
  );
}

function VerificationLine({ row, applied }: { row: FindingRow; applied: boolean }) {
  const v = row.suggestion!.verification;
  const passed = v.status === 'passed';
  return (
    <div
      className={`mt-3 flex items-center gap-2 rounded-md px-2.5 py-1.5 text-[12.5px] ${passed ? 'bg-ok/8 text-ok' : 'bg-warn/8 text-warn'}`}
    >
      <span aria-hidden>{passed ? '✓' : '⚠'}</span>
      <span className="font-medium">{passed ? 'Doğrulandı' : 'Doğrulanamadı'}</span>
      <span className="min-w-0 truncate text-text/70">{v.detail}</span>
      <span className="ml-auto shrink-0 font-mono text-[11px] text-muted">
        {applied ? 'uygulandı' : passed ? formatDuration(v.duration_ms) : 'uygulanamaz'}
      </span>
    </div>
  );
}

function DiffSection({ row }: { row: FindingRow }) {
  const suggestion = row.suggestion!;
  const { patch } = suggestion;
  return (
    <section className="flex min-h-0 flex-1 flex-col border-t border-border">
      <div className="grid h-8 shrink-0 grid-cols-2 px-6 text-[11px] text-muted">
        <span className="self-center">Önce</span>
        <span className="self-center pl-2">Sonra</span>
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
  );
}
