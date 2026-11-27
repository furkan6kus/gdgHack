// Small presentational primitives shared across screens.
import type { ButtonHTMLAttributes, ReactNode } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  // Solid green with dark text, like Kule's "Onayla".
  primary: 'bg-ok font-semibold text-[#022c22] shadow-lg shadow-ok/20 hover:brightness-110',
  secondary: 'border border-border text-text hover:border-border-strong hover:bg-white/[0.04]',
  ghost: 'text-muted hover:text-text hover:bg-white/[0.04]',
  danger: 'bg-err font-semibold text-white shadow-lg shadow-err/20 hover:brightness-110',
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: 'sm' | 'md';
}

export function Button({
  variant = 'secondary',
  size = 'md',
  className = '',
  type = 'button',
  ...rest
}: ButtonProps) {
  const sizing = size === 'sm' ? 'h-8 rounded-lg px-3 text-xs' : 'h-10 rounded-xl px-4 text-sm';
  return (
    <button
      type={type}
      className={`inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap font-medium transition-[background,border,filter,color] duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:pointer-events-none disabled:opacity-40 ${sizing} ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    />
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded border border-border bg-panel px-1.5 py-px font-sans text-[11px] text-muted">
      {children}
    </kbd>
  );
}

export function Spinner({ className = 'size-4' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.2" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function Switch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
}) {
  return (
    <label className="inline-flex cursor-pointer select-none items-center gap-2.5 text-sm">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-5 w-9 rounded-full transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${checked ? 'bg-accent' : 'bg-border'}`}
      >
        <span
          className={`absolute top-0.5 left-0 size-4 rounded-full bg-white shadow transition-transform duration-150 ${checked ? 'translate-x-4.5' : 'translate-x-0.5'}`}
        />
      </button>
      <span>{label}</span>
    </label>
  );
}

/** Card surface: the one container style used across screens. */
export const CARD = 'rounded-2xl border border-border bg-panel';

/** Inset box inside a card (e.g. "Kaldığın Yer" style summaries). */
export const INSET = 'rounded-xl border border-border bg-white/[0.02]';

export type Tone = 'info' | 'warn' | 'err' | 'ok' | 'neutral';

const PILL_TONES: Record<Tone, { pill: string; dot: string }> = {
  info: { pill: 'bg-info/10 text-sky-300 ring-info/25', dot: 'bg-info' },
  warn: { pill: 'bg-warn/10 text-amber-300 ring-warn/30', dot: 'bg-warn' },
  err: { pill: 'bg-err/10 text-rose-300 ring-err/30', dot: 'bg-err' },
  ok: { pill: 'bg-ok/10 text-emerald-300 ring-ok/25', dot: 'bg-ok' },
  neutral: { pill: 'bg-white/[0.04] text-muted ring-border', dot: 'bg-subtle' },
};

/** Status pill: small uppercase label with a coloured dot (Kule style). */
export function Pill({
  tone = 'neutral',
  pulse = false,
  className = '',
  children,
}: {
  tone?: Tone;
  pulse?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const t = PILL_TONES[tone];
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide ring-1 ring-inset ${t.pill} ${className}`}
    >
      <span className={`size-1.5 rounded-full ${t.dot} ${pulse ? 'animate-pulse' : ''}`} />
      {children}
    </span>
  );
}

const CALLOUT_TONES: Record<Tone, string> = {
  info: 'border-info/15 bg-info/[0.06] text-sky-100/90',
  warn: 'border-warn/20 bg-warn/[0.07] text-amber-100/90',
  err: 'border-err/20 bg-err/[0.07] text-rose-100/90',
  ok: 'border-ok/20 bg-ok/[0.07] text-emerald-100/90',
  neutral: 'border-border bg-white/[0.02] text-text',
};

/** Soft tinted message box (running / waiting / error / done states). */
export function Callout({
  tone = 'neutral',
  className = '',
  children,
}: {
  tone?: Tone;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={`rounded-xl border p-4 text-sm leading-relaxed ${CALLOUT_TONES[tone]} ${className}`}>
      {children}
    </div>
  );
}

/** Rounded pill counter for header bars ("Bulgular: 12"). */
export function StatBadge({ dot, children }: { dot?: string; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-border bg-panel px-3 py-1.5 text-sm text-muted">
      {dot && <span className={`size-2 rounded-full ${dot}`} />}
      {children}
    </span>
  );
}
