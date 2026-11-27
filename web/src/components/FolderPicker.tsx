import { useEffect, useState } from 'react';
import { api, toErrorPayload } from '../api/client';
import type { BrowseEntry, BrowseResponse, ErrorPayload, Place } from '../api/types';
import { Modal } from './Modal';
import { Button, Spinner, Switch } from './ui';

interface FolderPickerProps {
  open: boolean;
  initialPath?: string;
  onClose: () => void;
  /** Called with a folder or a single file path. */
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

const PLACE_ICONS: Record<Place['kind'], string> = { home: '⌂', folder: '▣', drive: '⛁' };

export function FolderPicker({ open, initialPath, onClose, onPick }: FolderPickerProps) {
  const [target, setTarget] = useState<Target>({ path: initialPath, showHidden: false });
  const [loaded, setLoaded] = useState<Listing | null>(null);
  const [places, setPlaces] = useState<Place[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
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

  useEffect(() => {
    if (!open) return;
    let alive = true;
    api
      .places()
      .then((p) => alive && setPlaces(p))
      .catch(() => undefined); // the listing still works without quick access
    return () => {
      alive = false;
    };
  }, [open]);

  const navigate = (path: string | undefined) => {
    setSelectedFile(null);
    setTarget((t) => ({ ...t, path }));
  };
  const current = listing?.kind === 'ok' ? listing.data.path : target.path;
  const choice = selectedFile ?? (listing?.kind === 'ok' ? listing.data.path : null);

  const footer = (
    <>
      <span className="mr-auto min-w-0 truncate font-mono text-xs text-muted" title={choice ?? ''}>
        {choice}
      </span>
      <Button onClick={onClose}>Vazgeç</Button>
      <Button variant="primary" disabled={choice === null} onClick={() => choice && onPick(choice)}>
        {selectedFile ? 'Bu dosyayı seç' : 'Bu klasörü seç'}
      </Button>
    </>
  );

  return (
    <Modal open={open} title="Klasör veya dosya seç" onClose={onClose} footer={footer} width="max-w-3xl">
      <div className="grid h-[26rem] grid-cols-[180px_minmax(0,1fr)] divide-x divide-border">
        <PlacesList places={places} current={current} onOpen={navigate} />
        <div className="flex min-h-0 flex-col">
          <div className="flex shrink-0 items-center gap-2 border-b border-border px-3 py-2">
            <Button
              size="sm"
              variant="ghost"
              aria-label="Üst klasör"
              disabled={listing?.kind !== 'ok' || listing.data.parent === null}
              onClick={() => listing?.kind === 'ok' && navigate(listing.data.parent ?? undefined)}
            >
              ←
            </Button>
            <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted" title={current}>
              {current}
            </span>
            <Switch
              checked={target.showHidden}
              onChange={(showHidden) => setTarget((t) => ({ ...t, showHidden }))}
              label="Gizliler"
            />
          </div>
          <div className="min-h-0 flex-1 overflow-auto p-1.5">
            {listing === null && (
              <div className="flex h-full items-center justify-center text-muted">
                <Spinner />
              </div>
            )}
            {listing?.kind === 'error' && (
              <div className="flex h-full flex-col items-center justify-center gap-3 text-sm">
                <p className="text-err">{listing.error.message}</p>
                <Button size="sm" onClick={() => navigate(undefined)}>
                  Ev klasörüne dön
                </Button>
              </div>
            )}
            {listing?.kind === 'ok' && (
              <EntryList
                entries={listing.data.entries}
                selectedFile={selectedFile}
                onOpenDir={navigate}
                onSelectFile={setSelectedFile}
                onPickFile={onPick}
              />
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
}

function PlacesList({
  places,
  current,
  onOpen,
}: {
  places: Place[];
  current: string | undefined;
  onOpen: (path: string) => void;
}) {
  return (
    <nav className="overflow-auto bg-panel-2/30 p-2" aria-label="Hızlı erişim">
      {places.map((place, i) => (
        <div key={place.path}>
          {place.kind === 'drive' && places[i - 1]?.kind !== 'drive' && (
            <p className="mt-3 mb-1 px-2.5 text-[10px] font-semibold tracking-wide text-muted/70 uppercase">
              Sürücüler
            </p>
          )}
          <button
            type="button"
            onClick={() => onOpen(place.path)}
            title={place.path}
            className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left text-[13px] transition-colors ${current === place.path ? 'bg-accent-soft text-text' : 'text-muted hover:bg-panel-2 hover:text-text'}`}
          >
            <span aria-hidden className="w-4 text-center text-accent/80">
              {PLACE_ICONS[place.kind]}
            </span>
            <span className="truncate">{place.name}</span>
          </button>
        </div>
      ))}
    </nav>
  );
}

function EntryList({
  entries,
  selectedFile,
  onOpenDir,
  onSelectFile,
  onPickFile,
}: {
  entries: BrowseEntry[];
  selectedFile: string | null;
  onOpenDir: (path: string) => void;
  onSelectFile: (path: string) => void;
  onPickFile: (path: string) => void;
}) {
  if (entries.length === 0) {
    return <p className="p-6 text-center text-sm text-muted">Bu klasör boş.</p>;
  }
  return (
    <ul>
      {entries.map((entry) => {
        const selected = entry.path === selectedFile;
        return (
          <li key={entry.path}>
            <button
              type="button"
              onClick={() => (entry.is_dir ? onOpenDir(entry.path) : onSelectFile(entry.path))}
              onDoubleClick={() => !entry.is_dir && onPickFile(entry.path)}
              className={`flex w-full items-center gap-2.5 rounded-md px-3 py-1.5 text-left text-sm transition-colors ${selected ? 'bg-accent-soft text-text' : 'hover:bg-panel-2'}`}
            >
              <span aria-hidden className={`w-3 ${entry.is_dir ? 'text-accent' : 'text-muted/60'}`}>
                {entry.is_dir ? '▸' : '·'}
              </span>
              <span className={`truncate font-mono text-[13px] ${entry.is_dir ? '' : 'text-text/80'}`}>
                {entry.name}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
