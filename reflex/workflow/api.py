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
import os
from typing import TYPE_CHECKING, Any, Final

from reflex_base.utils import console
from starlette.responses import JSONResponse

from reflex.workflow.records import attempts_made

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from starlette.requests import Request

    from reflex.workflow.runtime import WorkflowRuntime

TOKEN_ENV: Final = "REFLEX_WORKFLOW_API_TOKEN"
START_ROUTE: Final = "/_workflow/api/runs"
RUN_ROUTE: Final = "/_workflow/api/runs/{run_id}"
MAX_BODY_BYTES: Final = 1_048_576


def api_token() -> str | None:
    """Read the bearer token the API requires, if one is configured.

    Returns:
        The token, or None when the API should stay unmounted.
    """
    return os.environ.get(TOKEN_ENV) or None


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
    runtime: WorkflowRuntime, token: str
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
        if not _authorized(request, token):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
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
        target = getattr(definition.state_cls, handler_name, None)
        if target is None:
            return JSONResponse({"error": "unknown handler"}, status_code=404)

        args = payload.get("args") or {}
        if not isinstance(args, dict):
            return JSONResponse(
                {"error": "args must be a JSON object"}, status_code=400
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
            console.warn(f"Workflow API start refused: {err}")
            return JSONResponse({"error": str(err)}, status_code=400)
        return JSONResponse(
            {"disposition": result.disposition, "run_id": result.run_id},
            status_code=202,
        )

    return endpoint


def run_endpoint(
    runtime: WorkflowRuntime, token: str
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
        if not _authorized(request, token):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        run_id = request.path_params.get("run_id", "")
        snapshot = await runtime.kernel.get_run(run_id)
        if snapshot is None:
            return JSONResponse({"error": "unknown run"}, status_code=404)
        return JSONResponse({
            "run_id": snapshot.run_id,
            "workflow": snapshot.workflow_id,
            "status": snapshot.status.value,
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
