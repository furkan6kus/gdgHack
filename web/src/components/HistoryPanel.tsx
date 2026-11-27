import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import { api, toErrorPayload } from '../api/client';
import type { ErrorPayload, HistoryEntry } from '../api/types';
import { languageFor } from '../screens/results/model';
import { Modal } from './Modal';
import { Button, Callout, INSET, Spinner } from './ui';

const DiffView = lazy(() => import('./DiffView'));

interface HistoryPanelProps {
  open: boolean;
  onClose: () => void;
  /** Called after an undo, so open tabs for that path can be re-analyzed. */
  onUndone: (entry: HistoryEntry) => void;
}

/** Every change applied from the UI: what changed, why, the diff, and undo. */
export function HistoryPanel({ open, onClose, onUndone }: HistoryPanelProps) {
  const [entries, setEntries] = useState<HistoryEntry[] | null>(null);
  const [error, setError] = useState<ErrorPayload | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .history()
      .then((list) => {
        setEntries(list);
        setError(null);
      })
      .catch((err: unknown) => setError(toErrorPayload(err)));
  }, []);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  const undo = async (entry: HistoryEntry) => {
    setBusy(entry.id);
    setError(null);
    try {
      const updated = await api.undo(entry.id);
      setEntries((list) => list?.map((e) => (e.id === updated.id ? updated : e)) ?? null);
      onUndone(updated);
    } catch (err) {
      setError(toErrorPayload(err));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Modal open={open} title="Değişiklik geçmişi" onClose={onClose} width="max-w-5xl">
      <div className="space-y-3 p-6 text-sm">
        <p className="text-muted">
          Arayüzden uygulanan her düzeltme burada saklanır: neyi neden değiştirdiği, önceki ve
          sonraki kod. İstediğinizi geri alabilirsiniz.
        </p>
        {error && <Callout tone="err" className="!p-3 text-xs">{error.message}</Callout>}
        {entries === null && !error && (
          <div className="flex justify-center p-8 text-muted">
            <Spinner />
          </div>
        )}
        {entries?.length === 0 && (
          <p className={`${INSET} p-6 text-center text-subtle`}>Henüz uygulanan bir değişiklik yok.</p>
        )}
        {entries?.map((entry) => (
          <article key={entry.id} className={`${INSET} overflow-hidden`}>
            <header className="flex flex-wrap items-center gap-3 px-4 py-3">
              <time className="font-mono text-xs text-subtle" dateTime={entry.time}>
                {formatTime(entry.time)}
              </time>
              <span className="min-w-0 flex-1 truncate font-mono text-[13px] text-text" title={entry.root}>
                {entry.files.map((f) => f.name).join(', ')}
              </span>
              {entry.undone && <span className="text-xs text-warn-ink">geri alındı</span>}
              <Button size="sm" onClick={() => setExpanded((id) => (id === entry.id ? null : entry.id))}>
                {expanded === entry.id ? 'Farkı gizle' : 'Farkı göster'}
              </Button>
              <Button
                size="sm"
                disabled={entry.undone || busy !== null}
                onClick={() => void undo(entry)}
              >
                {busy === entry.id && <Spinner className="size-3" />}
                Geri al
              </Button>
            </header>
            {entry.explanations.length > 0 && (
              <ul className="space-y-1 border-t border-border px-4 py-3 text-[13px] leading-relaxed text-muted">
                {entry.explanations.map((text, i) => (
                  <li key={i}>• {text}</li>
                ))}
              </ul>
            )}
            {expanded === entry.id &&
              entry.files.map((file) => (
                <div key={file.path} className="border-t border-border">
                  <p className="px-4 py-2 font-mono text-xs text-subtle" title={file.path}>
                    {file.path}
                  </p>
                  <div className="h-72">
                    <Suspense
                      fallback={
                        <div className="flex h-full items-center justify-center text-muted">
                          <Spinner className="size-5" />
                        </div>
                      }
                    >
                      <DiffView
                        modelKey={`history:${entry.id}:${file.path}`}
                        original={file.before}
                        modified={file.after}
                        language={languageFor(file.name)}
                      />
                    </Suspense>
                  </div>
                </div>
              ))}
          </article>
        ))}
      </div>
    </Modal>
  );
}

function formatTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'medium' });
}
