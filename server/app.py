"""FastAPI application: HTTP API for the mytool UI plus the built frontend."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from mytool.core.pricing import PRICES_PER_MTOK
from starlette.middleware.trustedhost import TrustedHostMiddleware

from server import browse, chat, native, places
from server.adapters import adapter_from_env
from server.adapters.base import Adapter
from server.contracts import LLMChoice, Suggestion
from server.errors import INTERNAL, INTERNAL_MESSAGE, UserFacingError
from server.history import HistoryEntry, HistoryStore, read_text
from server.jobs import Job, JobStore
from server.notify import TelegramNotifier, applied_message
from server.schemas import (
    AnalyzeRequest,
    AnalyzeStarted,
    ApplyRequest,
    ApplyResponse,
    BrowseResponse,
    CloneRequest,
    ErrorPayload,
    HealthResponse,
    ModelInfo,
    ModelsResponse,
    PickRequest,
    PickResponse,
    Place,
)

log = logging.getLogger(__name__)

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
DEV_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]
DEFAULT_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def create_app(
    adapter: Adapter | None = None,
    dist_dir: Path | None = None,
    *,
    history: HistoryStore | None = None,
    notifier: TelegramNotifier | None = None,
    chat_llm: chat.LLMFactory = chat.default_llm,
) -> FastAPI:
    store = JobStore(adapter or adapter_from_env(), notifier)
    changes = history or HistoryStore()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        _quiet_connection_resets(asyncio.get_running_loop())
        yield
        store.cancel_all()  # stop worker threads on shutdown

    app = FastAPI(title="mytool UI", lifespan=lifespan, docs_url=None, redoc_url=None)
    _install_middleware(app)
    _install_error_handlers(app)
    _install_routes(app, store, changes)
    _install_chat_routes(app, store, changes, chat_llm)
    _mount_frontend(app, dist_dir or Path(os.environ.get("MYTOOL_UI_DIST", DEFAULT_DIST)))
    return app


def _quiet_connection_resets(loop: asyncio.AbstractEventLoop) -> None:
    """Drop the traceback Windows' Proactor loop prints when a browser closes a socket.

    Closing a tab (or a finished SSE stream) resets the connection; asyncio then
    logs "ConnectionResetError: [WinError 10054]" from its own cleanup callback.
    The server is fine, so only that case is silenced; everything else is logged.
    """
    previous = loop.get_exception_handler()

    def handler(lp: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
        if isinstance(context.get("exception"), ConnectionResetError):
            return
        if previous is not None:
            previous(lp, context)
        else:
            lp.default_exception_handler(context)

    loop.set_exception_handler(handler)


# --------------------------------------------------------------------------- middleware


def _install_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
    app.middleware("http")(_require_json_posts)


async def _require_json_posts(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Reject non-JSON POSTs so cross-site form posts cannot reach the API."""
    if request.method == "POST" and request.url.path.startswith("/api/"):
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            payload = ErrorPayload(code="unsupported_media_type", message="JSON bekleniyor.")
            return JSONResponse(payload.model_dump(), status_code=415)
    return await call_next(request)


def _install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(UserFacingError)
    async def user_facing(_: Request, err: UserFacingError) -> JSONResponse:
        return JSONResponse(err.payload().model_dump(), status_code=err.status_code)

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, __: RequestValidationError) -> JSONResponse:
        payload = ErrorPayload(code="invalid_request", message="Geçersiz istek.")
        return JSONResponse(payload.model_dump(), status_code=422)

    @app.exception_handler(Exception)
    async def crashed(_: Request, err: Exception) -> JSONResponse:
        log.exception("unhandled error", exc_info=err)
        payload = ErrorPayload(code=INTERNAL, message=INTERNAL_MESSAGE)
        return JSONResponse(payload.model_dump(), status_code=500)


# --------------------------------------------------------------------------- routes


def _install_routes(app: FastAPI, store: JobStore, changes: HistoryStore) -> None:
    @app.get("/api/health")
    async def health() -> HealthResponse:
        adapter = store.adapter
        return HealthResponse(
            status="ok",
            adapter=adapter.name,
            api_key_configured=adapter.api_key_configured(),
            telegram_configured=store.notifier.configured,
        )

    @app.post("/api/analyze")
    async def analyze(body: AnalyzeRequest) -> AnalyzeStarted:
        root = browse.resolve_target(body.path)  # a folder or a single file
        job = store.start(root, verify=body.verify, llm=_checked_llm(body.llm))
        return AnalyzeStarted(job_id=job.id)

    @app.get("/api/analyze/{job_id}/events")
    async def events(job_id: str) -> StreamingResponse:
        job = _require_job(store, job_id)
        return StreamingResponse(job.stream(), media_type="text/event-stream", headers=SSE_HEADERS)

    @app.post("/api/analyze/{job_id}/cancel", status_code=204)
    async def cancel(job_id: str) -> Response:
        _require_job(store, job_id).cancel.set()
        return Response(status_code=204)

    @app.get("/api/browse")
    async def browse_dir(path: str | None = None, show_hidden: bool = False) -> BrowseResponse:
        return browse.list_dir(browse.resolve_dir(path), show_hidden=show_hidden)

    @app.get("/api/places")
    async def quick_access() -> list[Place]:
        return places.places()

    @app.post("/api/apply")
    async def apply(body: ApplyRequest) -> ApplyResponse:
        job = _require_job(store, body.job_id)
        chosen = select_applicable(job, body.suggestion_ids)
        before = _current_texts(job.root, chosen)
        outcome = await asyncio.to_thread(store.adapter.apply, job.root, chosen)
        job.applied_ids.update(outcome.applied_ids)
        applied = [s for s in chosen if s.id in set(outcome.applied_ids)]
        entry = await asyncio.to_thread(
            changes.record, job.root, before, [s.explanation for s in applied]
        )
        if outcome.applied_ids:
            store.notify(applied_message(job.root, outcome.changed_files, len(outcome.applied_ids)))
        return ApplyResponse(**outcome.model_dump(), history_id=entry.id if entry else None)

    @app.get("/api/models")
    async def models() -> ModelsResponse:
        from mytool.core.config import load_config

        cfg = load_config()
        return ModelsResponse(
            models=[
                ModelInfo(
                    id=m,
                    **MODEL_INFO[m],
                    input_per_mtok=PRICES_PER_MTOK[m][0],
                    output_per_mtok=PRICES_PER_MTOK[m][1],
                )
                for m in MODEL_INFO
            ],
            default_model=cfg.model if cfg.model in MODEL_INFO else "claude-sonnet-5-5",
            default_effort=cfg.effort,
        )

    @app.post("/api/pick")
    async def pick(body: PickRequest) -> PickResponse:
        paths = await asyncio.to_thread(native.pick_paths, body.kind, body.initial_dir)
        return PickResponse(paths=paths)

    @app.post("/api/clone")
    async def clone(body: CloneRequest) -> PickResponse:
        path = await asyncio.to_thread(native.clone_github, body.url)
        return PickResponse(paths=[str(path)])

    @app.get("/api/history")
    async def history_list() -> list[HistoryEntry]:
        return changes.entries()

    @app.post("/api/history/{entry_id}/undo")
    async def history_undo(entry_id: str) -> HistoryEntry:
        return await asyncio.to_thread(changes.undo, entry_id)

    @app.post("/api/notify/test")
    async def notify_test() -> dict[str, bool]:
        if not store.notifier.configured:
            raise UserFacingError(
                "telegram_not_configured",
                "Telegram ayarlı değil: TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID tanımlayın.",
            )
        sent = await store.notifier.send("🔔 Verifix: Telegram bildirimleri çalışıyor.")
        return {"sent": sent}


def _install_chat_routes(
    app: FastAPI, store: JobStore, changes: HistoryStore, llm_factory: chat.LLMFactory
) -> None:
    @app.post("/api/chat")
    async def chat_answer(body: chat.ChatRequest) -> chat.ChatResponse:
        if not store.adapter.api_key_configured() or store.adapter.name == "mock":
            raise UserFacingError(
                "api_key_missing",
                "Sohbet için ANTHROPIC_API_KEY tanımlı olmalı ve sunucu core modunda çalışmalı.",
            )
        return await asyncio.to_thread(chat.answer, body, llm_factory)

    @app.post("/api/chat/apply")
    async def chat_apply(body: chat.ChatApplyRequest) -> ApplyResponse:
        root, target = chat.resolve_file(body.path, body.file)
        text = chat.read_source(target)
        new_text, problem = chat.check_edit(text, target, body.original, body.replacement)
        if problem:
            raise UserFacingError("apply_failed", problem, 409)
        target.write_text(new_text, encoding="utf-8")
        store.notify(applied_message(root, [body.file], 1, body.explanation))
        entry = await asyncio.to_thread(
            changes.record, root, {target: text}, [body.explanation or "Sohbetten değişiklik"]
        )
        return ApplyResponse(
            applied_ids=[],
            changed_files=[body.file],
            backup_path="",
            history_id=entry.id if entry else None,
        )


MODEL_INFO: dict[str, dict[str, str]] = {
    "claude-opus-5-5": {"name": "Opus 5.5", "note": "En güçlü; zor hatalar ve büyük değişiklikler"},
    "claude-sonnet-5-5": {"name": "Sonnet 5.5", "note": "Dengeli; günlük iş için önerilen"},
    "claude-haiku-5-5": {"name": "Haiku 5.5", "note": "En hızlı ve en ucuz; basit düzeltmeler"},
}


def _checked_llm(choice: LLMChoice | None) -> LLMChoice | None:
    if choice is not None and choice.model not in MODEL_INFO:
        raise UserFacingError("invalid_model", f"Bilinmeyen model: {choice.model}")
    return choice


def _current_texts(root: Path, suggestions: list[Suggestion]) -> dict[Path, str]:
    """Text of every file the suggestions touch, read before they are applied."""
    base = root if root.is_dir() else root.parent
    texts: dict[Path, str] = {}
    for suggestion in suggestions:
        path = (base / suggestion.patch.file).resolve()
        text = read_text(path)
        if text is not None:
            texts[path] = text
    return texts


def _require_job(store: JobStore, job_id: str) -> Job:
    job = store.get(job_id)
    if job is None:
        raise UserFacingError("job_not_found", "Analiz bulunamadı; yeniden başlatın.", 404)
    return job


def select_applicable(job: Job, suggestion_ids: list[str]) -> list[Suggestion]:
    """Return the requested suggestions, or raise if any is not applicable.

    Only suggestions whose verification *passed* may be applied; the request is
    rejected as a whole otherwise so nothing is applied by surprise.
    """
    if job.result is None:
        raise UserFacingError("job_not_finished", "Analiz henüz tamamlanmadı.", 409)
    by_id = {s.id: s for s in job.result.suggestions}
    wanted = list(dict.fromkeys(suggestion_ids))
    if unknown := [i for i in wanted if i not in by_id]:
        raise UserFacingError("unknown_suggestion", f"Bilinmeyen öneri: {', '.join(unknown)}")
    if unverified := [i for i in wanted if by_id[i].verification.status != "passed"]:
        raise UserFacingError(
            "not_verified",
            f"Yalnızca doğrulaması geçen öneriler uygulanabilir: {', '.join(unverified)}",
        )
    if again := [i for i in wanted if i in job.applied_ids]:
        raise UserFacingError("already_applied", f"Zaten uygulandı: {', '.join(again)}", 409)
    return [by_id[i] for i in wanted]


# --------------------------------------------------------------------------- frontend


MISSING_BUILD_PAGE = """<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><title>Verifix</title>
<style>body{background:#0b0f17;color:#e2e8f0;font:15px/1.6 system-ui,sans-serif;
display:grid;place-items:center;height:100vh;margin:0}main{max-width:560px;padding:24px}
code,pre{font-family:ui-monospace,Menlo,Consolas,monospace;background:#131822;
border:1px solid #1f2937;border-radius:10px}code{padding:1px 5px}pre{padding:12px}
h1{font-size:18px}p{color:#94a3b8}</style></head><body><main>
<h1>Arayüz henüz derlenmemiş</h1>
<p>Sunucu çalışıyor ama <code>web/dist</code> bulunamadı. Bir kez derleyip sunucuyu
yeniden başlatın:</p>
<pre>cd web
npm ci
npm run build
cd ..
python -m server</pre>
<p>Geliştirme modu için ikinci terminalde <code>cd web &amp;&amp; npm run dev</code> çalıştırıp
<code>http://127.0.0.1:5173</code> adresini açın.</p>
</main></body></html>"""


def _mount_frontend(app: FastAPI, dist_dir: Path) -> None:
    if (dist_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=dist_dir, html=True), name="frontend")
        return

    @app.get("/", include_in_schema=False)
    async def missing_build() -> HTMLResponse:
        return HTMLResponse(MISSING_BUILD_PAGE)
