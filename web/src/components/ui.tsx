// Small presentational primitives shared across screens.
import type { ButtonHTMLAttributes, ReactNode } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: 'bg-accent font-semibold text-on-accent hover:bg-[#0068d9] active:bg-[#0058b8]',
  secondary: 'border border-border bg-panel text-strong hover:border-border-strong hover:bg-hover',
  ghost: 'text-muted hover:bg-hover hover:text-strong',
  danger: 'bg-err font-semibold text-white hover:bg-err-ink',
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
  const sizing = size === 'sm' ? 'h-8 px-3 text-[13px]' : 'h-10 px-4 text-sm';
  return (
    <button
      type={type}
      className={`inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-control)] font-medium transition-[background,border,color] duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:pointer-events-none disabled:opacity-40 ${sizing} ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    />
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded-[4px] border border-b-2 border-border bg-panel px-1.5 py-px font-mono text-[12px] text-muted">
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

/** A sheet of paper on the porcelain page. Borders, not shadows. */
export const CARD = 'rounded-[var(--radius-sheet)] border border-border bg-panel';

/** A recessed area inside a sheet (lists, code paths, summaries). */
export const INSET = 'rounded-[var(--radius-control)] border border-border bg-sunken';

export type Tone = 'info' | 'warn' | 'err' | 'ok' | 'neutral';

const PILL_TONES: Record<Tone, { pill: string; dot: string }> = {
  info: { pill: 'bg-info-wash text-info-ink', dot: 'bg-info' },
  warn: { pill: 'bg-warn-wash text-warn-ink', dot: 'bg-warn' },
  err: { pill: 'bg-err-wash text-err-ink', dot: 'bg-err' },
  ok: { pill: 'bg-ok-wash text-ok-ink', dot: 'bg-ok' },
  neutral: { pill: 'bg-sunken text-muted', dot: 'bg-subtle' },
};

/** Status tag: what a finding or a step means, in its chart colour. */
export function Pill({
  tone = 'neutral',
  pulse = false,
  dot = true,
  className = '',
  children,
}: {
  tone?: Tone;
  pulse?: boolean;
  /** Hide the dot when the label is already a status glyph (✓ / ⚠). */
  dot?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const t = PILL_TONES[tone];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[12px] font-semibold ${t.pill} ${className}`}
    >
      {dot && <span className={`size-1.5 rounded-full ${t.dot} ${pulse ? 'animate-pulse' : ''}`} />}
      {children}
    </span>
  );
}

// A coloured rule on the left says what kind of message it is; the text stays ink.
const CALLOUT_TONES: Record<Tone, string> = {
  info: 'border-l-info bg-info-wash text-info-ink',
  warn: 'border-l-warn bg-warn-wash text-warn-ink',
  err: 'border-l-err bg-err-wash text-err-ink',
  ok: 'border-l-ok bg-ok-wash text-ok-ink',
  neutral: 'border-l-border-strong bg-sunken text-text',
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
    <div
      className={`rounded-[var(--radius-control)] border-l-[3px] p-4 text-sm leading-relaxed ${CALLOUT_TONES[tone]} ${className}`}
    >
      {children}
    </div>
  );
}

/** Counter for header bars ("12 bulgu"). */
export function StatBadge({ dot, children }: { dot?: string; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted">
      {dot && <span className={`size-2 rounded-full ${dot}`} />}
      {children}
    </span>
  );
}
