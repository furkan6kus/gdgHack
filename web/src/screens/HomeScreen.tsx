import { AnimatePresence, motion } from 'framer-motion';
import { useState, type FormEvent } from 'react';
import type { ErrorPayload, HealthResponse } from '../api/types';
import { FolderPicker } from '../components/FolderPicker';
import { LogoMark } from '../components/Logo';
import { ApiKeyMissingHelp } from '../components/StateMessage';
import { Button, Switch } from '../components/ui';
import { APP_NAME, MAX_RECENT_PATHS, STORAGE_KEYS } from '../config';
import { readJson, writeJson } from '../lib/storage';

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
    <div className="flex h-full flex-col items-center overflow-auto px-6 pt-[14vh] pb-12">
      <div className="w-full max-w-xl">
        <header className="mb-8 flex items-center gap-3">
          <LogoMark size={36} />
          <div>
            <h1 className="font-mono text-lg font-semibold tracking-tight">{APP_NAME}</h1>
            <p className="text-xs text-muted">Kodunuzu analiz edin, doğrulanmış düzeltmeler alın.</p>
          </div>
          {health && (
            <span className="ml-auto rounded border border-border px-2 py-0.5 font-mono text-[10px] text-muted">
              adapter: {health.adapter}
            </span>
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

        <form onSubmit={submit} className="rounded-xl border border-border bg-panel p-4 shadow-xl shadow-black/30">
          <label htmlFor="path" className="mb-2 block text-xs font-medium text-muted">
            Analiz edilecek proje klasörü
          </label>
          <div className="flex gap-2">
            <input
              id="path"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/home/kullanici/projem"
              autoFocus
              spellCheck={false}
              className="h-9 min-w-0 flex-1 rounded-md border border-border bg-bg px-3 font-mono text-sm outline-none transition-colors placeholder:text-muted/50 focus:border-accent"
            />
            <Button onClick={() => setPickerOpen(true)}>Gözat…</Button>
          </div>
          {startError && <p className="mt-2 text-xs text-err">{startError.message}</p>}
          <div className="mt-4 flex items-center justify-between">
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
            <p className="mt-3 text-xs text-warn">
              Doğrulama kapalı: öneriler ⚠ olarak işaretlenir ve uygulanamaz.
            </p>
          )}
        </form>

        {recent.length > 0 && (
          <section className="mt-8">
            <h2 className="mb-2 text-xs font-medium text-muted">Son kullanılanlar</h2>
            <ul className="space-y-0.5">
              {recent.map((p) => (
                <li key={p}>
                  <button
                    type="button"
                    onClick={() => setPath(p)}
                    className="w-full truncate rounded-md px-2.5 py-1.5 text-left font-mono text-[13px] text-muted transition-colors hover:bg-panel hover:text-text"
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
      className="mb-4 overflow-hidden rounded-xl border border-accent/30 bg-accent-soft p-4"
    >
      <p className="text-sm font-medium">Doğrulama kodu SİZİN makinenizde çalıştırır.</p>
      <p className="mt-1 text-xs leading-relaxed text-muted">
        Her yama geçici bir kopyaya uygulanır ve projenizin testleri ya da sözdizimi kontrolü yerel
        olarak çalıştırılır. İsterseniz doğrulamayı kapatabilirsiniz.
      </p>
      <div className="mt-3 flex items-center justify-between">
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
  const cls = tone === 'err' ? 'border-err/30 bg-err/8' : 'border-warn/30 bg-warn/8';
  return (
    <div className={`mb-4 rounded-xl border p-4 text-sm ${cls}`}>
      {title && <p className={`mb-1 font-medium ${tone === 'err' ? 'text-err' : 'text-warn'}`}>{title}</p>}
      <div className="text-muted">{children}</div>
    </div>
  );
}
