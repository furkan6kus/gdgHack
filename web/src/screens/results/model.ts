import type { AnalyzeResult, Category, Finding, Severity, Suggestion } from '../../api/types';

export interface FindingRow {
  finding: Finding;
  suggestion: Suggestion | null;
}

export interface Filters {
  categories: ReadonlySet<Category>;
  severities: ReadonlySet<Severity>;
  file: string | null;
}

export const EMPTY_FILTERS: Filters = { categories: new Set(), severities: new Set(), file: null };

/** Join findings with their (non-failed) suggestion, sorted by file and line. */
export function buildRows(result: AnalyzeResult): FindingRow[] {
  const byFinding = new Map<string, Suggestion>();
  for (const s of result.suggestions) {
    if (s.verification.status === 'failed') continue; // defensive: server already strips these
    for (const id of s.finding_ids) byFinding.set(id, s);
  }
  return [...result.findings]
    .sort((a, b) => a.file.localeCompare(b.file) || a.line_start - b.line_start)
    .map((finding) => ({ finding, suggestion: byFinding.get(finding.id) ?? null }));
}

export function applyFilters(rows: FindingRow[], filters: Filters): FindingRow[] {
  return rows.filter(({ finding, suggestion }) => {
    if (filters.file !== null && finding.file !== filters.file) return false;
    if (filters.severities.size > 0 && !filters.severities.has(finding.severity)) return false;
    if (filters.categories.size > 0) {
      return suggestion !== null && filters.categories.has(suggestion.category);
    }
    return true;
  });
}

export function isFiltered(filters: Filters): boolean {
  return filters.file !== null || filters.categories.size > 0 || filters.severities.size > 0;
}

export function isApplicable(suggestion: Suggestion | null, applied: ReadonlySet<string>): boolean {
  return suggestion !== null && suggestion.verification.status === 'passed' && !applied.has(suggestion.id);
}

export function toggleIn<T>(set: ReadonlySet<T>, value: T): Set<T> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

export function languageFor(file: string): string {
  const ext = file.split('.').pop()?.toLowerCase() ?? '';
  const map: Record<string, string> = {
    py: 'python',
    ts: 'typescript',
    tsx: 'typescript',
    js: 'javascript',
    jsx: 'javascript',
    json: 'json',
    md: 'markdown',
  };
  return map[ext] ?? 'plaintext';
}

export function basename(path: string): string {
  return path.split('/').pop() ?? path;
}
