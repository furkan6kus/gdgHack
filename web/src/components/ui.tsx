// Small presentational primitives shared across screens.
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import type { Severity, VerificationStatus } from '../api/types';
import { SEVERITY_BG, SEVERITY_LABELS } from '../lib/labels';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-white hover:brightness-110 shadow-[0_0_0_1px_#ffffff1a_inset]',
  secondary: 'bg-panel-2 text-text border border-border hover:border-muted/60',
  ghost: 'text-muted hover:text-text hover:bg-panel-2',
  danger: 'bg-err/15 text-err border border-err/30 hover:bg-err/25',
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
  const sizing = size === 'sm' ? 'h-7 px-2.5 text-xs' : 'h-9 px-3.5 text-sm';
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-2 rounded-md font-medium transition-[background,border,filter,color] duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:pointer-events-none disabled:opacity-40 ${sizing} ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    />
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded border border-border bg-panel-2 px-1.5 py-px font-mono text-[10px] text-muted">
      {children}
    </kbd>
  );
}

export function SeverityDot({ severity }: { severity: Severity }) {
  return (
    <span
      title={SEVERITY_LABELS[severity]}
      className={`inline-block size-2 shrink-0 rounded-full ${SEVERITY_BG[severity]}`}
    />
  );
}

const BADGE: Record<Exclude<VerificationStatus, 'failed'>, { icon: string; label: string; cls: string }> =
  {
    passed: { icon: '✓', label: 'Doğrulandı', cls: 'bg-ok/12 text-ok border-ok/25' },
    skipped: { icon: '⚠', label: 'Doğrulanamadı', cls: 'bg-warn/12 text-warn border-warn/25' },
  };

export function VerificationBadge({
  status,
  compact = false,
}: {
  status: VerificationStatus | null;
  compact?: boolean;
}) {
  if (status === null || status === 'failed') {
    return (
      <span className="rounded border border-border px-1.5 py-px text-[10px] text-muted">
        öneri yok
      </span>
    );
  }
  const badge = BADGE[status];
  return (
    <span
      title={badge.label}
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-px text-[11px] font-medium ${badge.cls}`}
    >
      <span aria-hidden>{badge.icon}</span>
      {!compact && badge.label}
    </span>
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
