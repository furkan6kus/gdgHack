import type { AnalyzeResult, Category, Finding, Suggestion } from '../../api/types';

export interface FindingRow {
  finding: Finding;
  suggestion: Suggestion | null;
}

export interface FileGroup {
  file: string;
  rows: FindingRow[];
}

export type CategoryFilter = Category | 'all';

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

/** Rows that carry a suggestion and match the category filter. */
export function suggestionRows(rows: FindingRow[], category: CategoryFilter): FindingRow[] {
  return rows.filter(
    (r) => r.suggestion !== null && (category === 'all' || r.suggestion.category === category),
  );
}

export function orphanRows(rows: FindingRow[]): FindingRow[] {
  return rows.filter((r) => r.suggestion === null);
}

/** Group consecutive rows by file; rows are already sorted by file. */
export function groupByFile(rows: FindingRow[]): FileGroup[] {
  const groups: FileGroup[] = [];
  for (const row of rows) {
    const last = groups.at(-1);
    if (last?.file === row.finding.file) last.rows.push(row);
    else groups.push({ file: row.finding.file, rows: [row] });
  }
  return groups;
}

export function countByCategory(rows: FindingRow[]): Record<CategoryFilter, number> {
  const counts: Record<CategoryFilter, number> = {
    all: 0,
    bug: 0,
    security: 0,
    perf: 0,
    style: 0,
    shrink: 0,
    translate: 0,
  };
  for (const { suggestion } of rows) {
    if (!suggestion) continue;
    counts.all += 1;
    counts[suggestion.category] += 1;
  }
  return counts;
}

/** Short, human title for a row: the LLM title when present, else the analyzer message. */
export function rowTitle(row: FindingRow): string {
  return row.suggestion?.title || row.finding.message;
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
    md: 'markdown',
  };
  return map[ext] ?? 'plaintext';
}
