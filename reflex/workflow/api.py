"""An HTTP surface for starting and reading runs from outside the process.

The engine is reachable in Python by importing the workflow class. That is
the right answer for a Reflex app or a worker, and the wrong one for the
service that has the business event: a Django view, a Go service, a cron box,
anything that should not import your workflow package to say "this happened".

These endpoints give those callers the two verbs they need -- start a run,
read a run -- over HTTP, with the same admission semantics as an in-process
start, including idempotency keys. Every route requires a bearer token, and
without one configured the surface is not mounted at all: an unauthenticated
endpoint that starts arbitrary workflows is not something to leave on by
accident.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
from typing import TYPE_CHECKING, Any, Final

from starlette.responses import JSONResponse, PlainTextResponse

from reflex.workflow.definition import unbound_params
from reflex.workflow.records import attempts_made
from reflex.workflow.validation import mistyped_args

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from starlette.requests import Request
    from starlette.responses import Response

    from reflex.workflow.runtime import WorkflowRuntime

logger = logging.getLogger(__name__)

TOKEN_ENV: Final = "REFLEX_WORKFLOW_API_TOKEN"
START_ROUTE: Final = "/_workflow/api/runs"
RUN_ROUTE: Final = "/_workflow/api/runs/{run_id}"
METRICS_ROUTE: Final = "/_workflow/api/metrics"
MAX_BODY_BYTES: Final = 1_048_576


def api_token() -> str | None:
    """Read the bearer token the API requires, if one is configured.

    Returns:
        The token, or None when the API should stay unmounted.
    """
    return os.environ.get(TOKEN_ENV) or None


if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    AuthorizeFn = Callable[[Request], JSONResponse | None]
else:
    AuthorizeFn = object


def _refusal(request: Request, token: str | AuthorizeFn) -> JSONResponse | None:
    """Authorize a request against a token or a scope authorizer.

    Args:
        request: The incoming request.
        token: The single bearer token, or an authorizer returning a refusal
            response (401/403) or None to admit.

    Returns:
        The refusal to send, or None when the request may proceed.
    """
    if callable(token):
        return token(request)
    if _authorized(request, token):
        return None
    return JSONResponse({"error": "unauthorized"}, status_code=401)


def _authorized(request: Request, token: str) -> bool:
    """Check a request's bearer token in constant time.

    Args:
        request: The incoming request.
        token: The configured token.

    Returns:
        True when the request carries the right token.
    """
    header = request.headers.get("authorization", "")
    scheme, _, presented = header.partition(" ")
    if scheme.lower() != "bearer":
        return False
    return hmac.compare_digest(presented, token)


def start_endpoint(
    runtime: WorkflowRuntime, token: str | AuthorizeFn
) -> Callable[[Request], Coroutine[Any, Any, JSONResponse]]:
    """Build the endpoint that starts a run.

    Args:
        runtime: The runtime owning the workflows.
        token: The bearer token every caller must present.

    Returns:
        The endpoint callable.
    """

    async def endpoint(request: Request) -> JSONResponse:
        """Start a run from a JSON body.

        Args:
            request: The incoming request.

        Returns:
            The admission result, or an error.
        """
        refused = _refusal(request, token)
        if refused is not None:
            return refused
        body = await request.body()
        if len(body) > MAX_BODY_BYTES:
            return JSONResponse({"error": "payload too large"}, status_code=413)
        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return JSONResponse({"error": "payload is not JSON"}, status_code=400)
        if not isinstance(payload, dict):
            return JSONResponse(
                {"error": "payload must be a JSON object"}, status_code=400
            )

        workflow_id = payload.get("workflow")
        handler_name = payload.get("handler")
        if not isinstance(workflow_id, str) or not isinstance(handler_name, str):
            return JSONResponse(
                {"error": "workflow and handler are required"}, status_code=400
            )
        definition = next(
            (
                candidate
                for candidate in runtime.definitions
                if candidate.workflow_id == workflow_id
            ),
            None,
        )
        if definition is None:
            return JSONResponse({"error": "unknown workflow"}, status_code=404)
        # The stable id is what the run records and what every read surface
        # reports, so it has to be what the write surface accepts; a caller
        # that read `handler: "accept_order"` back must be able to send it.
        # The Python name stays valid so renaming neither breaks callers.
        handler = next(
            (
                candidate
                for candidate in definition.handlers.values()
                if handler_name in (candidate.id, candidate.name)
            ),
            None,
        )
        if handler is None:
            return JSONResponse({"error": "unknown handler"}, status_code=404)
        target = getattr(definition.state_cls, handler.name)

        raw_args = payload.get("args")
        if raw_args is not None and not isinstance(raw_args, dict):
            return JSONResponse(
                {"error": "args must be a JSON object"}, status_code=400
            )
        args = raw_args or {}
        mistyped = mistyped_args(handler, args)
        if mistyped:
            # Admitting a payload the handler's signature refuses creates a
            # run whose first attempt can only raise; the caller gets a 202
            # and a poison run instead of the 400 that names their bug.
            return JSONResponse(
                {"error": f"arguments do not match the handler: {mistyped}"},
                status_code=400,
            )
        missing = sorted(unbound_params(handler, set(args)))
        if missing:
            # Admitting this would create a run that cannot possibly run: the
            # worker would raise TypeError on the first attempt and the caller
            # would have a 202 and a poisoned run id.
            return JSONResponse(
                {"error": f"missing required arguments: {missing}"}, status_code=400
            )
        labels = payload.get("labels")
        try:
            result = await runtime.kernel.start(
                target(**args) if args else target,
                request_key=payload.get("request_key"),
                labels=labels if isinstance(labels, dict) else None,
            )
        except Exception as err:
            # A rejected start is the caller's problem to see, not a 500: the
            # usual cause is a handler that is not a manual root, or args that
            # do not fit it.
            logger.warning(f"Workflow API start refused: {err}")
            return JSONResponse({"error": str(err)}, status_code=400)
        return JSONResponse(
            {"disposition": result.disposition, "run_id": result.run_id},
            status_code=202,
        )

    return endpoint


def run_endpoint(
    runtime: WorkflowRuntime, token: str | AuthorizeFn
) -> Callable[[Request], Coroutine[Any, Any, JSONResponse]]:
    """Build the endpoint that reads one run.

    Args:
        runtime: The runtime owning the runs.
        token: The bearer token every caller must present.

    Returns:
        The endpoint callable.
    """

    async def endpoint(request: Request) -> JSONResponse:
        """Report a run's status, result, and steps.

        Args:
            request: The incoming request.

        Returns:
            The run projection, or an error.
        """
        refused = _refusal(request, token)
        if refused is not None:
            return refused
        run_id = request.path_params.get("run_id", "")
        snapshot = await runtime.kernel.get_run(run_id)
        if snapshot is None:
            return JSONResponse({"error": "unknown run"}, status_code=404)
        return JSONResponse({
            "run_id": snapshot.run_id,
            "workflow": snapshot.workflow_id,
            "status": snapshot.status.value,
            "release": snapshot.release_id,
            "result": snapshot.result,
            "error": snapshot.error,
            "steps": [
                {
                    "ordinal": step.ordinal,
                    "handler": step.handler_id,
                    "status": step.status.value,
                    "attempts": attempts_made(step),
                }
                for step in snapshot.steps
            ],
        })

    return endpoint


def _label(value: str) -> str:
    """Escape a value for a Prometheus label.

    Args:
        value: The raw label value.

    Returns:
        The escaped value, without its surrounding quotes.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render_prometheus(snapshot: dict[str, Any]) -> str:
    """Render counter totals in the Prometheus text exposition format.

    Plain text on purpose: it is what a Prometheus server scrapes, what the
    OpenTelemetry collector's prometheus receiver reads, and what every
    hosted metrics vendor accepts, with no client library and no dependency
    of ours to keep current.

    Args:
        snapshot: A ``MetricsObserver.snapshot()`` result.

    Returns:
        The exposition text, ending in a newline.
    """
    totals: dict[str, int] = snapshot.get("totals", {})
    by_workflow: dict[str, dict[str, int]] = snapshot.get("by_workflow", {})
    names = sorted({
        *totals,
        *(key for counts in by_workflow.values() for key in counts),
    })
    lines: list[str] = []
    for name in names:
        metric = f"reflex_workflow_{name}_total"
        lines.extend((
            f"# TYPE {metric} counter",
            f"{metric} {totals.get(name, 0)}",
        ))
        for workflow_id in sorted(by_workflow):
            count = by_workflow[workflow_id].get(name)
            if count:
                lines.append(f'{metric}{{workflow="{_label(workflow_id)}"}} {count}')
    return "\n".join(lines) + "\n"


def metrics_endpoint(
    runtime: WorkflowRuntime, token: str | AuthorizeFn
) -> Callable[[Request], Coroutine[Any, Any, Response]]:
    """Build the endpoint that exposes this process's counters.

    The counters are per process: each worker reports what it did, and the
    collector sums them. That is what makes a fleet's numbers addable rather
    than a single process's guess about the whole system.

    Args:
        runtime: The runtime whose counters to report.
        token: The bearer token every caller must present.

    Returns:
        The endpoint callable.
    """

    async def endpoint(request: Request) -> Response:  # noqa: RUF029
        """Report the counters as Prometheus text.

        Args:
            request: The incoming request.

        Returns:
            The exposition text, or an error.
        """
        # Reading in-process counters needs no await; the signature is a
        # Starlette endpoint's, not a claim that this does I/O.
        refused = _refusal(request, token)
        if refused is not None:
            return refused
        return PlainTextResponse(
            render_prometheus(runtime.metrics.snapshot()),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return endpoint
