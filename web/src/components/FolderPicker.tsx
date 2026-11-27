import { useEffect, useState } from 'react';
import { api, toErrorPayload } from '../api/client';
import type { BrowseEntry, BrowseResponse, ErrorPayload, Place } from '../api/types';
import { Modal } from './Modal';
import { Button, Callout, Spinner, Switch } from './ui';

interface FolderPickerProps {
  open: boolean;
  initialPath?: string;
  onClose: () => void;
  /** Called with one folder, or with the files that were ticked (from any folder). */
  onPick: (paths: string[]) => void;
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
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [query, setQuery] = useState('');
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

  const toggleFile = (path: string) =>
    setSelectedFiles((prev) => (prev.includes(path) ? prev.filter((p) => p !== path) : [...prev, path]));
  const navigate = (path: string | undefined) => {
    setQuery('');
    setTarget((t) => ({ ...t, path }));
  };
  const current = listing?.kind === 'ok' ? listing.data.path : target.path;
  const folder = listing?.kind === 'ok' ? listing.data.path : null;
  const pickedFiles = selectedFiles.length > 0;
  const summary = pickedFiles ? selectedFiles.join(', ') : (folder ?? '');

  const footer = (
    <>
      <span className="mr-auto min-w-0 truncate font-mono text-xs text-muted" title={summary}>
        {pickedFiles ? `${selectedFiles.length} dosya seçili` : folder}
      </span>
      {pickedFiles && (
        <Button size="sm" variant="ghost" onClick={() => setSelectedFiles([])}>
          Seçimi temizle
        </Button>
      )}
      <Button onClick={onClose}>Vazgeç</Button>
      <Button
        variant="primary"
        disabled={!pickedFiles && folder === null}
        onClick={() => {
          if (pickedFiles) onPick(selectedFiles);
          else if (folder) onPick([folder]);
          setSelectedFiles([]);
        }}
      >
        {pickedFiles ? `${selectedFiles.length} dosyayı ekle` : 'Bu klasörü ekle'}
      </Button>
    </>
  );

  return (
    <Modal open={open} title="Dosya ya da klasör seç (birden çok dosya işaretleyebilirsiniz)" onClose={onClose} footer={footer} width="max-w-3xl">
      <div className="grid h-[26rem] grid-cols-[120px_minmax(0,1fr)] divide-x divide-border sm:grid-cols-[180px_minmax(0,1fr)]">
        <PlacesList places={places} current={current} onOpen={navigate} />
        <div className="flex min-h-0 flex-col">
          <div className="flex shrink-0 items-center gap-2 border-b border-border px-3 py-2.5">
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
          <div className="shrink-0 border-b border-border px-3 py-2.5">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Bu klasörde ara…"
              aria-label="Bu klasörde ara"
              autoFocus
              spellCheck={false}
              className="h-9 w-full rounded-[var(--radius-control)] border border-border bg-bg px-3 text-sm text-strong outline-none placeholder:text-subtle focus-visible:border-accent/60 focus-visible:ring-2 focus-visible:ring-accent/30"
            />
          </div>
          <div className="min-h-0 flex-1 overflow-auto p-1.5">
            {listing === null && (
              <div className="flex h-full items-center justify-center text-muted">
                <Spinner />
              </div>
            )}
            {listing?.kind === 'error' && (
              <div className="flex h-full flex-col items-center justify-center gap-3 p-3 text-sm">
                <Callout tone="err">{listing.error.message}</Callout>
                <Button size="sm" onClick={() => navigate(undefined)}>
                  Ev klasörüne dön
                </Button>
              </div>
            )}
            {listing?.kind === 'ok' && (
              <EntryList
                entries={filterEntries(listing.data.entries, query)}
                filtered={query.trim() !== ''}
                selectedFiles={selectedFiles}
                onOpenDir={navigate}
                onToggleFile={toggleFile}
                onPickFile={(path) => {
                  onPick(unique([...selectedFiles, path]));
                  setSelectedFiles([]);
                }}
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
    <nav className="overflow-auto bg-sunken p-2" aria-label="Hızlı erişim">
      {places.map((place, i) => (
        <div key={place.path}>
          {place.kind === 'drive' && places[i - 1]?.kind !== 'drive' && (
            <p className="mt-3 mb-1 px-2.5 text-[13px] font-semibold text-muted">
              Sürücüler
            </p>
          )}
          <button
            type="button"
            onClick={() => onOpen(place.path)}
            title={place.path}
            className={`flex w-full items-center gap-2.5 rounded-[var(--radius-control)] px-2.5 py-2 text-left text-[13px] transition-colors focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:outline-none ${current === place.path ? 'bg-accent-soft text-strong ring-1 ring-accent/40' : 'text-muted hover:bg-hover hover:text-text'}`}
          >
            <span aria-hidden className="w-4 text-center text-accent">
              {PLACE_ICONS[place.kind]}
            </span>
            <span className="truncate">{place.name}</span>
          </button>
        </div>
      ))}
    </nav>
  );
}

function filterEntries(entries: BrowseEntry[], query: string): BrowseEntry[] {
  const needle = query.trim().toLocaleLowerCase('tr-TR');
  if (!needle) return entries;
  return entries.filter((e) => e.name.toLocaleLowerCase('tr-TR').includes(needle));
}

function EntryList({
  entries,
  filtered,
  selectedFiles,
  onOpenDir,
  onToggleFile,
  onPickFile,
}: {
  entries: BrowseEntry[];
  filtered: boolean;
  selectedFiles: string[];
  onOpenDir: (path: string) => void;
  onToggleFile: (path: string) => void;
  onPickFile: (path: string) => void;
}) {
  if (entries.length === 0) {
    return (
      <p className="p-6 text-center text-sm text-subtle">
        {filtered ? 'Eşleşen dosya ya da klasör yok.' : 'Bu klasör boş.'}
      </p>
    );
  }
  return (
    <ul>
      {entries.map((entry) => {
        const selected = selectedFiles.includes(entry.path);
        return (
          <li key={entry.path}>
            <button
              type="button"
              aria-pressed={entry.is_dir ? undefined : selected}
              onClick={() => (entry.is_dir ? onOpenDir(entry.path) : onToggleFile(entry.path))}
              onDoubleClick={() => !entry.is_dir && onPickFile(entry.path)}
              className={`flex w-full items-center gap-2.5 rounded-[var(--radius-control)] px-3 py-2 text-left text-sm transition-colors focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:outline-none ${selected ? 'bg-accent-soft text-strong ring-1 ring-accent/40' : 'hover:bg-hover'}`}
            >
              <span aria-hidden className={`w-3 ${entry.is_dir ? 'text-accent' : selected ? 'text-accent' : 'text-subtle'}`}>
                {entry.is_dir ? '▸' : selected ? '✓' : '·'}
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

function unique(items: string[]): string[] {
  return [...new Set(items)];
}
