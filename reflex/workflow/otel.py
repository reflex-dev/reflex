"""Forward workflow activity to OpenTelemetry.

Install with ``pip install opentelemetry-api opentelemetry-sdk`` -- this is
never a hard dependency of Reflex, and importing this module without it says
so plainly instead of failing somewhere inside a callback.

**What is traced, and what deliberately is not.** A span is an in-process,
time-bounded thing. A durable run is neither: it can wait a day, cross a
restart, and execute its steps on different machines. Modelling one run as
one span would mean holding a span open across processes, which OpenTelemetry
cannot do and no backend would render usefully.

So the span here is *one attempt* -- claim to commit -- which really is
bounded and really does happen in one process. Every span carries
``workflow.run_id``, so "show me everything that happened to this run" is a
search by attribute across however many days and processes it took, rather
than a single trace. Steps that never ran (a run cancelled while waiting)
produce no spans, because nothing executed to time.

Counters mirror :class:`~reflex.workflow.kernel.MetricsObserver` exactly,
sharing its event-to-name mapping so the two exporters can never drift into
reporting different numbers for the same deployment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from reflex.workflow.kernel import MetricsObserver, WorkflowObserver
from reflex.workflow.records import HistoryEventType

if TYPE_CHECKING:
    from collections.abc import Mapping

INSTRUMENTATION_NAME: Final = "reflex.workflow"

_ATTEMPT_ENDINGS: Final[dict[HistoryEventType, str]] = {
    HistoryEventType.ATTEMPT_SUCCEEDED: "succeeded",
    HistoryEventType.ATTEMPT_FAILED: "failed",
    HistoryEventType.ATTEMPT_TIMED_OUT: "timed_out",
    HistoryEventType.ATTEMPT_CANCELLED: "cancelled",
    HistoryEventType.ATTEMPT_ABANDONED: "abandoned",
}

_OK_ENDINGS: Final = frozenset({"succeeded"})

MAX_OPEN_SPANS: Final = 4096


def _require_opentelemetry():
    """Import OpenTelemetry, explaining the install if it is absent.

    Returns:
        The ``trace``, ``metrics``, and ``Status``/``StatusCode`` handles.

    Raises:
        ImportError: If OpenTelemetry is not installed.
    """
    try:
        from opentelemetry import metrics, trace
        from opentelemetry.trace import Status, StatusCode
    except ImportError as error:
        msg = (
            "OpenTelemetryObserver needs OpenTelemetry, which Reflex does not "
            "install: pip install opentelemetry-api opentelemetry-sdk"
        )
        raise ImportError(msg) from error
    return trace, metrics, Status, StatusCode


class OpenTelemetryObserver(WorkflowObserver):
    """Emit a span per attempt and a counter per transition.

    Install it the same way as any observer::

        app = rx.App(workflow_observer=OpenTelemetryObserver())

    Callbacks never raise: the kernel swallows observer errors by design, and
    an exporter that broke a run would be worse than one that lost a span.
    """

    def __init__(self, *, tracer_provider: Any = None, meter_provider: Any = None):
        """Bind to a tracer and a meter.

        Args:
            tracer_provider: Provider to take the tracer from; the global one
                by default.
            meter_provider: Provider to take the meter from; the global one
                by default.
        """
        trace, metrics, status, status_code = _require_opentelemetry()
        self._status = status
        self._status_code = status_code
        self._tracer = (tracer_provider or trace).get_tracer(INSTRUMENTATION_NAME)
        meter = (meter_provider or metrics).get_meter(INSTRUMENTATION_NAME)
        names = set(MetricsObserver._COUNTED.values())  # pyright: ignore[reportPrivateUsage]
        names.update(("schedule_occurrences_skipped", "deliveries_dead_lettered"))
        self._counters = {
            name: meter.create_counter(f"reflex.workflow.{name}") for name in names
        }
        self._open: dict[tuple[str, Any], Any] = {}

    def on_event(
        self,
        event_type: HistoryEventType,
        run_id: str,
        workflow_id: str,
        data: dict[str, Any],
    ) -> None:
        """Record one transition as a span edge and a counter increment.

        Args:
            event_type: What happened.
            run_id: The run it happened to.
            workflow_id: That run's workflow identity.
            data: Event payload, such as ordinal, handler, attempt, or error.
        """
        self._count(event_type, workflow_id)
        if event_type is HistoryEventType.ATTEMPT_STARTED:
            self._open_span(run_id, workflow_id, data)
            return
        ending = _ATTEMPT_ENDINGS.get(event_type)
        if ending is not None:
            self._close_span(run_id, data, ending)

    def on_schedule_skip(self, schedule_key: str, skipped: int) -> None:
        """Count scheduled occurrences that were dropped rather than run.

        Args:
            schedule_key: The schedule that lost occurrences.
            skipped: How many were dropped.
        """
        self._counters["schedule_occurrences_skipped"].add(
            skipped, {"workflow.schedule_key": schedule_key}
        )

    def on_dead_letter(
        self,
        workflow_id: str | None,
        channel: str | None,
        count: int,
        reason: str,
    ) -> None:
        """Count deliveries that became dead letters.

        Args:
            workflow_id: The addressed workflow, when the delivery named one.
            channel: The addressed channel, when the delivery named one.
            count: How many deliveries became dead letters.
            reason: Why they did.
        """
        self._counters["deliveries_dead_lettered"].add(
            count,
            {
                "workflow.id": workflow_id or "",
                "workflow.channel": channel or "",
                "workflow.reason": reason,
            },
        )

    def _count(self, event_type: HistoryEventType, workflow_id: str) -> None:
        """Add one to the counter this event feeds, if any.

        Args:
            event_type: What happened.
            workflow_id: The workflow it happened in.
        """
        name = MetricsObserver._COUNTED.get(event_type)  # pyright: ignore[reportPrivateUsage]
        counter = self._counters.get(name) if name else None
        if counter is not None:
            counter.add(1, {"workflow.id": workflow_id})

    def _open_span(
        self, run_id: str, workflow_id: str, data: Mapping[str, Any]
    ) -> None:
        """Start a span for an attempt that just began.

        Args:
            run_id: The run being executed.
            workflow_id: That run's workflow identity.
            data: The ``attempt_started`` payload.
        """
        if len(self._open) >= MAX_OPEN_SPANS:
            # An attempt whose ending never arrived -- its worker was killed
            # between the two events. Ending it as unset says "we do not know
            # how this finished", which is true, and keeps the map bounded.
            oldest = next(iter(self._open))
            self._open.pop(oldest).end()
        handler = data.get("handler_id", "?")
        span = self._tracer.start_span(
            f"{workflow_id}.{handler}",
            attributes={
                "workflow.id": workflow_id,
                "workflow.run_id": run_id,
                "workflow.handler_id": handler,
                "workflow.step_ordinal": data.get("ordinal", -1),
                "workflow.attempt": data.get("attempt", 0),
                "workflow.effect": str(data.get("effect", "")),
            },
        )
        self._open[run_id, data.get("ordinal")] = span

    def _close_span(self, run_id: str, data: Mapping[str, Any], ending: str) -> None:
        """Finish the span for an attempt that just ended.

        Args:
            run_id: The run being executed.
            data: The ending event's payload.
            ending: How the attempt ended.
        """
        span = self._open.pop((run_id, data.get("ordinal")), None)
        if span is None:
            return
        span.set_attribute("workflow.attempt_outcome", ending)
        reason = data.get("reason")
        if reason:
            span.set_attribute("workflow.reason", str(reason))
        if ending in _OK_ENDINGS:
            span.set_status(self._status(self._status_code.OK))
        else:
            span.set_status(
                self._status(self._status_code.ERROR, str(reason or ending))
            )
        span.end()
