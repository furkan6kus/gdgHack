import { useEffect, useState } from 'react';
import { api, toErrorPayload } from '../api/client';
import type { BrowseResponse, ErrorPayload } from '../api/types';
import { Modal } from './Modal';
import { Button, Spinner, Switch } from './ui';

interface FolderPickerProps {
  open: boolean;
  initialPath?: string;
  onClose: () => void;
  onPick: (path: string) => void;
}

interface Target {
  path: string | undefined;
  showHidden: boolean;
}

type Listing =
  | { key: string; kind: 'ok'; data: BrowseResponse }
  | { key: string; kind: 'error'; error: ErrorPayload };

const keyOf = (t: Target) => `${t.showHidden ? 1 : 0}:${t.path ?? ''}`;

export function FolderPicker({ open, initialPath, onClose, onPick }: FolderPickerProps) {
  const [target, setTarget] = useState<Target>({ path: initialPath, showHidden: false });
  const [loaded, setLoaded] = useState<Listing | null>(null);
  const key = keyOf(target);
  const listing = loaded?.key === key ? loaded : null; // null = loading

  useEffect(() => {
    if (!open) return;
    let alive = true;
    api
      .browse(target.path, target.showHidden)
      .then((data) => alive && setLoaded({ key, kind: 'ok', data }))
      .catch((err: unknown) => alive && setLoaded({ key, kind: 'error', error: toErrorPayload(err) }));
    return () => {
      alive = false;
    };
  }, [open, key, target]);

  const load = (path: string | undefined) => setTarget((t) => ({ ...t, path }));
  const current = listing?.kind === 'ok' ? listing.data.path : target.path;

  const footer = (
    <>
      <span className="mr-auto truncate font-mono text-xs text-muted" title={current}>
        {current}
      </span>
      <Button onClick={onClose}>Vazgeç</Button>
      <Button
        variant="primary"
        disabled={listing?.kind !== 'ok'}
        onClick={() => listing?.kind === 'ok' && onPick(listing.data.path)}
      >
        Bu klasörü seç
      </Button>
    </>
  );

  return (
    <Modal open={open} title="Klasör seç" onClose={onClose} footer={footer} width="max-w-xl">
      <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-2.5">
        <Button
          size="sm"
          variant="ghost"
          disabled={listing?.kind !== 'ok' || listing.data.parent === null}
          onClick={() => listing?.kind === 'ok' && load(listing.data.parent ?? undefined)}
        >
          ← Üst klasör
        </Button>
        <Switch
          checked={target.showHidden}
          onChange={(showHidden) => setTarget((t) => ({ ...t, showHidden }))}
          label="Gizlileri göster"
        />
      </div>
      <div className="h-80 overflow-auto px-2 py-2">
        {listing === null && (
          <div className="flex h-full items-center justify-center text-muted">
            <Spinner />
          </div>
        )}
        {listing?.kind === 'error' && (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-sm">
            <p className="text-err">{listing.error.message}</p>
            <Button size="sm" onClick={() => load(undefined)}>
              Ana klasöre dön
            </Button>
          </div>
        )}
        {listing?.kind === 'ok' && <EntryList data={listing.data} onOpen={load} />}
      </div>
    </Modal>
  );
}

function EntryList({ data, onOpen }: { data: BrowseResponse; onOpen: (path: string) => void }) {
  if (data.entries.length === 0) {
    return <p className="p-6 text-center text-sm text-muted">Bu klasör boş.</p>;
  }
  return (
    <ul>
      {data.entries.map((entry) => (
        <li key={entry.path}>
          <button
            type="button"
            disabled={!entry.is_dir}
            onClick={() => onOpen(entry.path)}
            className="flex w-full items-center gap-2.5 rounded-md px-3 py-1.5 text-left text-sm hover:bg-panel-2 disabled:cursor-default disabled:text-muted/60 disabled:hover:bg-transparent"
          >
            <span aria-hidden className={entry.is_dir ? 'text-accent' : 'text-muted/50'}>
              {entry.is_dir ? '▸' : '·'}
            </span>
            <span className="truncate font-mono text-[13px]">{entry.name}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
