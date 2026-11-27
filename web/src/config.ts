// Product name lives here only; it may change.
export const APP_NAME = 'mytool';

// Empty = same origin (FastAPI serves the app, or Vite proxies /api in dev).
// A desktop wrapper can set VITE_API_BASE to an absolute URL.
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? '';

export const STORAGE_KEYS = {
  recentPaths: `${APP_NAME}.recentPaths`,
  verify: `${APP_NAME}.verify`,
  verifyNoticeSeen: `${APP_NAME}.verifyNoticeSeen`,
} as const;

export const MAX_RECENT_PATHS = 6;
export const SPLASH_MS = 1700;
