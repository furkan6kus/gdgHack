import { AnimatePresence, motion } from 'framer-motion';
import { useState, type FormEvent } from 'react';
import type { ErrorPayload, HealthResponse } from '../api/types';
import { FolderPicker } from '../components/FolderPicker';
import { LogoMark } from '../components/Logo';
import { ApiKeyMissingHelp } from '../components/StateMessage';
import { Button, CARD, Callout, Pill, Switch } from '../components/ui';
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
  onStart: (path: string, verify: boolean) => void;
}

export function HomeScreen({ health, healthError, startError, starting, onStart }: HomeScreenProps) {
  const [recent, setRecent] = useState<string[]>(() => readJson(STORAGE_KEYS.recentPaths, []));
  const [path, setPath] = useState(() => recent[0] ?? '');
  const [verify, setVerify] = useState<boolean>(() => readJson(STORAGE_KEYS.verify, true));
  const [noticeSeen, setNoticeSeen] = useState<boolean>(() =>
    readJson(STORAGE_KEYS.verifyNoticeSeen, false),
  );
  const [pickerOpen, setPickerOpen] = useState(false);

  const keyMissing = health !== null && !health.api_key_configured;
  const canStart = path.trim() !== '' && !starting && !keyMissing && healthError === null;

  const changeVerify = (value: boolean) => {
    setVerify(value);
    writeJson(STORAGE_KEYS.verify, value);
  };

  const dismissNotice = () => {
    setNoticeSeen(true);
    writeJson(STORAGE_KEYS.verifyNoticeSeen, true);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!canStart) return;
    const trimmed = path.trim();
    const next = [trimmed, ...recent.filter((p) => p !== trimmed)].slice(0, MAX_RECENT_PATHS);
    setRecent(next);
    writeJson(STORAGE_KEYS.recentPaths, next);
    onStart(trimmed, verify);
  };

  return (
    <div className="flex h-full flex-col items-center overflow-auto px-4 pt-[10vh] pb-12 sm:px-6">
      <div className="w-full max-w-xl">
        <header className="mb-8 flex flex-wrap items-center gap-4">
          <LogoMark size={40} />
          <div className="min-w-0">
            <h1 className="text-2xl font-bold tracking-tight text-strong">{APP_NAME}</h1>
            <p className="mt-0.5 text-sm text-subtle">Kodunuzu analiz edin, doğrulanmış düzeltmeler alın.</p>
          </div>
          {health && (
            <Pill className="ml-auto">
              adapter: {health.adapter}
            </Pill>
          )}
        </header>

        <AnimatePresence>
          {!noticeSeen && <VerifyNotice verify={verify} onVerifyChange={changeVerify} onDismiss={dismissNotice} />}
        </AnimatePresence>

        {healthError && <Banner tone="err">{healthError.message}</Banner>}
        {keyMissing && (
          <Banner tone="warn" title="API anahtarı eksik">
            <ApiKeyMissingHelp />
          </Banner>
        )}

        <form onSubmit={submit} className={`${CARD} p-6 shadow-xl shadow-black/30`}>
          <label htmlFor="path" className="mb-3 block text-xs font-semibold tracking-wider text-subtle uppercase">
            Analiz edilecek klasör veya dosya
          </label>
          <div className="flex gap-2">
            <input
              id="path"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder={PATH_PLACEHOLDER}
              autoFocus
              spellCheck={false}
              className="h-10 min-w-0 flex-1 rounded-xl border border-border bg-bg px-3 font-mono text-sm text-strong outline-none transition-colors placeholder:text-subtle focus-visible:border-accent/60 focus-visible:ring-2 focus-visible:ring-accent/30"
            />
            <Button onClick={() => setPickerOpen(true)}>Gözat…</Button>
          </div>
          {startError && <Callout tone="err" className="mt-3 !p-3 text-xs">{startError.message}</Callout>}
          <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
            {noticeSeen ? (
              <Switch checked={!verify} onChange={(v) => changeVerify(!v)} label="Doğrulama yapma" />
            ) : (
              <span />
            )}
            <Button type="submit" variant="primary" disabled={!canStart}>
              {starting ? 'Başlatılıyor…' : 'Analiz et'}
            </Button>
          </div>
          {!verify && (
            <Callout tone="warn" className="mt-4 !p-3 text-xs">
              Doğrulama kapalı: öneriler ⚠ olarak işaretlenir ve uygulanamaz.
            </Callout>
          )}
        </form>

        {recent.length > 0 && (
          <section className="mt-10">
            <h2 className="mb-3 text-xs font-semibold tracking-wider text-subtle uppercase">Son kullanılanlar</h2>
            <ul className="space-y-1">
              {recent.map((p) => (
                <li key={p}>
                  <button
                    type="button"
                    onClick={() => setPath(p)}
                    className="w-full truncate rounded-xl border border-transparent px-3 py-2 text-left font-mono text-[13px] text-muted transition-colors hover:border-border hover:bg-panel hover:text-text focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:outline-none"
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
          setPath(picked);
          setPickerOpen(false);
        }}
      />
    </div>
  );
}

function VerifyNotice({
  verify,
  onVerifyChange,
  onDismiss,
}: {
  verify: boolean;
  onVerifyChange: (value: boolean) => void;
  onDismiss: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, height: 0, marginBottom: 0 }}
      className="mb-6 overflow-hidden rounded-2xl border border-info/15 bg-info/[0.06] p-6"
    >
      <p className="text-sm font-semibold text-strong">Doğrulama kodu SİZİN makinenizde çalıştırır.</p>
      <p className="mt-1.5 text-sm leading-relaxed text-muted">
        Her yama geçici bir kopyaya uygulanır ve projenizin testleri ya da sözdizimi kontrolü yerel
        olarak çalıştırılır. İsterseniz doğrulamayı kapatabilirsiniz.
      </p>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <Switch checked={!verify} onChange={(v) => onVerifyChange(!v)} label="Doğrulama yapma" />
        <Button size="sm" variant="primary" onClick={onDismiss}>
          Anladım
        </Button>
      </div>
    </motion.div>
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
        <p className={`mb-1 font-semibold ${tone === 'err' ? 'text-rose-300' : 'text-amber-300'}`}>{title}</p>
      )}
      <div className="text-muted">{children}</div>
    </Callout>
  );
}
