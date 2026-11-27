import { motion } from 'framer-motion';
import { useEffect, useRef, useState } from 'react';
import { subscribeToAnalysis } from '../api/client';
import type { AnalyzeResult, ErrorPayload, ProgressEvent, Stage } from '../api/types';
import { Button, Spinner } from '../components/ui';
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
    <div className="flex h-full items-center justify-center overflow-auto px-6 py-10">
      <div className="w-full max-w-2xl">
        <div className="mb-6 flex items-end justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs text-muted">Analiz ediliyor</p>
            <p className="truncate font-mono text-sm" title={path}>
              {path}
            </p>
          </div>
          <Button
            variant="danger"
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

        <ol className="space-y-1 rounded-xl border border-border bg-panel p-3">
          {STAGE_ORDER.map((stage, i) => (
            <StageRow
              key={stage}
              stage={stage}
              state={stageState(i, activeIndex, stage, verify)}
            />
          ))}
        </ol>

        <div className="mt-4">
          <div className="mb-1.5 flex justify-between font-mono text-[11px] text-muted">
            <span>{latest?.message ?? 'Başlatılıyor…'}</span>
            {hasCount && (
              <span>
                {latest.current}/{latest.total}
              </span>
            )}
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-panel-2">
            {percent === null ? (
              <motion.div
                className="h-full w-1/3 rounded-full bg-accent/70"
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

        <div className="mt-5 h-44 overflow-auto rounded-xl border border-border bg-bg/60 p-3 font-mono text-[12px] leading-5">
          {log.map((line) => (
            <motion.div
              key={line.id}
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.15 }}
              className="flex gap-3"
            >
              <span className="w-28 shrink-0 text-muted/60">{line.stage}</span>
              <span className="text-muted">{line.text}</span>
            </motion.div>
          ))}
          <div ref={logEnd} />
        </div>
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
    pending: 'text-muted/60',
    active: 'text-text',
    done: 'text-muted',
    skipped: 'text-muted/50 line-through',
  }[state];
  return (
    <li className={`flex items-center gap-3 rounded-md px-2 py-1.5 text-sm ${state === 'active' ? 'bg-panel-2' : ''}`}>
      <span className="flex size-5 items-center justify-center">
        {state === 'active' && <Spinner className="size-4 text-accent" />}
        {state === 'done' && (
          <motion.span
            initial={{ scale: 0.4, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="flex size-4 items-center justify-center rounded-full bg-ok/20 text-[10px] text-ok"
          >
            ✓
          </motion.span>
        )}
        {state === 'pending' && <span className="size-1.5 rounded-full bg-border" />}
        {state === 'skipped' && <span className="text-xs text-muted/50">–</span>}
      </span>
      <span className={textCls}>{STAGE_LABELS[stage]}</span>
      {state === 'skipped' && <span className="ml-auto text-xs text-muted/60">kapalı</span>}
    </li>
  );
}
