import { motion } from 'framer-motion';
import { lazy, Suspense } from 'react';
import { Callout, INSET, Pill, Spinner } from '../../components/ui';
import { CATEGORY_LABELS, SEVERITY_LABELS, SEVERITY_TONE, formatDuration } from '../../lib/labels';
import { languageFor, rowTitle, type FindingRow } from './model';

const DiffView = lazy(() => import('../../components/DiffView'));

interface FindingDetailProps {
  row: FindingRow | null;
  applied: boolean;
}

export function FindingDetail({ row, applied }: FindingDetailProps) {
  if (row === null) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-subtle">
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
        className="shrink-0 p-6"
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.14 }}
      >
        <DetailText row={row} applied={applied} />
      </motion.div>
      {row.suggestion ? (
        <DiffSection row={row} />
      ) : (
        <div className="flex flex-1 items-center justify-center border-t border-border p-8 text-center text-sm text-subtle">
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
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone={SEVERITY_TONE[finding.severity]}>
          <span className="uppercase">{SEVERITY_LABELS[finding.severity]}</span>
        </Pill>
        {suggestion && (
          <Pill>
            <span className="uppercase">{CATEGORY_LABELS[suggestion.category]}</span>
          </Pill>
        )}
      </div>
      <h2 className="mt-3 text-xl leading-snug font-bold text-strong">{rowTitle(row)}</h2>
      <p className="mt-2 flex flex-wrap items-center gap-x-2 font-mono text-xs text-subtle">
        <span className="break-all">
          {finding.file}:{finding.line_start}
        </span>
        <span>·</span>
        <span className="text-muted">{finding.rule_code}</span>
      </p>
      {suggestion && <VerificationLine row={row} applied={applied} />}
      {suggestion && (
        <div className="mt-5">
          <p className="mb-2 text-xs font-semibold tracking-wider text-subtle uppercase">Açıklama</p>
          <p className="max-h-32 overflow-auto text-sm leading-relaxed text-muted">{suggestion.explanation}</p>
        </div>
      )}
      <p className={`${INSET} mt-4 p-4 text-xs leading-relaxed text-subtle`}>
        <span className="font-mono text-muted">{finding.tool}:</span> {finding.message}
      </p>
    </>
  );
}

function VerificationLine({ row, applied }: { row: FindingRow; applied: boolean }) {
  const v = row.suggestion!.verification;
  const passed = v.status === 'passed';
  return (
    <Callout tone={passed ? 'ok' : 'warn'} className="mt-4 !py-3">
      <div className="flex items-center gap-3">
        <span aria-hidden>{passed ? '✓' : '⚠'}</span>
        <span className="font-semibold">{passed ? 'Doğrulandı' : 'Doğrulanamadı'}</span>
        <span className="ml-auto shrink-0 text-xs opacity-70">
          {applied ? 'uygulandı' : passed ? formatDuration(v.duration_ms) : 'uygulanamaz'}
        </span>
      </div>
      <p className="mt-1 opacity-80">{v.detail}</p>
    </Callout>
  );
}

function DiffSection({ row }: { row: FindingRow }) {
  const suggestion = row.suggestion!;
  const { patch } = suggestion;
  return (
    <section className="flex min-h-0 flex-1 flex-col border-t border-border">
      <div className="grid h-9 shrink-0 grid-cols-2 px-6 text-xs font-semibold tracking-wider text-subtle uppercase">
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
