import { motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { CARD } from './ui';

type Tone = 'neutral' | 'ok' | 'warn' | 'err';

const TONE_RING: Record<Tone, string> = {
  neutral: 'bg-white/[0.04] text-muted ring-border',
  ok: 'bg-ok/10 text-emerald-300 ring-ok/25',
  warn: 'bg-warn/10 text-amber-300 ring-warn/30',
  err: 'bg-err/10 text-rose-300 ring-err/30',
};

interface StateMessageProps {
  icon: string;
  title: string;
  tone?: Tone;
  children?: ReactNode;
  actions?: ReactNode;
}

/** Centered empty / error / info state. Never renders stack traces: callers pass user text. */
export function StateMessage({ icon, title, tone = 'neutral', children, actions }: StateMessageProps) {
  return (
    <motion.div
      className={`${CARD} mx-4 flex max-w-md flex-col items-center gap-3 p-8 text-center`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className={`flex size-12 items-center justify-center rounded-full text-xl ring-1 ring-inset ${TONE_RING[tone]}`}>
        {icon}
      </div>
      <h2 className="text-lg font-bold text-strong">{title}</h2>
      {children && <div className="text-sm leading-relaxed text-muted">{children}</div>}
      {actions && <div className="mt-2 flex gap-2">{actions}</div>}
    </motion.div>
  );
}

export function ApiKeyMissingHelp() {
  return (
    <>
      <p>
        LLM açıklamaları için <code className="font-mono text-text">ANTHROPIC_API_KEY</code> ortam
        değişkeni gerekiyor. Anahtarı tanımlayıp sunucuyu yeniden başlatın:
      </p>
      <pre className="mt-3 overflow-x-auto rounded-xl border border-border bg-white/[0.02] p-4 text-left font-mono text-xs text-text">
        export ANTHROPIC_API_KEY=…{'\n'}python -m server
      </pre>
      <p className="mt-3 text-xs text-subtle">Anahtarın değeri arayüze hiçbir zaman gönderilmez.</p>
    </>
  );
}
