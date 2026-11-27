import { useEffect, useRef, useState } from 'react';
import type { Effort, LLMChoice, ModelInfo } from '../api/types';
import { EFFORT_LABELS, formatUsd } from '../lib/llmChoice';

interface ModelPickerProps {
  choice: LLMChoice | null;
  models: ModelInfo[];
  onChange: (next: LLMChoice) => void;
  /** API money spent in this browser session (analyses + chat). */
  spent: number;
}

const EFFORTS: Effort[] = ['low', 'medium', 'high'];

const EFFORT_NOTES: Record<Effort, string> = {
  low: 'Az düşünür, en ucuz',
  medium: 'Çoğu iş için yeterli',
  high: 'Zor hatalarda daha iyi, daha pahalı',
};

/** Compact "Sonnet 5.5 · Dengeli" button with a popover to change model and effort. */
export function ModelPicker({ choice, models, onChange, spent }: ModelPickerProps) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const current = models.find((m) => m.id === choice?.model);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    window.addEventListener('mousedown', close);
    window.addEventListener('keydown', esc);
    return () => {
      window.removeEventListener('mousedown', close);
      window.removeEventListener('keydown', esc);
    };
  }, [open]);

  if (!choice) return null;
  return (
    <div ref={box} className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-[var(--radius-control)] border border-border bg-panel px-2.5 py-1 text-[13px] text-strong hover:border-border-strong focus-visible:outline-2 focus-visible:outline-accent"
      >
        <span className="font-semibold">{current?.name ?? choice.model}</span>
        <span className="text-subtle">{EFFORT_LABELS[choice.effort]}</span>
        <span className="border-l border-border pl-2 text-subtle tabular-nums" title="Bu oturumda harcanan API ücreti">
          {formatUsd(spent)}
        </span>
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Model seçimi"
          className="absolute right-0 z-50 mt-2 w-[340px] rounded-[var(--radius-sheet)] border border-border bg-panel p-3 shadow-xl shadow-strong/10"
        >
          <p className="px-1 pb-2 text-[13px] font-semibold text-strong">Model</p>
          <ul className="space-y-1">
            {models.map((m) => {
              const selected = m.id === choice.model;
              return (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => onChange({ ...choice, model: m.id })}
                    className={`flex w-full items-start gap-3 rounded-[var(--radius-control)] px-2.5 py-2 text-left focus-visible:outline-2 focus-visible:outline-accent ${selected ? 'bg-accent-soft' : 'hover:bg-hover'}`}
                  >
                    <span
                      aria-hidden
                      className={`mt-1 size-3.5 shrink-0 rounded-full border-[3px] ${selected ? 'border-accent' : 'border-border'}`}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline justify-between gap-2">
                        <span className="text-sm font-semibold text-strong">{m.name}</span>
                        <span className="text-[12px] text-subtle tabular-nums">
                          ${m.input_per_mtok} / ${m.output_per_mtok}
                        </span>
                      </span>
                      <span className="block text-[12px] text-subtle">{m.note}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          <p className="px-1 pt-1 text-[11.5px] text-hint">Fiyat: 1 milyon token başına girdi / çıktı (USD).</p>

          <p className="px-1 pt-4 pb-2 text-[13px] font-semibold text-strong">Düşünme seviyesi</p>
          <div className="grid grid-cols-3 gap-1 rounded-[var(--radius-control)] bg-sunken p-0.5">
            {EFFORTS.map((effort) => (
              <button
                key={effort}
                type="button"
                aria-pressed={choice.effort === effort}
                onClick={() => onChange({ ...choice, effort })}
                className={`rounded-[8px] py-1.5 text-[13px] font-semibold focus-visible:outline-2 focus-visible:outline-accent ${choice.effort === effort ? 'bg-panel text-strong shadow-sm' : 'text-subtle hover:text-strong'}`}
              >
                {EFFORT_LABELS[effort]}
              </button>
            ))}
          </div>
          <p className="px-1 pt-1.5 text-[12px] text-subtle">{EFFORT_NOTES[choice.effort]}</p>

          <div className="mt-4 flex items-baseline justify-between border-t border-border px-1 pt-3 text-[13px]">
            <span className="text-muted">Bu oturumda harcanan</span>
            <span className="font-semibold text-strong tabular-nums">{formatUsd(spent)}</span>
          </div>
          <p className="px-1 pt-1 text-[11.5px] text-hint">
            Her analizin ve sohbet yanıtının tahmini ücreti eklenir; kesin tutar Anthropic Console'dadır.
          </p>
        </div>
      )}
    </div>
  );
}
