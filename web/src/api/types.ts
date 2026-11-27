// Hand-mirrored from server/contracts.py and server/schemas.py.
// Keep in sync with the backend contract; this is the ONLY place these shapes live.

export type Severity = 'error' | 'warning' | 'info';
export type Category = 'bug' | 'security' | 'perf' | 'style' | 'shrink' | 'translate';
export type VerificationStatus = 'passed' | 'failed' | 'skipped';
export type Stage = 'parsing' | 'static_analysis' | 'llm' | 'verify' | 'done' | 'error';

export interface Finding {
  id: string;
  tool: string;
  file: string;
  line_start: number;
  line_end: number;
  severity: Severity;
  rule_code: string;
  message: string;
}

export interface Patch {
  file: string;
  original_text: string;
  new_text: string;
}

export interface VerificationResult {
  status: VerificationStatus;
  detail: string;
  duration_ms: number;
}

export interface Suggestion {
  id: string;
  finding_ids: string[];
  category: Category;
  explanation: string;
  /** UI addition (see docs/ui-core-requests.md §10); may be absent from the core. */
  title?: string | null;
  patch: Patch;
  verification: VerificationResult;
}

export interface SeverityCounts {
  error: number;
  warning: number;
  info: number;
}

export interface FileSummary {
  path: string;
  line_count: number;
  counts: SeverityCounts;
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
}

export interface AnalyzeResult {
  root: string;
  files: FileSummary[];
  findings: Finding[];
  suggestions: Suggestion[];
  token_usage: TokenUsage;
}

export interface ProgressEvent {
  stage: Stage;
  message: string;
  current: number | null;
  total: number | null;
}

// ---- HTTP layer (server/schemas.py)

export interface ErrorPayload {
  code: string;
  message: string;
}

export interface AnalyzeStarted {
  job_id: string;
}

export interface ApplyResponse {
  applied_ids: string[];
  changed_files: string[];
  backup_path: string;
}

export interface BrowseEntry {
  name: string;
  path: string;
  is_dir: boolean;
}

export interface BrowseResponse {
  path: string;
  parent: string | null;
  entries: BrowseEntry[];
}

export interface Place {
  name: string;
  path: string;
  kind: 'home' | 'folder' | 'drive';
}

export interface HealthResponse {
  status: string;
  adapter: string;
  api_key_configured: boolean;
}

export const ERROR_CODES = {
  apiKeyMissing: 'api_key_missing',
  cancelled: 'cancelled',
  network: 'network',
} as const;
