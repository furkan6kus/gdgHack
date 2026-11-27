import { motion } from 'framer-motion';
import { useEffect, useRef, useState } from 'react';
import { subscribeToAnalysis } from '../api/client';
import type { AnalyzeResult, ErrorPayload, ProgressEvent, Stage } from '../api/types';
import { Button, CARD, Spinner } from '../components/ui';
import { STAGE_LABELS, STAGE_ORDER } from '../lib/labels';

interface AnalyzingScreenProps {
  jobId: string;
  path: string;
  verify: boolean;
  onResult: (result: AnalyzeResult) => void;
  onError: (error: ErrorPayload) => void;
  onCancel: () => void;
}

interface LogLine {
  id: number;
  stage: Stage;
  text: string;
}

const MAX_LOG_LINES = 200;

export function AnalyzingScreen({ jobId, path, verify, onResult, onError, onCancel }: AnalyzingScreenProps) {
  const [latest, setLatest] = useState<ProgressEvent | null>(null);
  const [log, setLog] = useState<LogLine[]>([]);
  const [cancelling, setCancelling] = useState(false);
  const logEnd = useRef<HTMLDivElement>(null);
  const handlers = useRef({ onResult, onError });

  useEffect(() => {
    handlers.current = { onResult, onError };
  }, [onResult, onError]);

  useEffect(() => {
    let counter = 0;
    return subscribeToAnalysis(jobId, {
      onProgress: (event) => {
        setLatest(event);
        counter += 1;
        const line = { id: counter, stage: event.stage, text: event.message };
        setLog((prev) => [...prev, line].slice(-MAX_LOG_LINES));
      },
      onResult: (result) => handlers.current.onResult(result),
      onError: (error) => handlers.current.onError(error),
    });
  }, [jobId]);

  useEffect(() => {
    logEnd.current?.scrollIntoView({ block: 'end' });
  }, [log]);

  const activeIndex = latest ? STAGE_ORDER.indexOf(latest.stage as (typeof STAGE_ORDER)[number]) : 0;
  const hasCount = latest?.current != null && latest.total != null && latest.total > 0;
  const percent = hasCount ? Math.round(((latest.current ?? 0) / (latest.total ?? 1)) * 100) : null;

  return (
    <div className="flex h-full items-center justify-center overflow-auto bg-bg/60 p-4">
      <div className={`${CARD} w-full max-w-md p-5 shadow-xl shadow-strong/10`}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="truncate text-[17px] font-semibold text-strong" title={path}>
              {path.split(/[\\/]/).filter(Boolean).pop() ?? path} inceleniyor
            </h1>
            <p className="mt-0.5 truncate font-mono text-[12px] text-hint" title={path}>
              {path}
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            disabled={cancelling}
            onClick={() => {
              setCancelling(true);
              onCancel();
            }}
          >
            {cancelling ? 'İptal ediliyor…' : 'İptal'}
          </Button>
        </div>

        <ol className="mt-4 space-y-0.5">
          {STAGE_ORDER.map((stage, i) => (
            <StageRow key={stage} stage={stage} state={stageState(i, activeIndex, stage, verify)} />
          ))}
        </ol>

        <div className="mt-4">
          <div className="mb-2 flex justify-between gap-3 text-[13px]">
            <span className="min-w-0 truncate text-muted">{latest?.message ?? 'Başlatılıyor…'}</span>
            {hasCount && (
              <span className="shrink-0 font-medium tabular-nums text-strong">
                {latest.current}/{latest.total}
              </span>
            )}
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-sunken">
            {percent === null ? (
              <motion.div
                className="h-full w-1/3 rounded-full bg-accent"
                animate={{ x: ['-100%', '300%'] }}
                transition={{ repeat: Infinity, duration: 1.2, ease: 'easeInOut' }}
              />
            ) : (
              <motion.div
                className="h-full rounded-full bg-accent"
                animate={{ width: `${percent}%` }}
                transition={{ duration: 0.25, ease: 'easeOut' }}
              />
            )}
          </div>
        </div>

        <details className="mt-4 text-[13px]">
          <summary className="cursor-pointer text-subtle hover:text-strong">Ayrıntılar ({log.length})</summary>
          <div className="mt-2 max-h-40 overflow-auto rounded-[var(--radius-control)] bg-sunken p-3 leading-6">
            {log.map((line) => (
              <div key={line.id} className="flex gap-3">
                <span className="w-32 shrink-0 text-hint">{STAGE_LABELS[line.stage]}</span>
                <span className="min-w-0 break-words text-muted">{line.text}</span>
              </div>
            ))}
            <div ref={logEnd} />
          </div>
        </details>
      </div>
    </div>
  );
}

type StageState = 'pending' | 'active' | 'done' | 'skipped';

function stageState(index: number, activeIndex: number, stage: Stage, verify: boolean): StageState {
  if (stage === 'verify' && !verify) return 'skipped';
  if (index < activeIndex) return 'done';
  if (index === activeIndex) return stage === 'done' ? 'done' : 'active';
  return 'pending';
}

function StageRow({ stage, state }: { stage: Stage; state: StageState }) {
  const textCls = {
    pending: 'text-subtle',
    active: 'text-text',
    done: 'text-muted',
    skipped: 'text-subtle line-through',
  }[state];
  return (
    <li className={`flex items-center gap-3 rounded-[var(--radius-control)] px-3 py-2 text-sm ${state === 'active' ? 'bg-accent-soft' : ''}`}>
      <span className="flex size-5 items-center justify-center">
        {state === 'active' && <Spinner className="size-4 text-accent" />}
        {state === 'done' && (
          <motion.span
            initial={{ scale: 0.4, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="flex size-4 items-center justify-center rounded-full bg-ok-wash text-[10px] text-ok-ink"
          >
            ✓
          </motion.span>
        )}
        {state === 'pending' && <span className="size-1.5 rounded-full bg-border" />}
        {state === 'skipped' && <span className="text-xs text-subtle">–</span>}
      </span>
      <span className={textCls}>{STAGE_LABELS[stage]}</span>
      {state === 'skipped' && <span className="ml-auto text-[13px] text-subtle">kapalı</span>}
    </li>
  );
}
