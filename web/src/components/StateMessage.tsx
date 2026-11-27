import { motion } from 'framer-motion';
import type { ReactNode } from 'react';

type Tone = 'neutral' | 'ok' | 'warn' | 'err';

const TONE_RING: Record<Tone, string> = {
  neutral: 'bg-panel-2 text-muted',
  ok: 'bg-ok/12 text-ok',
  warn: 'bg-warn/12 text-warn',
  err: 'bg-err/12 text-err',
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
      className="mx-auto flex max-w-md flex-col items-center gap-3 px-6 text-center"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className={`flex size-12 items-center justify-center rounded-full text-xl ${TONE_RING[tone]}`}>
        {icon}
      </div>
      <h2 className="text-base font-semibold">{title}</h2>
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
      <pre className="mt-3 rounded-md border border-border bg-panel px-3 py-2 text-left font-mono text-xs text-text">
        export ANTHROPIC_API_KEY=…{'\n'}python -m server
      </pre>
      <p className="mt-2 text-xs">Anahtarın değeri arayüze hiçbir zaman gönderilmez.</p>
    </>
  );
}
