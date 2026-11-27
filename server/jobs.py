"""In-memory analysis jobs and their Server-Sent Event history.

Each job runs the (synchronous) adapter in a worker thread. Progress events are
marshalled back onto the event loop and appended to an append-only history, so
an SSE client that (re)connects late still receives every event in order.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from server.adapters.base import Adapter
from server.contracts import AnalyzeResult, LLMChoice, ProgressEvent
from server.errors import CANCELLED, INTERNAL, INTERNAL_MESSAGE, AdapterError
from server.notify import TelegramNotifier, error_message, result_message
from server.schemas import ErrorPayload

log = logging.getLogger(__name__)

EventName = Literal["progress", "result", "error"]
JobStatus = Literal["running", "done", "error", "cancelled"]

MAX_JOBS = 20
HEARTBEAT_SECONDS = 15.0


@dataclass(frozen=True)
class SseMessage:
    event: EventName
    data: str

    @property
    def terminal(self) -> bool:
        return self.event != "progress"

    def encode(self) -> str:
        return f"event: {self.event}\ndata: {self.data}\n\n"


@dataclass
class Job:
    id: str
    root: Path
    cancel: threading.Event = field(default_factory=threading.Event)
    events: list[SseMessage] = field(default_factory=list)
    status: JobStatus = "running"
    result: AnalyzeResult | None = None
    applied_ids: set[str] = field(default_factory=set)
    _signal: asyncio.Event = field(default_factory=asyncio.Event)

    def publish(self, message: SseMessage) -> None:
        """Append *message* and wake waiting streams. Event-loop thread only."""
        self.events.append(message)
        self._signal.set()
        self._signal = asyncio.Event()

    async def stream(self) -> AsyncIterator[str]:
        """Yield encoded SSE frames from the start until a terminal event."""
        index = 0
        while True:
            while index < len(self.events):
                message = self.events[index]
                index += 1
                yield message.encode()
                if message.terminal:
                    return
            signal = self._signal
            try:
                await asyncio.wait_for(signal.wait(), timeout=HEARTBEAT_SECONDS)
            except TimeoutError:
                yield ": keep-alive\n\n"


def only_visible_suggestions(result: AnalyzeResult) -> AnalyzeResult:
    """Drop suggestions whose verification failed: they are never shown."""
    visible = [s for s in result.suggestions if s.verification.status != "failed"]
    return result.model_copy(update={"suggestions": visible})


class JobStore:
    def __init__(self, adapter: Adapter, notifier: TelegramNotifier | None = None) -> None:
        self.adapter = adapter
        self.notifier = notifier or TelegramNotifier()
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._tasks: set[asyncio.Task[None]] = set()

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def cancel_all(self) -> None:
        for job in self._jobs.values():
            job.cancel.set()

    def start(self, root: Path, *, verify: bool, llm: LLMChoice | None = None) -> Job:
        job = Job(id=uuid.uuid4().hex, root=root)
        self._remember(job)
        task = asyncio.create_task(self._run(job, verify, llm))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    def _remember(self, job: Job) -> None:
        self._jobs[job.id] = job
        while len(self._jobs) > MAX_JOBS:
            _, old = self._jobs.popitem(last=False)
            old.cancel.set()

    async def _run(self, job: Job, verify: bool, llm: LLMChoice | None) -> None:
        loop = asyncio.get_running_loop()

        def on_progress(event: ProgressEvent) -> None:
            message = SseMessage("progress", event.model_dump_json())
            loop.call_soon_threadsafe(job.publish, message)

        try:
            raw = await asyncio.to_thread(
                self.adapter.analyze,
                job.root,
                verify=verify,
                on_progress=on_progress,
                cancel=job.cancel,
                llm=llm,
            )
        except AdapterError as err:
            self._finish_with_error(job, err.payload())
        except Exception:
            log.exception("analysis job %s crashed", job.id)
            self._finish_with_error(job, ErrorPayload(code=INTERNAL, message=INTERNAL_MESSAGE))
        else:
            await asyncio.sleep(0)  # let queued progress callbacks land first
            job.result = only_visible_suggestions(raw)
            job.status = "done"
            job.publish(SseMessage("result", job.result.model_dump_json()))
            self._notify(result_message(job.root, job.result))

    def _finish_with_error(self, job: Job, payload: ErrorPayload) -> None:
        job.status = "cancelled" if payload.code == CANCELLED else "error"
        job.publish(SseMessage("error", payload.model_dump_json()))
        if job.status == "error":
            self._notify(error_message(job.root, payload))

    def notify(self, text: str) -> None:
        """Public: other routes (apply, chat) also report to Telegram."""
        self._notify(text)

    def _notify(self, text: str) -> None:
        """Send in the background; the analysis result never waits for Telegram."""
        if not self.notifier.configured:
            return
        task = asyncio.create_task(self._send(text))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _send(self, text: str) -> None:
        await self.notifier.send(text)
