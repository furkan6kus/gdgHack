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

Dependencies are declared in `server/pyproject.toml`. `server/` is not an
installable package, so install the dependencies directly:

```bash
python -m venv .venv
.venv/bin/pip install fastapi uvicorn "pydantic>=2.7"
.venv/bin/pip install pytest httpx ruff mypy      # dev tools
cd web && npm ci
```

## 4. Dev mode (two terminals)

```bash
# terminal 1, from the repo root (port 8765)
python -m server --no-browser

# terminal 2
cd web && npm run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` to port 8765. If `web/dist`
exists the backend also serves it, which is harmless in dev mode; if it is
missing, the backend serves the API only.

## 5. Production / single process

```bash
cd web && npm run build
cd .. && python -m server
```

Opens http://127.0.0.1:8765 (API and built frontend from one process).

## 6. Configuration

| Variable | Values | Meaning |
|---|---|---|
| `MYTOOL_UI_ADAPTER` | `mock` (default), `core` | Which adapter backs the API |
| `MYTOOL_UI_MOCK_SCENARIO` | `ok`, `empty`, `error`, `no_key` | Mock behaviour for demos |
| `MYTOOL_UI_MOCK_DELAY` | number | Delay multiplier for the mock (`0` = instant) |
| `MYTOOL_UI_DIST` | path | Override the built frontend directory |
| `ANTHROPIC_API_KEY` | string | Core adapter only. Only its presence is checked; the value is never sent to the UI |

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
MockAdapter              CoreAdapter
(fake data)                  |
                             v
                        core.pipeline (teammates)
```

- The adapter runs in a worker thread and reports progress through a
  thread-safe callback; events are appended to the job's history, so late SSE
  clients get a full replay.
- SSE emits `progress` events, then exactly one terminal `result` or `error`.
- Suggestions whose verification failed are stripped server-side and never
  reach the UI.
- `/api/apply` accepts only suggestions with `verification.status == "passed"`;
  a request containing anything else is rejected as a whole.
- The data contracts in `server/contracts.py` are TEMPORARY until
  `core/models.py` exists.

## 8. API

| Endpoint | Description |
|---|---|
| `GET /api/health` | `{status, adapter, api_key_configured}` |
| `POST /api/analyze` `{path, verify}` | Start a job, returns `{job_id}` |
| `GET /api/analyze/{job_id}/events` | SSE stream: `progress`..., then `result` or `error` |
| `POST /api/analyze/{job_id}/cancel` | Cancel a running job (204) |
| `GET /api/browse?path=&show_hidden=` | List a directory (default: home) |
| `POST /api/apply` `{job_id, suggestion_ids}` | Apply passed suggestions; returns `{applied_ids, changed_files, backup_path}` |

Errors always have the body `{"code": "...", "message": "..."}`. Common codes:
`path_not_found` (404), `not_a_directory`, `path_denied` (403),
`invalid_request` (422), `unsupported_media_type` (415), `job_not_found` (404),
`job_not_finished` (409), `unknown_suggestion`, `not_verified`,
`already_applied` (409), `api_key_missing`, `analyzer_failed`, `cancelled`.

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

## 10. Switching from mock to core adapter (Phase 2)

1. Implement `CoreAdapter` in `server/adapters/core_adapter.py` by calling `core.pipeline`.
2. Replace `server/contracts.py` with re-exports from `core.models`.
3. Run with `MYTOOL_UI_ADAPTER=core` (and `ANTHROPIC_API_KEY` set).

See `docs/ui-core-requests.md` for what the UI needs from the core.

## 11. Quality checks

```bash
# from server/
../.venv/bin/ruff check . && ../.venv/bin/ruff format --check .
../.venv/bin/mypy .
../.venv/bin/python -m pytest

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

- Category chips: `HATA` = bug, `PERF` = perf, `STİL` = style (shrink/translate are not shown for analyze).
  Severity chips use *Ciddi / Uyarı / Bilgi* so that "Hata" is not ambiguous.
- ⚠ (skipped) suggestions are listed with their explanation and diff but cannot be selected or applied.
- With "Doğrulama yapma" on, every suggestion is ⚠ skipped, so nothing can be applied in that run.
- Mock demo states: `MYTOOL_UI_MOCK_SCENARIO=empty|error|no_key python -m server`.
