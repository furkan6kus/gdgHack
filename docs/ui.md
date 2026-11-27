# mytool UI

## 1. Overview

A local-only web app for the `analyze` command: pick a folder, watch live
progress, review findings and LLM suggestions with diffs, and apply the ones
whose verification passed. It runs on your machine and is never exposed to the
network. A Tauri desktop wrapper is planned for later.

## 2. Prerequisites

- Python >= 3.11
- Node >= 20

## 3. Setup

The server imports the `mytool` core, so everything is installed from the repo
root into one virtualenv (the `ui` dependency group adds FastAPI and uvicorn):

```bash
uv sync --group ui
cd web && npm ci
```

Set `ANTHROPIC_API_KEY` before starting the server; the UI uses the real core
by default and refuses to analyze without a key.

## 4. Dev mode (two terminals)

```bash
# terminal 1, from the repo root (port 8765)
uv run python -m server --no-browser

# terminal 2
cd web && npm run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` to port 8765. If `web/dist`
exists the backend also serves it, which is harmless in dev mode; if it is
missing, the backend serves the API only.

## 5. Production / single process

```bash
cd web && npm run build
cd .. && uv run python -m server
```

Opens http://127.0.0.1:8765 (API and built frontend from one process). The
browser opens only once the server accepts connections; if `web/dist` is missing
the page explains how to build it. Use `--port` if 8765 is taken.

> `web/dist` is a build artifact and is not committed: run the build once after
> cloning or pulling frontend changes.

## 6. Configuration

| Variable | Values | Meaning |
|---|---|---|
| `MYTOOL_UI_ADAPTER` | `core` (default), `mock` | Which adapter backs the API (`mock` = fake data, no API key needed) |
| `MYTOOL_MODEL` | model name | Core adapter: model used for suggestions (default `claude-sonnet-5-5`) |
| `MYTOOL_UI_MOCK_SCENARIO` | `ok`, `empty`, `error`, `no_key` | Mock behaviour for demos |
| `MYTOOL_UI_MOCK_DELAY` | number | Delay multiplier for the mock (`0` = instant) |
| `MYTOOL_UI_DIST` | path | Override the built frontend directory |
| `ANTHROPIC_API_KEY` | string | Core adapter: required. Only its presence is reported; the value is never sent to the UI |

## 7. Architecture

```
Browser (React app)
  web/src/api/client.ts      <- the ONLY place that talks HTTP
        |  JSON + SSE
        v
FastAPI (server/)
  app.py     routes, middleware, apply rules
  jobs.py    job store + SSE event history
  browse.py  folder listing + deny-list
        |
        v
Adapter protocol (server/adapters/base.py)
   |                         |
MockAdapter              CoreAdapter  (core models -> UI contract)
(fake data)                  |
                             v
              mytool.core.pipeline.analyze(on_progress, should_cancel)
              mytool.core.apply.apply_suggestions
```

- The adapter runs in a worker thread and reports progress through a
  thread-safe callback; events are appended to the job's history, so late SSE
  clients get a full replay.
- SSE emits `progress` events, then exactly one terminal `result` or `error`.
- Suggestions whose verification failed are stripped server-side and never
  reach the UI.
- `/api/apply` accepts only suggestions with `verification.status == "passed"`;
  a request containing anything else is rejected as a whole.
- `server/contracts.py` is the JSON the browser reads. It stays separate from
  `mytool.core.models` on purpose; `CoreAdapter` converts between them.
- Verification mapping: only a test-backed pass (`pytest`/benchmark) is shown
  as `passed` and can be applied from the UI. A syntax-only check (project has
  no tests, tests fail on the baseline, project too large) is shown as
  `skipped` with "Doğrulanamadı: yalnız sözdizimi denetlendi", the same rule as
  the CLI's `--fix`.
- `CoreAdapter` keeps the last 20 core runs in memory so `apply` can hand the
  core its own reports; a file edited after the analysis is refused
  (`apply_failed`) instead of being patched blindly.

## 8. API

| Endpoint | Description |
|---|---|
| `GET /api/health` | `{status, adapter, api_key_configured}` |
| `POST /api/analyze` `{path, verify}` | Start a job on a folder or a single file, returns `{job_id}` |
| `GET /api/analyze/{job_id}/events` | SSE stream: `progress`..., then `result` or `error` |
| `POST /api/analyze/{job_id}/cancel` | Cancel a running job (204) |
| `GET /api/browse?path=&show_hidden=` | List a directory (default: home; a file path lists its folder) |
| `GET /api/places` | Picker quick access: home, the OS's real Desktop/Documents/Downloads (Windows Known Folders, Linux XDG user-dirs; name guesses as fallback), drives |
| `POST /api/apply` `{job_id, suggestion_ids}` | Apply passed suggestions; returns `{applied_ids, changed_files, backup_path}` |

Errors always have the body `{"code": "...", "message": "..."}`. Common codes:
`path_not_found` (404), `path_denied` (403),
`invalid_request` (422), `unsupported_media_type` (415), `job_not_found` (404),
`job_not_finished` (409), `unknown_suggestion`, `not_verified`,
`already_applied` (409), `api_key_missing`, `analysis_failed` (500), `apply_failed` (409),
`cancelled`. (`analyzer_failed` is only produced by the mock.)

## 9. Security notes

- Binds to 127.0.0.1 only.
- Host header allow-list (`127.0.0.1`, `localhost`) protects against DNS rebinding.
- POST requires `Content-Type: application/json`, which blocks cross-site form posts.
- CORS allows only the Vite dev origin (port 5173).
- Browse deny-list (case-insensitive, never listed or enterable): `.env`,
  `.env.*`, `*.env`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.keystore`,
  `id_rsa*`/`id_dsa*`/`id_ecdsa*`/`id_ed25519*`, `.netrc`, `.pgpass`, `.npmrc`,
  `.pypirc`, `credentials*`, `secrets*`, `.ssh`, `.gnupg`, `.aws`, `.docker`, `.kube`.
- Stack traces are logged on the server and never sent to the UI.

## 10. Core adapter (Phase 2, done)

The UI runs on the real core by default. `CoreAdapter` calls
`mytool.core.pipeline.analyze(..., on_progress=..., should_cancel=...)`, maps
`Cancelled` to the `cancelled` state and any run error (ruff failure, fatal
LLM error such as an invalid key or rate limit) to `analysis_failed` with the
core's Turkish message. Non-fatal warnings are logged on the server.

Cancellation is checked between units of work (per file, per LLM call, per
verification); a test run already in progress finishes (bounded by the
subprocess timeout) before the job stops.

For demos without an API key: `MYTOOL_UI_ADAPTER=mock`.

## 11. Quality checks

```bash
# from server/
uv run ruff check . && uv run ruff format --check .
uv run mypy .
uv run python -m pytest

# from web/
npm run lint && npm run typecheck && npm run build
```

## 12. Keyboard shortcuts (results screen)

| Key | Action |
|---|---|
| `j` / `↓` | next finding |
| `k` / `↑` | previous finding |
| `Space` | toggle the selected finding's suggestion (only ✓ passed ones are selectable) |
| `Esc` | close the open modal |
| any key / click | skip the splash animation |

Shortcuts are ignored while typing in an input or when focus is inside the diff editor.

## 13. UI behaviour notes

- Results are two columns: suggestions grouped by file (left) and detail + side-by-side diff (right).
  Findings without a suggestion live in a collapsed "Önerisiz bulgular" section.
- The picker ("Gözat…") has a quick-access sidebar and can select a folder **or a single file**
  (click a file, then "Bu dosyayı seç", or double-click it), with a search box to filter the current folder. Browsing a file path lists its folder.

- Category chips: `HATA` = bug, `PERF` = perf, `STİL` = style (shrink/translate are not shown for analyze).
  There is no severity filter; severity is the coloured bar on each row (*Ciddi / Uyarı / Bilgi* on hover).
- ⚠ (skipped) suggestions are listed with their explanation and diff but cannot be selected or applied.
- With "Doğrulama yapma" on, every suggestion is ⚠ skipped, so nothing can be applied in that run.
- Visual style is shared with the Kule dashboard (`public/index.html`): slate palette tokens in `web/src/index.css`,
  `CARD`/`INSET`/`Pill`/`Callout`/`StatBadge` in `web/src/components/ui.tsx`. Inter and JetBrains Mono are bundled
  locally via `@fontsource` (no Google Fonts request); mono is used only for paths, file names and code.
- Mock demo states: `MYTOOL_UI_MOCK_SCENARIO=empty|error|no_key python -m server`.
