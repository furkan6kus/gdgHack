import type { Category, Severity, Stage } from '../api/types';
import type { Tone } from '../components/ui';

export const STAGE_ORDER: Exclude<Stage, 'error'>[] = [
  'parsing',
  'static_analysis',
  'llm',
  'verify',
  'done',
];

export const STAGE_LABELS: Record<Stage, string> = {
  parsing: 'Dosyalar ayrıştırılıyor',
  static_analysis: 'Statik analiz (ruff)',
  llm: 'LLM açıklama ve yama önerileri',
  verify: 'Yamalar doğrulanıyor',
  done: 'Tamamlandı',
  error: 'Hata',
};

// Filter chips shown for analyze. shrink/translate belong to other commands.
export const CATEGORY_CHIPS: { value: Category; label: string }[] = [
  { value: 'bug', label: 'HATA' },
  { value: 'security', label: 'GÜVENLİK' },
  { value: 'perf', label: 'PERF' },
  { value: 'style', label: 'STİL' },
];

export const CATEGORY_LABELS: Record<Category, string> = {
  bug: 'HATA',
  security: 'GÜVENLİK',
  perf: 'PERF',
  style: 'STİL',
  shrink: 'KÜÇÜLTME',
  translate: 'ÇEVİRİ',
};

// "Hata" is already the bug category, so error severity is labelled "Ciddi".
export const SEVERITY_LABELS: Record<Severity, string> = {
  error: 'Ciddi',
  warning: 'Uyarı',
  info: 'Bilgi',
};

export const SEVERITY_TEXT: Record<Severity, string> = {
  error: 'text-err',
  warning: 'text-warn',
  info: 'text-info',
};

export const SEVERITY_BG: Record<Severity, string> = {
  error: 'bg-err',
  warning: 'bg-warn',
  info: 'bg-info',
};

export const SEVERITY_TONE: Record<Severity, Tone> = {
  error: 'err',
  warning: 'warn',
  info: 'info',
};

export function formatDuration(ms: number): string {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} sn`;
}

export function formatNumber(n: number): string {
  return n.toLocaleString('tr-TR');
}
