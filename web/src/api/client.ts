// The single module that talks to the backend. Components must not call fetch directly.
import { API_BASE } from '../config';
import {
  ERROR_CODES,
  type AnalyzeResult,
  type AnalyzeStarted,
  type ApplyResponse,
  type BrowseResponse,
  type ErrorPayload,
  type HealthResponse,
  type Place,
  type ProgressEvent,
} from './types';

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(payload: ErrorPayload, status: number) {
    super(payload.message);
    this.code = payload.code;
    this.status = status;
  }

  toPayload(): ErrorPayload {
    return { code: this.code, message: this.message };
  }
}

const NETWORK_ERROR: ErrorPayload = {
  code: ERROR_CODES.network,
  message: 'Sunucuya ulaşılamıyor. `python -m server` çalışıyor mu?',
};

function isErrorPayload(value: unknown): value is ErrorPayload {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as ErrorPayload).code === 'string' &&
    typeof (value as ErrorPayload).message === 'string'
  );
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(NETWORK_ERROR, 0);
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const payload = isErrorPayload(body)
      ? body
      : { code: 'http_error', message: `Beklenmeyen yanıt (${response.status}).` };
    throw new ApiError(payload, response.status);
  }
  return body as T;
}

function postJson<T>(path: string, data: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export function toErrorPayload(err: unknown): ErrorPayload {
  if (err instanceof ApiError) return err.toPayload();
  return { code: 'unknown', message: 'Beklenmeyen bir hata oluştu.' };
}

export const api = {
  health: () => request<HealthResponse>('/api/health'),

  startAnalyze: (path: string, verify: boolean) =>
    postJson<AnalyzeStarted>('/api/analyze', { path, verify }),

  cancelAnalyze: async (jobId: string): Promise<void> => {
    await fetch(`${API_BASE}/api/analyze/${encodeURIComponent(jobId)}/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    }).catch(() => undefined);
  },

  browse: (path?: string, showHidden = false) => {
    const params = new URLSearchParams();
    if (path) params.set('path', path);
    if (showHidden) params.set('show_hidden', 'true');
    const query = params.toString();
    return request<BrowseResponse>(`/api/browse${query ? `?${query}` : ''}`);
  },

  places: () => request<Place[]>('/api/places'),

  apply: (jobId: string, suggestionIds: string[]) =>
    postJson<ApplyResponse>('/api/apply', { job_id: jobId, suggestion_ids: suggestionIds }),
};

export interface AnalysisHandlers {
  onProgress: (event: ProgressEvent) => void;
  onResult: (result: AnalyzeResult) => void;
  onError: (error: ErrorPayload) => void;
}

/**
 * Subscribe to a job's Server-Sent Events. Exactly one of onResult/onError is
 * called at the end. Returns an unsubscribe function.
 */
export function subscribeToAnalysis(jobId: string, handlers: AnalysisHandlers): () => void {
  const source = new EventSource(`${API_BASE}/api/analyze/${encodeURIComponent(jobId)}/events`);
  let finished = false;
  const finish = () => {
    finished = true;
    source.close();
  };

  source.addEventListener('progress', (e) => {
    handlers.onProgress(JSON.parse((e as MessageEvent<string>).data) as ProgressEvent);
  });
  source.addEventListener('result', (e) => {
    finish();
    handlers.onResult(JSON.parse((e as MessageEvent<string>).data) as AnalyzeResult);
  });
  // "error" is both our terminal server event and EventSource's native connection error.
  source.addEventListener('error', (e) => {
    if (finished) return;
    finish();
    const data = e instanceof MessageEvent && typeof e.data === 'string' ? e.data : null;
    const parsed: unknown = data ? JSON.parse(data) : null;
    handlers.onError(
      isErrorPayload(parsed)
        ? parsed
        : { code: ERROR_CODES.network, message: 'Sunucu bağlantısı koptu.' },
    );
  });

  return finish;
}
