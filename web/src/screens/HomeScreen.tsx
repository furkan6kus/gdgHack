import { useState, type FormEvent, type ReactNode } from 'react';
import { api, toErrorPayload } from '../api/client';
import type { ErrorPayload, HealthResponse } from '../api/types';
import { FolderPicker } from '../components/FolderPicker';
import { LogoMark } from '../components/Logo';
import { ApiKeyMissingHelp } from '../components/StateMessage';
import { Button, CARD, Callout, Pill, Spinner } from '../components/ui';
import { APP_NAME, MAX_RECENT_PATHS, STORAGE_KEYS } from '../config';
import { readJson, writeJson } from '../lib/storage';

const PATH_PLACEHOLDER = navigator.userAgent.includes('Windows')
  ? 'C:\\Users\\kullanici\\projem'
  : '/home/kullanici/projem';

interface HomeScreenProps {
  health: HealthResponse | null;
  healthError: ErrorPayload | null;
  startError: ErrorPayload | null;
  starting: boolean;
  /** Every path becomes its own analysis tab. */
  onStart: (paths: string[], verify: boolean) => void;
  openTabs: number;
  onBackToTabs: () => void;
  onOpenHistory: () => void;
  /** Model + effort picker with the session's API spend. */
  picker?: ReactNode;
}

export function HomeScreen({
  health,
  healthError,
  startError,
  starting,
  onStart,
  openTabs,
  onBackToTabs,
  onOpenHistory,
  picker,
}: HomeScreenProps) {
  const [recent, setRecent] = useState<string[]>(() => readJson(STORAGE_KEYS.recentPaths, []));
  const [path, setPath] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [picking, setPicking] = useState(false);
  const [repoUrl, setRepoUrl] = useState('');
  const [cloning, setCloning] = useState(false);
  const [sourceError, setSourceError] = useState<string | null>(null);

  /** Opens Windows Explorer / Finder; falls back to the in-app browser when it cannot. */
  const browseNative = async (kind: 'files' | 'folder') => {
    setPicking(true);
    setSourceError(null);
    try {
      const { paths } = await api.pick(kind, selected.at(-1));
      addPaths(paths);
    } catch (err) {
      const error = toErrorPayload(err);
      if (error.code === 'dialog_unavailable') setPickerOpen(true);
      else setSourceError(error.message);
    } finally {
      setPicking(false);
    }
  };

  const addRepo = async () => {
    setCloning(true);
    setSourceError(null);
    try {
      const { paths } = await api.cloneRepo(repoUrl.trim());
      addPaths(paths);
      setRepoUrl('');
    } catch (err) {
      setSourceError(toErrorPayload(err).message);
    } finally {
      setCloning(false);
    }
  };

  const keyMissing = health !== null && !health.api_key_configured;
  const targets = unique([...selected, path.trim()].filter(Boolean));
  const canStart = targets.length > 0 && !starting && !keyMissing && healthError === null;

  const addPaths = (paths: string[]) => setSelected((prev) => unique([...prev, ...paths]));
  const removePath = (p: string) => setSelected((prev) => prev.filter((x) => x !== p));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!canStart) return;
    const next = unique([...targets, ...recent]).slice(0, MAX_RECENT_PATHS);
    setRecent(next);
    writeJson(STORAGE_KEYS.recentPaths, next);
    onStart(targets, true); // suggestions are always verified before they can be applied
  };

  return (
    <div className="flex h-full flex-col items-center overflow-auto px-4 pt-[10vh] pb-12 sm:px-6">
      <div className="w-full max-w-xl">
        <header className="mb-8 flex flex-wrap items-start gap-4">
          <LogoMark size={44} />
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-semibold text-strong">{APP_NAME}</h1>
            <p className="mt-1 max-w-[52ch] text-[15px] text-muted">
              Dosyanı seç. Sorunları Türkçe anlatır, denenmiş düzeltmeleri tek tıkla uygular, her
              değişikliği geri alınabilir şekilde saklar.
            </p>
          </div>
          {health?.adapter === 'mock' && <Pill tone="warn">Demo verisi</Pill>}
        </header>

        <nav className="mb-6 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm" aria-label="Kısayollar">
          {openTabs > 0 && (
            <Button size="sm" variant="primary" onClick={onBackToTabs}>
              Açık analizlere dön ({openTabs})
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={onOpenHistory}>
            Değişiklik geçmişi
          </Button>
          <TelegramStatus configured={health?.telegram_configured ?? false} />
          <span className="ml-auto">{picker}</span>
        </nav>

        {healthError && <Banner tone="err">{healthError.message}</Banner>}
        {keyMissing && (
          <Banner tone="warn" title="API anahtarı eksik">
            <ApiKeyMissingHelp />
          </Banner>
        )}

        <form onSubmit={submit} className={`${CARD} p-6`}>
          <label htmlFor="path" className="mb-3 block text-sm font-semibold text-strong">
            Neyi analiz edelim?
          </label>
          {selected.length > 0 && (
            <ul className="mb-3 space-y-1.5" aria-label="Seçilenler">
              {selected.map((p) => (
                <li
                  key={p}
                  className="flex items-center gap-2 rounded-[var(--radius-control)] border border-border bg-bg py-1.5 pr-1.5 pl-3"
                >
                  <span className="min-w-0 flex-1 truncate font-mono text-[13px] text-text" title={p}>
                    {p}
                  </span>
                  <Button size="sm" variant="ghost" aria-label={`${p} öğesini çıkar`} onClick={() => removePath(p)}>
                    ×
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex gap-2">
            <input
              id="path"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder={PATH_PLACEHOLDER}
              autoFocus
              spellCheck={false}
              className="h-10 min-w-0 flex-1 rounded-[var(--radius-control)] border border-border bg-bg px-3 font-mono text-sm text-strong outline-none transition-colors placeholder:text-subtle focus-visible:border-accent/60 focus-visible:ring-2 focus-visible:ring-accent/30"
            />
            <Button
              disabled={path.trim() === ''}
              onClick={() => {
                addPaths([path.trim()]);
                setPath('');
              }}
            >
              Ekle
            </Button>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button variant="primary" size="sm" disabled={picking} onClick={() => void browseNative('files')}>
              {picking && <Spinner className="size-3" />}
              Dosya seç…
            </Button>
            <Button size="sm" disabled={picking} onClick={() => void browseNative('folder')}>
              Klasör seç…
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setPickerOpen(true)}>
              Uygulama içi gezgin
            </Button>
          </div>
          <p className="mt-2 text-xs text-subtle">
            Birden çok dosya ya da klasör ekleyebilirsiniz; her biri kendi sekmesinde açılır.
          </p>

          <div className="mt-5 border-t border-border pt-4">
            <label htmlFor="repo" className="mb-2 block text-sm font-semibold text-strong">
              GitHub reposu ekle
            </label>
            <div className="flex gap-2">
              <input
                id="repo"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    if (repoUrl.trim()) void addRepo();
                  }
                }}
                placeholder="https://github.com/kullanici/proje"
                spellCheck={false}
                className="h-10 min-w-0 flex-1 rounded-[var(--radius-control)] border border-border bg-bg px-3 font-mono text-sm text-strong outline-none placeholder:text-hint focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/25"
              />
              <Button disabled={cloning || repoUrl.trim() === ''} onClick={() => void addRepo()}>
                {cloning && <Spinner className="size-3" />}
                {cloning ? 'İndiriliyor…' : 'Repoyu ekle'}
              </Button>
            </div>
            <p className="mt-2 text-xs text-subtle">
              Herkese açık repo bilgisayarınıza indirilir ve proje olarak eklenir. Doğrulama projenin
              testlerini çalıştırır; yalnız güvendiğiniz repoları ekleyin.
            </p>
          </div>
          {sourceError && <Callout tone="err" className="mt-3 !p-3 text-xs">{sourceError}</Callout>}
          {startError && <Callout tone="err" className="mt-3 !p-3 text-xs">{startError.message}</Callout>}
          <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
            <p className="min-w-0 flex-1 text-xs text-subtle">
              Öneriler, uygulanmadan önce bilgisayarınızda geçici bir kopyada denenir.
            </p>
            <Button type="submit" variant="primary" disabled={!canStart}>
              {starting ? 'Başlatılıyor…' : targets.length > 1 ? `${targets.length} öğeyi analiz et` : 'Analiz et'}
            </Button>
          </div>
        </form>

        {recent.length > 0 && (
          <section className="mt-10">
            <h2 className="mb-2 text-sm font-semibold text-strong">Son kullanılanlar</h2>
            <ul className="space-y-1.5">
              {recent.map((p) => (
                <li key={p}>
                  <button
                    type="button"
                    onClick={() => addPaths([p])}
                    title="Seçilenlere ekle"
                    className="w-full truncate rounded-[var(--radius-control)] border border-border bg-panel px-3 py-2 text-left font-mono text-[13px] text-strong transition-colors hover:border-accent/40 hover:bg-accent-soft hover:text-accent focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:outline-none"
                  >
                    {p}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      <FolderPicker
        open={pickerOpen}
        initialPath={path || undefined}
        onClose={() => setPickerOpen(false)}
        onPick={(picked) => {
          addPaths(picked);
          setPickerOpen(false);
        }}
      />
    </div>
  );
}

/** Shows whether Telegram notifications are on, and sends a test message when they are. */
function TelegramStatus({ configured }: { configured: boolean }) {
  const [state, setState] = useState<'idle' | 'sending' | 'sent' | string>('idle');
  if (!configured) {
    return (
      <span
        className="text-xs text-subtle"
        title="Bildirim için sunucuyu TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID ile başlatın."
      >
        Telegram bildirimi kapalı
      </span>
    );
  }
  const test = async () => {
    setState('sending');
    try {
      const { sent } = await api.notifyTest();
      setState(sent ? 'sent' : 'Mesaj gönderilemedi; sunucu günlüğüne bakın.');
    } catch (err) {
      setState(toErrorPayload(err).message);
    }
  };
  return (
    <span className="flex items-center gap-2 text-[13px] text-ok-ink">
      Telegram bildirimi açık
      <Button size="sm" variant="ghost" disabled={state === 'sending'} onClick={() => void test()}>
        {state === 'sent' ? 'Gönderildi ✓' : 'Test gönder'}
      </Button>
      {state !== 'idle' && state !== 'sending' && state !== 'sent' && (
        <span className="text-err-ink">{state}</span>
      )}
    </span>
  );
}

function Banner({
  tone,
  title,
  children,
}: {
  tone: 'warn' | 'err';
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <Callout tone={tone} className="mb-6">
      {title && (
        <p className={`mb-1 font-semibold ${tone === 'err' ? 'text-err-ink' : 'text-warn-ink'}`}>{title}</p>
      )}
      <div className="text-muted">{children}</div>
    </Callout>
  );
}

function unique(items: string[]): string[] {
  return [...new Set(items)];
}
