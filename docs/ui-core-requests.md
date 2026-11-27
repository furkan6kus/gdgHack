# UI → core requests

Requests from the UI work to the `core/` owners. The UI never edits `core/` or
`cli/`; it talks to the core only through `server/adapters/core_adapter.py`.
Everything below is a proposal: the exact names are yours to pick. Tell us the
final signatures and we adapt the adapter.

Status legend: 🟥 blocking for UI Phase 2 · 🟨 strongly wanted · 🟩 nice to have

---

## 1. 🟥 Progress reporting from `core.pipeline` (core cannot print)

The UI shows a live stage list, a `current/total` bar and log lines, streamed
over SSE. Since core never prints, please let the pipeline report progress.

Either a callback:

```python
def analyze(
    root: Path,
    *,
    verify: bool = True,
    on_progress: Callable[[ProgressEvent], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> AnalyzeResult: ...
```

or a generator that yields `ProgressEvent`s and returns the result
(`Generator[ProgressEvent, None, AnalyzeResult]`). We prefer the callback, because the CLI can
pass a `rich` progress updater and the server a thread-safe queue push.

Expected events (this is what the mock emits today, see `server/adapters/mock.py`):

| stage | when | current/total |
|---|---|---|
| `parsing` | per file | file index / file count |
| `static_analysis` | analyzer start, then "N findings" | – |
| `llm` | per finding sent to the LLM | i / n |
| `verify` | per suggestion verified | i / n |
| `done` | once at the end | – |

- `message` should be short and user-readable. The UI is Turkish; English is fine for now.
- The callback is called from the worker thread that runs the pipeline. The server
  marshals the events onto the event loop, so core does not need to care about threads.

## 2. 🟥 `verify` flag

The home screen has a **"Doğrulama yapma"** (don't verify) toggle, because
verification runs the user's tests on their machine. Please accept
`verify: bool` in the pipeline. When it is `False`, return every suggestion with
`VerificationResult(status="skipped", detail="…disabled by user…", duration_ms=0)`.

## 3. 🟥 Cancellation

The analyzing screen has a cancel button. Please check `should_cancel()` between
units of work (per file, per LLM call, per verification) and stop early by raising
a dedicated exception, e.g. `core.errors.Cancelled`. The adapter maps it to the
UI's `cancelled` state. Make sure an in-flight test subprocess and its temp dir
are cleaned up.

## 4. 🟥 Apply API with backup

```python
def apply_suggestions(root: Path, suggestions: list[Suggestion]) -> ApplyOutcome:
    """Back up affected files into <root>/.mytool/backup/<timestamp>/, then apply."""
# ApplyOutcome: applied_ids: list[str], changed_files: list[str], backup_path: str
```

- The server only passes suggestions whose `verification.status == "passed"`,
  and it already rejects every other request. Core should still re-check this
  (defence in depth).
- Several suggestions may touch the same file, so apply them in one pass per file. If an
  `original_text` no longer matches the file on disk (the user edited the file meanwhile),
  fail that suggestion clearly instead of guessing.
- Returning `backup_path` lets the UI show where the backup went.

## 5. 🟥 Typed, user-safe errors

The UI never shows stack traces. Please raise errors with a stable `code` and a
human message, e.g. `core.errors.MytoolError(code: str, message: str)`. Codes
the UI already handles:

| code | meaning |
|---|---|
| `api_key_missing` | no `ANTHROPIC_API_KEY` |
| `analyzer_failed` | ruff missing or crashed |
| `cancelled` | cancellation acknowledged |

Unknown exceptions are logged server-side and shown as a generic message.

## 6. 🟨 API key presence check without a call

`core.config.api_key_configured() -> bool` (presence only, never the value). The
home screen uses it to show the "API anahtarı eksik" state *before* the user
starts a run.

## 7. 🟨 Models: `core/models.py`

The UI mirrors the spec in `server/contracts.py`, which is marked TEMPORARY. Once
`core/models.py` lands, we delete it and import from core. Please include:

- `Finding`, `Patch`, `VerificationResult`, `Suggestion`, `ProgressEvent` exactly
  as in the spec.
- The UI-level result needs `root`, a per-file summary (`path`, `line_count`, finding
  counts by severity) and `token_usage` (`input_tokens`, `output_tokens`). If core's
  `AnalyzeResult` doesn't carry these, either add them or tell us and the adapter will
  compute the file summary itself.
- `Patch.original_text` and `new_text`: the UI shows them in a side-by-side diff.
  Function-level snippets are ideal. Whole files also work but are noisier.
- Pydantic v2 models only, JSON-serialisable (no `Path` objects inside, or use
  `str` serialisation).

## 8. 🟩 Failed suggestions

Spec: failed suggestions are never shown. The server strips them already
(`server/jobs.py`), so core may return them (useful for CLI debug output) or drop
them. Either works.

## 9. 🟩 Thread safety

The server runs one pipeline call per job in a worker thread, and two jobs may
overlap if the user starts a new analysis right after cancelling. Please avoid
module-level mutable state in the pipeline (shared clients are fine if they are
thread-safe; the Anthropic SDK client is).

## 10. 🟨 Short title on `Suggestion` + single-file analysis

- **Title.** Result rows show a short, human title instead of the raw analyzer
  message (ruff messages are English, the UI is Turkish). The UI reads an optional
  `Suggestion.title: str | None` (≤ ~70 chars, same language as `explanation`). It
  has already been added to the temporary `server/contracts.py`. Ask the LLM for it
  in the same call that produces the explanation. If it is missing, the UI falls
  back to `Finding.message`.
- **Single file.** The folder picker can now pick a single file as well as a folder.
  `POST /api/analyze` passes that path through unchanged. Please let `analyze(root)`
  accept a file path (ruff accepts both). Backups for a single file go to
  `<file's folder>/.mytool/backup/`.
