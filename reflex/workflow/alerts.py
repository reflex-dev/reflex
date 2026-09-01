"""Page an operator when a run needs one.

Metrics and traces answer "what happened"; an alert answers "look now". The
conditions an operator pages on are a run that failed, timed out, or needs
attention, a schedule that dropped occurrences, and a delivery that became a
dead letter. Each becomes one JSON POST to ``REFLEX_WORKFLOW_ALERT_WEBHOOK``.
The payload carries a ``text`` line beside its structured fields, so a Slack
(or Slack-compatible) incoming webhook accepts it unchanged and a custom
receiver reads the fields instead.

Delivery never touches the kernel's path: observer callbacks enqueue, and a
background task posts with retries, giving up with a warning. An unreachable
sink costs alerts, never runs, and a run's outcome is never conditional on
its alert having been delivered.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import time
from collections import deque
from typing import TYPE_CHECKING, Any, Final

from reflex_base.utils import console

from reflex.workflow.kernel import WorkflowObserver
from reflex.workflow.records import HistoryEventType

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable, Sequence

    import httpx

ALERT_WEBHOOK_ENV: Final = "REFLEX_WORKFLOW_ALERT_WEBHOOK"
ALERT_KINDS_ENV: Final = "REFLEX_WORKFLOW_ALERT_KINDS"

ALERT_KINDS: Final = frozenset({
    "run_failed",
    "run_timed_out",
    "run_needs_attention",
    "schedule_skipped",
    "dead_letter",
})

_RUN_KINDS: Final[dict[HistoryEventType, tuple[str, str]]] = {
    HistoryEventType.RUN_FAILED: ("run_failed", "failed"),
    HistoryEventType.RUN_TIMED_OUT: ("run_timed_out", "timed out"),
    HistoryEventType.RUN_NEEDS_ATTENTION: ("run_needs_attention", "needs attention"),
}

DEFAULT_TIMEOUT: Final = 5.0
DEFAULT_RETRY_DELAYS: Final = (1.0, 4.0)
DEFAULT_MAX_QUEUED: Final = 1000


def _plural(count: int, noun: str, plural: str) -> str:
    """Spell a counted noun.

    Args:
        count: How many.
        noun: The singular form.
        plural: The plural form.

    Returns:
        The count followed by the fitting form.
    """
    return f"{count} {noun if count == 1 else plural}"


class AlertObserver(WorkflowObserver):
    """Post page-worthy transitions to a webhook, off the kernel's path.

    Installed automatically by every runtime when
    ``REFLEX_WORKFLOW_ALERT_WEBHOOK`` is set (``from_env``), or explicitly::

        app = rx.App(workflow_observer=AlertObserver("https://hooks.slack.com/..."))

    Attributes:
        url: Where alerts are posted.
        kinds: The alert kinds this observer sends.
        sent: Alerts delivered.
        failed: Alerts given up on after every attempt failed.
        dropped: Alerts discarded because the queue was full.
    """

    def __init__(
        self,
        url: str,
        *,
        kinds: Iterable[str] | None = None,
        send: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_delays: Sequence[float] = DEFAULT_RETRY_DELAYS,
        max_queued: int = DEFAULT_MAX_QUEUED,
        clock: Callable[[], float] = time.time,
    ):
        """Configure the sink.

        Args:
            url: The webhook to post alerts to.
            kinds: Alert kinds to send; every kind by default.
            send: Replaces the HTTP post, for tests and custom transports.
            client: The HTTP client to post with; one is created on first use.
            timeout: Seconds to wait on one post.
            retry_delays: Seconds to wait before each retry; the number of
                delays is the number of retries.
            max_queued: Alerts held while the sink is slow; the oldest are
                dropped beyond it.
            clock: Epoch-seconds source stamped on each alert.

        Raises:
            ValueError: If ``kinds`` names an alert kind that does not exist.
        """
        selected = frozenset(kinds) if kinds is not None else ALERT_KINDS
        unknown = selected - ALERT_KINDS
        if unknown:
            msg = (
                f"Unknown alert kinds {sorted(unknown)}; choose from "
                f"{sorted(ALERT_KINDS)}."
            )
            raise ValueError(msg)
        self.url = url
        self.kinds = selected
        self.sent = 0
        self.failed = 0
        self.dropped = 0
        self._send = send or self._post
        self._client = client
        self._timeout = timeout
        self._retry_delays = tuple(retry_delays)
        self._max_queued = max_queued
        self._clock = clock
        self._queue: deque[dict[str, Any]] = deque()
        self._wake: asyncio.Event | None = None
        self._idle: asyncio.Event | None = None
        self._task: asyncio.Task[None] | None = None
        self._overflowing = False

    @classmethod
    def from_env(cls) -> AlertObserver | None:
        """Build the sink the environment configures, if any.

        Returns:
            The observer, or None when no webhook is configured.

        Raises:
            ValueError: If ``REFLEX_WORKFLOW_ALERT_KINDS`` names an unknown kind.
        """
        url = os.environ.get(ALERT_WEBHOOK_ENV, "").strip()
        if not url:
            return None
        raw = os.environ.get(ALERT_KINDS_ENV, "")
        kinds = [kind.strip() for kind in raw.split(",") if kind.strip()]
        return cls(url, kinds=kinds or None)

    def on_event(
        self,
        event_type: HistoryEventType,
        run_id: str,
        workflow_id: str,
        data: dict[str, Any],
    ) -> None:
        """Alert on a run ending in a way an operator must see.

        Args:
            event_type: What happened.
            run_id: The run it happened to.
            workflow_id: That run's workflow identity.
            data: Event payload, carrying the reason or error.
        """
        named = _RUN_KINDS.get(event_type)
        if named is None or named[0] not in self.kinds:
            return
        kind, verb = named
        # A control return records {"reason", "details"}; an exception records
        # {"type", "message", "traceback"}; exhaustion puts the reason on top.
        error = data.get("error")
        reason = None
        if isinstance(error, dict):
            reason = error.get("reason") or error.get("message")
        if reason is None:
            reason = data.get("reason")
        text = f"{workflow_id} run {run_id[:8]} {verb}"
        if reason:
            text = f"{text}: {reason}"
        alert: dict[str, Any] = {
            "workflow_id": workflow_id,
            "run_id": run_id,
            "reason": None if reason is None else str(reason),
        }
        if isinstance(error, dict):
            alert["error"] = {
                key: error[key]
                for key in ("type", "message", "reason", "details")
                if key in error
            }
        self._alert(kind, text, alert)

    def on_schedule_skip(self, schedule_key: str, skipped: int) -> None:
        """Alert on scheduled occurrences that were dropped rather than run.

        Args:
            schedule_key: The schedule that lost occurrences.
            skipped: How many were dropped.
        """
        if "schedule_skipped" not in self.kinds:
            return
        self._alert(
            "schedule_skipped",
            f"schedule {schedule_key} dropped "
            f"{_plural(skipped, 'occurrence', 'occurrences')}",
            {"schedule_key": schedule_key, "count": skipped},
        )

    def on_dead_letter(
        self,
        workflow_id: str | None,
        channel: str | None,
        count: int,
        reason: str,
    ) -> None:
        """Alert on deliveries that can no longer reach a run.

        Args:
            workflow_id: The addressed workflow, when the delivery named one.
            channel: The addressed channel, when the delivery named one.
            count: How many deliveries became dead letters.
            reason: Why: ``undeliverable`` or ``unclaimed``.
        """
        if "dead_letter" not in self.kinds:
            return
        deliveries = _plural(count, "delivery", "deliveries")
        if workflow_id:
            text = (
                f"{deliveries} for {workflow_id}.{channel} became dead letters "
                f"({reason})"
            )
        else:
            text = f"{deliveries} went unclaimed past the TTL and became dead letters"
        self._alert(
            "dead_letter",
            text,
            {
                "workflow_id": workflow_id,
                "channel": channel,
                "count": count,
                "reason": reason,
            },
        )

    async def flush(self, within: float = DEFAULT_TIMEOUT) -> bool:
        """Wait for every queued alert to be delivered or given up on.

        Args:
            within: Seconds to wait.

        Returns:
            Whether the queue drained in time.
        """
        if self._queue and (self._task is None or self._task.done()):
            self._ensure_pump()
        if self._idle is None or self._idle.is_set():
            return True
        try:
            await asyncio.wait_for(self._idle.wait(), within)
        except asyncio.TimeoutError:
            return False
        return True

    async def aclose(self, within: float = DEFAULT_TIMEOUT) -> None:
        """Deliver what is queued, then stop posting.

        Args:
            within: Seconds to give the queue before stopping regardless.
        """
        if not await self.flush(within):
            console.warn(
                f"Stopping with {_plural(len(self._queue) + 1, 'alert', 'alerts')} "
                f"still undelivered to {self.url}."
            )
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _alert(self, kind: str, text: str, fields: dict[str, Any]) -> None:
        """Queue one alert.

        Args:
            kind: The alert kind.
            text: The human line.
            fields: The structured fields beside it.
        """
        payload = {"kind": kind, "at": self._clock(), "text": text, **fields}
        if len(self._queue) >= self._max_queued:
            self._queue.popleft()
            self.dropped += 1
            if not self._overflowing:
                self._overflowing = True
                console.warn(
                    f"Alert queue is full ({self._max_queued}); dropping the "
                    f"oldest alerts until {self.url} catches up."
                )
        self._queue.append(payload)
        self._ensure_pump()

    def _ensure_pump(self) -> None:
        """Make sure a task is draining the queue on the running loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No loop yet; the queue waits for flush() or the next event on one.
            return
        if self._wake is None or self._idle is None:
            self._wake = asyncio.Event()
            self._idle = asyncio.Event()
        if self._task is None or self._task.done():
            self._task = loop.create_task(self._pump())
        self._idle.clear()
        self._wake.set()

    async def _pump(self) -> None:
        """Deliver queued alerts in order until cancelled."""
        assert self._wake is not None
        assert self._idle is not None
        while True:
            await self._wake.wait()
            self._wake.clear()
            while self._queue:
                await self._deliver(self._queue.popleft())
            self._overflowing = False
            if not self._queue:
                self._idle.set()

    async def _deliver(self, payload: dict[str, Any]) -> None:
        """Post one alert, retrying on failure, and give up with a warning.

        Args:
            payload: The alert.
        """
        last: Exception | None = None
        attempts = 0
        for delay in (*self._retry_delays, None):
            attempts += 1
            try:
                await self._send(payload)
            except Exception as err:
                last = err
                if delay is None:
                    break
                await asyncio.sleep(delay)
            else:
                self.sent += 1
                return
        self.failed += 1
        console.warn(
            f"Alert {payload['kind']!r} could not be delivered to {self.url} "
            f"after {_plural(attempts, 'attempt', 'attempts')}: {last}"
        )

    async def _post(self, payload: dict[str, Any]) -> None:
        """Post one alert over HTTP.

        Args:
            payload: The alert.
        """
        # Imported on the first alert: most processes never send one, and the
        # kernel should not pay for an HTTP client it may never use.
        import httpx

        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        response = await self._client.post(self.url, json=payload)
        response.raise_for_status()
