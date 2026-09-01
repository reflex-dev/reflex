"""The standalone workflow service: ingress, API, and worker in one process.

``reflex workflows serve workflows.py`` runs everything a deployed workflow
needs with no frontend and no ``rx.App``: webhook and approval ingress, the
run HTTP API, the worker loop, and the probes an orchestrator points at.
``--ingress-only`` and ``--worker-only`` split the same process for separate
scaling; both halves keep ``/healthz``, ``/readyz``, and ``/metrics``.

Authorization is scoped. ``REFLEX_WORKFLOW_API_TOKEN`` grants everything, as it
always has; ``REFLEX_WORKFLOW_API_TOKEN_READ``, ``_START``, ``_SIGNAL``, and
``_OPERATE`` each grant exactly one scope, so the credential a dashboard
holds cannot cancel runs and the credential a webhook relay holds cannot
read them. A request with no valid token is a 401; a valid token without
the route's scope is a 403.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
from typing import TYPE_CHECKING, Any, Final

from reflex_base.utils.exceptions import WorkflowDefinitionError, WorkflowRuntimeError
from reflex_base.workflow import ChannelDelivery
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from reflex.workflow.api import (
    MAX_BODY_BYTES,
    TOKEN_ENV,
    metrics_endpoint,
    run_endpoint,
    start_endpoint,
)
from reflex.workflow.records import RunQuery, RunStatus
from reflex.workflow.runtime import _close_store

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from starlette.requests import Request

    from reflex.workflow.runtime import WorkflowRuntime

logger = logging.getLogger(__name__)

SCOPES: Final = ("read", "start", "signal", "operate")
SCOPE_TOKEN_ENVS: Final = {scope: f"{TOKEN_ENV}_{scope.upper()}" for scope in SCOPES}
PRINCIPALS_ENV: Final = f"{TOKEN_ENV}_PRINCIPALS"
"""Binds names to tokens: ``alek=tok1;deploy-bot=tok2``.

A bound token attributes its actions to its principal, so the audit answers
"who" from the credential rather than from a header the caller wrote. Tokens
named here must still be granted scopes by the scope variables above.
"""


def _bearer(request: Request) -> str:
    """Extract the bearer token a request presents.

    Args:
        request: The incoming request.

    Returns:
        The presented token, or an empty string.
    """
    header = request.headers.get("authorization", "")
    scheme, _, credential = header.partition(" ")
    return credential.strip() if scheme.lower() == "bearer" else ""


class ScopedTokens:
    """The service's token-to-scope mapping, read from the environment.

    Attributes:
        grants: Token to granted scopes.
    """

    def __init__(
        self,
        grants: dict[str, frozenset[str]] | None = None,
        principals: dict[str, str] | None = None,
    ):
        """Read every configured token and principal binding.

        Args:
            grants: Explicit token-to-scopes mapping; the environment is read
                when omitted.
            principals: Explicit token-to-name bindings; the environment is
                read when omitted.
        """
        if grants is not None or principals is not None:
            self.grants = dict(grants or {})
            self.principals = dict(principals or {})
            return
        self.grants: dict[str, frozenset[str]] = {}
        self.principals: dict[str, str] = {}
        universal = os.environ.get(TOKEN_ENV)
        if universal:
            self.grants[universal] = frozenset(SCOPES)
        for scope, env in SCOPE_TOKEN_ENVS.items():
            token = os.environ.get(env)
            if token:
                merged = self.grants.get(token, frozenset()) | {scope}
                self.grants[token] = merged
        for binding in filter(None, os.environ.get(PRINCIPALS_ENV, "").split(";")):
            name, _, token = binding.partition("=")
            if name.strip() and token.strip():
                self.principals[token.strip()] = name.strip()

    def scopes_of(self, token: str) -> frozenset[str] | None:
        """Resolve the scopes a raw token grants.

        Args:
            token: The presented token.

        Returns:
            The granted scopes, or None when no configured token matches.
        """
        if not token:
            return None
        for candidate, scopes in self.grants.items():
            # Compared in constant time, every candidate every time, so the
            # comparison count does not leak which token was close.
            if hmac.compare_digest(token, candidate):
                return scopes
        return None

    def principal_of(self, token: str) -> str | None:
        """The name a token is bound to, if any.

        Args:
            token: The presented token.

        Returns:
            The principal name, or None for an anonymous token.
        """
        for candidate, name in self.principals.items():
            if hmac.compare_digest(token, candidate):
                return name
        return None

    def actor_for(self, request: Request) -> str:
        """Who a request acts as, for the run's history.

        The credential wins: a token bound to a principal names that
        principal. Otherwise the caller's ``X-Actor`` claim is recorded as
        given, and failing that ``api`` -- naming the surface beats naming
        nobody.

        Args:
            request: The incoming request.

        Returns:
            The actor to record.
        """
        bound = self.principal_of(_bearer(request))
        if bound is not None:
            return bound
        return request.headers.get("x-actor") or "api"

    def __bool__(self) -> bool:
        """Whether any token is configured.

        Returns:
            True when at least one token exists.
        """
        return bool(self.grants)

    def scopes_for(self, request: Request) -> frozenset[str] | None:
        """Resolve the scopes a request's token grants.

        Args:
            request: The incoming request.

        Returns:
            The granted scopes, or None when no configured token matches.
        """
        return self.scopes_of(_bearer(request))

    def require(self, scope: str) -> Callable[[Request], JSONResponse | None]:
        """Build an authorizer demanding one scope.

        Args:
            scope: The scope the route requires.

        Returns:
            An authorizer returning a refusal response or None to admit.
        """

        def authorize(request: Request) -> JSONResponse | None:
            """Refuse a request without the scope.

            Args:
                request: The incoming request.

            Returns:
                The refusal, or None to admit.
            """
            granted = self.scopes_for(request)
            if granted is None:
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            if scope not in granted:
                return JSONResponse(
                    {"error": f"token lacks the {scope!r} scope"},
                    status_code=403,
                )
            return None

        return authorize


async def _read_json(request: Request) -> tuple[Any, JSONResponse | None]:
    """Read and decode a JSON request body within the size cap.

    Args:
        request: The incoming request.

    Returns:
        The decoded payload and None, or None and the refusal to send.
    """
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        return None, JSONResponse({"error": "payload too large"}, status_code=413)
    try:
        return (json.loads(body) if body else None), None
    except json.JSONDecodeError:
        return None, JSONResponse({"error": "payload is not JSON"}, status_code=400)


def list_runs_endpoint(runtime: WorkflowRuntime, tokens: ScopedTokens):
    """Build the run-listing endpoint.

    Args:
        runtime: The runtime owning the runs.
        tokens: The service's token scopes.

    Returns:
        The endpoint callable.
    """
    authorize = tokens.require("read")

    async def endpoint(request: Request) -> JSONResponse:
        """List runs, newest first, filtered by query parameters.

        Args:
            request: The incoming request.

        Returns:
            The run summaries.
        """
        refused = authorize(request)
        if refused is not None:
            return refused
        params = request.query_params
        raw_statuses = params.getlist("status")
        known = {status.value: status for status in RunStatus}
        unknown = [raw for raw in raw_statuses if raw.upper() not in known]
        if unknown:
            return JSONResponse(
                {"error": f"unknown status {unknown[0]!r}"}, status_code=400
            )
        statuses = [known[raw.upper()] for raw in raw_statuses]
        labels = {
            name.removeprefix("label."): value
            for name, value in params.items()
            if name.startswith("label.")
        }
        try:
            limit = min(int(params.get("limit", "50")), 500)
        except ValueError:
            return JSONResponse({"error": "limit must be an integer"}, 400)
        runs = await runtime.kernel._store.list_runs(  # pyright: ignore[reportPrivateUsage]
            RunQuery(
                workflow_id=params.get("workflow"),
                statuses=tuple(statuses),
                labels=labels or None,
                limit=limit,
            )
        )
        return JSONResponse({
            "runs": [
                {
                    "run_id": run.run_id,
                    "workflow": run.workflow_id,
                    "status": run.status.value,
                    "labels": run.labels or {},
                    "release": run.release_id,
                    "created_at": run.created_at,
                    "updated_at": run.updated_at,
                }
                for run in runs
            ]
        })

    return endpoint


def signal_endpoint(runtime: WorkflowRuntime, tokens: ScopedTokens):
    """Build the endpoint that delivers a signal to a run's channel.

    Args:
        runtime: The runtime owning the runs.
        tokens: The service's token scopes.

    Returns:
        The endpoint callable.
    """
    authorize = tokens.require("signal")

    async def endpoint(request: Request) -> JSONResponse:
        """Deliver the request body to the named channel.

        Args:
            request: The incoming request.

        Returns:
            The delivery disposition, or an error.
        """
        refused = authorize(request)
        if refused is not None:
            return refused
        payload, bad = await _read_json(request)
        if bad is not None:
            return bad
        run_id = request.path_params["run_id"]
        channel = request.path_params["channel"]
        key = request.headers.get("idempotency-key") or request.query_params.get("key")
        try:
            disposition = await runtime.kernel.signal(
                run_id, ChannelDelivery(channel=channel, payload=payload), key=key
            )
        except WorkflowDefinitionError as error:
            # An unknown channel or a payload the channel's model refuses is
            # the sender's bug; the kernel's message names the fix.
            return JSONResponse({"error": str(error)}, status_code=400)
        status = {
            "unknown_run": 404,
            "run_terminal": 409,
            "expired": 409,
        }.get(disposition, 202)
        return JSONResponse({"disposition": disposition}, status_code=status)

    return endpoint


def key_read_endpoint(runtime: WorkflowRuntime, tokens: ScopedTokens):
    """Build the endpoint that reads a run by its business key.

    Args:
        runtime: The runtime owning the runs.
        tokens: The service's token scopes.

    Returns:
        The endpoint callable.
    """
    authorize = tokens.require("read")

    async def endpoint(request: Request) -> JSONResponse:
        """Resolve the key and answer with the run's identity and status.

        Args:
            request: The incoming request.

        Returns:
            The run reference, or 404.
        """
        refused = authorize(request)
        if refused is not None:
            return refused
        workflow_id = request.path_params["workflow_id"]
        request_key = request.path_params["request_key"]
        try:
            run_id = await runtime.kernel.find_by_key(workflow_id, request_key)
        except WorkflowRuntimeError as error:
            return JSONResponse({"error": str(error)}, status_code=404)
        if run_id is None:
            return JSONResponse({"error": "unknown key"}, status_code=404)
        snapshot = await runtime.kernel.get_run(run_id)
        if snapshot is None:
            return JSONResponse({"error": "unknown key"}, status_code=404)
        return JSONResponse({
            "run_id": snapshot.run_id,
            "workflow": snapshot.workflow_id,
            "status": snapshot.status.value,
            "result": snapshot.result,
            "error": snapshot.error,
        })

    return endpoint


def key_signal_endpoint(runtime: WorkflowRuntime, tokens: ScopedTokens):
    """Build the endpoint that signals a run by its business key.

    Args:
        runtime: The runtime owning the runs.
        tokens: The service's token scopes.

    Returns:
        The endpoint callable.
    """
    authorize = tokens.require("signal")

    async def endpoint(request: Request) -> JSONResponse:
        """Deliver the request body to the keyed run's channel.

        Args:
            request: The incoming request.

        Returns:
            The delivery disposition, or an error.
        """
        refused = authorize(request)
        if refused is not None:
            return refused
        payload, bad = await _read_json(request)
        if bad is not None:
            return bad
        key = request.headers.get("idempotency-key") or request.query_params.get("key")
        try:
            disposition = await runtime.kernel.signal_by_key(
                request.path_params["workflow_id"],
                request.path_params["request_key"],
                ChannelDelivery(
                    channel=request.path_params["channel"], payload=payload
                ),
                key=key,
            )
        except WorkflowRuntimeError as error:
            return JSONResponse({"error": str(error)}, status_code=404)
        except WorkflowDefinitionError as error:
            return JSONResponse({"error": str(error)}, status_code=400)
        status = {
            "unknown_key": 404,
            "unknown_run": 404,
            "run_terminal": 409,
            "expired": 409,
        }.get(disposition, 202)
        return JSONResponse({"disposition": disposition}, status_code=status)

    return endpoint


def deadletters_endpoint(runtime: WorkflowRuntime, tokens: ScopedTokens):
    """Build the endpoint that lists correlated webhook deliveries.

    Args:
        runtime: The runtime owning the store.
        tokens: The service's token scopes.

    Returns:
        The endpoint callable.
    """
    authorize = tokens.require("read")

    async def endpoint(request: Request) -> JSONResponse:
        """List deliveries, dead letters by default.

        Args:
            request: The incoming request.

        Returns:
            The delivery rows.
        """
        refused = authorize(request)
        if refused is not None:
            return refused
        from reflex.workflow.records import ParkedStatus

        raw = request.query_params.get("status", "dead")
        if raw == "all":
            chosen = None
        else:
            try:
                chosen = ParkedStatus(raw.upper())
            except ValueError:
                return JSONResponse(
                    {"error": f"unknown status {raw!r}"}, status_code=400
                )
        rows = await runtime.kernel._store.list_parked(status=chosen)  # pyright: ignore[reportPrivateUsage]
        return JSONResponse({
            "deliveries": [
                {
                    "parked_id": row.parked_id,
                    "workflow": row.workflow_id,
                    "channel": row.channel,
                    "correlation_key": row.correlation_key,
                    "status": row.status.value,
                    "reason": row.reason,
                    "run_id": row.run_id,
                    "created_at": row.created_at,
                }
                for row in rows
            ]
        })

    return endpoint


def deadletter_replay_endpoint(runtime: WorkflowRuntime, tokens: ScopedTokens):
    """Build the endpoint that replays one delivery.

    Args:
        runtime: The runtime owning the store.
        tokens: The service's token scopes.

    Returns:
        The endpoint callable.
    """
    authorize = tokens.require("operate")

    async def endpoint(request: Request) -> JSONResponse:
        """Route the delivery again, with the same event-id idempotency.

        Args:
            request: The incoming request.

        Returns:
            The routing outcome.
        """
        refused = authorize(request)
        if refused is not None:
            return refused

        payload, bad = await _read_json(request)

        if bad is not None:
            return bad

        attribution = {"actor": tokens.actor_for(request)}

        if isinstance(payload, dict) and payload.get("reason"):
            attribution["reason"] = str(payload["reason"])
        disposition = await runtime.kernel._store.replay_parked(
            # pyright: ignore[reportPrivateUsage]
            request.path_params["parked_id"],
            runtime.kernel._clock(),  # pyright: ignore[reportPrivateUsage],
            attribution,
        )
        status = {"unknown_key": 404, "dead_letter": 409}.get(disposition, 202)
        return JSONResponse({"disposition": disposition}, status_code=status)

    return endpoint


def audit_endpoint(runtime: WorkflowRuntime, tokens: ScopedTokens):
    """Build the endpoint that lists audited run-less operator actions.

    Args:
        runtime: The runtime owning the store.
        tokens: The service's token scopes.

    Returns:
        The endpoint callable.
    """
    authorize = tokens.require("read")

    async def endpoint(request: Request) -> JSONResponse:
        """List audit entries, newest first.

        Args:
            request: The incoming request.

        Returns:
            The entries.
        """
        refused = authorize(request)
        if refused is not None:
            return refused
        try:
            limit = min(int(request.query_params.get("limit", "50")), 500)
        except ValueError:
            return JSONResponse({"error": "limit must be an integer"}, 400)
        entries = await runtime.kernel._store.list_audit(  # pyright: ignore[reportPrivateUsage]
            action=request.query_params.get("action"), limit=limit
        )
        return JSONResponse({
            "entries": [
                {
                    "audit_id": entry.audit_id,
                    "at": entry.at,
                    "actor": entry.actor,
                    "action": entry.action,
                    "target": entry.target,
                    "detail": entry.detail,
                    "reason": entry.reason,
                }
                for entry in entries
            ]
        })

    return endpoint


def triggers_endpoint(runtime: WorkflowRuntime, tokens: ScopedTokens):
    """Build the endpoint that summarizes what starts each workflow.

    Args:
        runtime: The runtime whose definitions are summarized.
        tokens: The service's token scopes.

    Returns:
        The endpoint callable.
    """
    authorize = tokens.require("read")

    async def endpoint(request: Request) -> JSONResponse:
        """List webhooks, schedules, and manual roots.

        Args:
            request: The incoming request.

        Returns:
            The trigger rows.
        """
        refused = authorize(request)
        if refused is not None:
            return refused
        from reflex.workflow.triggers import describe_triggers, schedule_cursors

        now = runtime.kernel._clock()  # pyright: ignore[reportPrivateUsage]
        cursors = await schedule_cursors(
            runtime.definitions,
            runtime.kernel._store.read_schedule_cursor,  # pyright: ignore[reportPrivateUsage]
        )
        paused = await runtime.kernel._store.paused_schedules()  # pyright: ignore[reportPrivateUsage]
        return JSONResponse({
            "triggers": describe_triggers(runtime.definitions, now, cursors, paused)
        })

    return endpoint


def connections_endpoint(runtime: WorkflowRuntime, tokens: ScopedTokens):
    """Build the endpoint that reports connections and secrets.

    Args:
        runtime: The runtime whose definitions are inspected.
        tokens: The service's token scopes.

    Returns:
        The endpoint callable.
    """
    authorize = tokens.require("read")

    async def endpoint(request: Request) -> JSONResponse:  # noqa: RUF029
        """List every dependency and whether it is satisfied.

        Args:
            request: The incoming request.

        Returns:
            The connection rows; secret values are never included.
        """
        refused = authorize(request)
        if refused is not None:
            return refused
        from reflex.workflow.health import describe_connections

        return JSONResponse({"connections": describe_connections(runtime.definitions)})

    return endpoint


def schedule_toggle_endpoint(
    runtime: WorkflowRuntime, tokens: ScopedTokens, paused: bool
):
    """Build the endpoint that pauses or resumes a schedule.

    Args:
        runtime: The runtime owning the store.
        tokens: The service's token scopes.
        paused: Whether this endpoint pauses (True) or resumes (False).

    Returns:
        The endpoint callable.
    """
    authorize = tokens.require("operate")

    async def endpoint(request: Request) -> JSONResponse:
        """Set the flag, attributed to the caller.

        Args:
            request: The incoming request.

        Returns:
            The new state.
        """
        refused = authorize(request)
        if refused is not None:
            return refused
        payload, bad = await _read_json(request)
        if bad is not None:
            return bad
        attribution = {"actor": tokens.actor_for(request)}
        if isinstance(payload, dict) and payload.get("reason"):
            attribution["reason"] = str(payload["reason"])
        key = request.path_params["key"]
        await runtime.kernel._store.set_schedule_paused(  # pyright: ignore[reportPrivateUsage]
            key,
            paused,
            runtime.kernel._clock(),
            attribution,  # pyright: ignore[reportPrivateUsage]
        )
        return JSONResponse({"key": key, "paused": paused}, status_code=202)

    return endpoint


def operator_endpoint(runtime: WorkflowRuntime, tokens: ScopedTokens, action: str):
    """Build one operator action endpoint.

    Args:
        runtime: The runtime owning the runs.
        tokens: The service's token scopes.
        action: One of ``cancel``, ``retry``, or ``resume``.

    Returns:
        The endpoint callable.
    """
    authorize = tokens.require("operate")

    async def endpoint(request: Request) -> JSONResponse:
        """Apply the operator action to the addressed run.

        Args:
            request: The incoming request.

        Returns:
            Whether the action applied, or an error.
        """
        refused = authorize(request)
        if refused is not None:
            return refused
        run_id = request.path_params["run_id"]
        if await runtime.kernel.get_run(run_id) is None:
            return JSONResponse({"error": "unknown run"}, status_code=404)
        payload, bad = await _read_json(request)
        if bad is not None:
            return bad
        reason = payload.get("reason") if isinstance(payload, dict) else None
        actor = tokens.actor_for(request)
        applied = await getattr(runtime.kernel, action)(
            run_id, actor=actor, reason=reason
        )
        if not applied:
            # The run exists but is not in a state this action accepts --
            # retrying a healthy run, resuming one that is not suspended.
            return JSONResponse(
                {"error": f"run does not accept {action} in its current state"},
                status_code=409,
            )
        return JSONResponse({"applied": True}, status_code=202)

    return endpoint


def health_endpoint():
    """Build the liveness probe.

    Returns:
        The endpoint callable.
    """

    async def endpoint(request: Request) -> JSONResponse:  # noqa: RUF029
        """Answer that the process is up.

        Args:
            request: The incoming request.

        Returns:
            200 always; a dead process does not answer.
        """
        return JSONResponse({"status": "ok"})

    return endpoint


def ready_endpoint(runtime: WorkflowRuntime):
    """Build the readiness probe.

    Args:
        runtime: The runtime whose store must be reachable.

    Returns:
        The endpoint callable.
    """

    async def endpoint(request: Request) -> JSONResponse:
        """Answer whether this process can do useful work right now.

        Args:
            request: The incoming request.

        Returns:
            200 with the store reachable, 503 otherwise.
        """
        try:
            await runtime.kernel._store.epoch_time()  # pyright: ignore[reportPrivateUsage]
        except Exception as error:
            return JSONResponse(
                {"status": "unready", "store": str(error)}, status_code=503
            )
        return JSONResponse({"status": "ready"})

    return endpoint


def openapi_endpoint(runtime: WorkflowRuntime):
    """Build the OpenAPI document endpoint.

    Args:
        runtime: The runtime whose workflows the document describes.

    Returns:
        The endpoint callable.
    """

    async def endpoint(request: Request) -> JSONResponse:  # noqa: RUF029
        """Serve the API description.

        Args:
            request: The incoming request.

        Returns:
            The OpenAPI 3.1 document.
        """
        workflows = sorted(defn.workflow_id for defn in runtime.definitions)
        run_ref = {"$ref": "#/components/schemas/Disposition"}
        document = {
            "openapi": "3.1.0",
            "info": {
                "title": "Reflex Workflows",
                "version": "1",
                "description": (
                    f"Workflow service for: {', '.join(workflows) or 'none'}"
                ),
            },
            "components": {
                "securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}},
                "schemas": {
                    "Disposition": {
                        "type": "object",
                        "properties": {
                            "disposition": {"type": "string"},
                            "run_id": {"type": ["string", "null"]},
                        },
                    }
                },
            },
            "security": [{"bearer": []}],
            "paths": {
                "/runs": {
                    "post": {
                        "summary": "Start a run (scope: start)",
                        "responses": {"202": {"description": "Admitted"}},
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["workflow", "handler"],
                                        "properties": {
                                            "workflow": {"type": "string"},
                                            "handler": {"type": "string"},
                                            "args": {"type": "object"},
                                            "request_key": {"type": "string"},
                                            "labels": {"type": "object"},
                                        },
                                    }
                                }
                            }
                        },
                    },
                    "get": {
                        "summary": "List runs (scope: read)",
                        "responses": {"200": {"description": "Run summaries"}},
                    },
                },
                "/runs/{run_id}": {
                    "get": {
                        "summary": "Read one run (scope: read)",
                        "responses": {
                            "200": {
                                "description": "The run",
                                "content": {"application/json": {"schema": run_ref}},
                            }
                        },
                    }
                },
                "/runs/{run_id}/signals/{channel}": {
                    "post": {
                        "summary": "Deliver a signal (scope: signal)",
                        "responses": {"202": {"description": "Delivered"}},
                    }
                },
                **{
                    f"/runs/{{run_id}}/{action}": {
                        "post": {
                            "summary": f"{action.title()} a run (scope: operate)",
                            "responses": {"202": {"description": "Applied"}},
                        }
                    }
                    for action in ("cancel", "retry", "resume")
                },
                "/workflows/{workflow_id}/keys/{request_key}": {
                    "get": {
                        "summary": "Read a run by business key (scope: read)",
                        "responses": {"200": {"description": "The run"}},
                    }
                },
                "/workflows/{workflow_id}/keys/{request_key}/signals/{channel}": {
                    "post": {
                        "summary": ("Deliver a signal by business key (scope: signal)"),
                        "responses": {"202": {"description": "Delivered"}},
                    }
                },
                "/deadletters": {
                    "get": {
                        "summary": ("List correlated webhook deliveries (scope: read)"),
                        "responses": {"200": {"description": "The deliveries"}},
                    }
                },
                "/deadletters/{parked_id}/replay": {
                    "post": {
                        "summary": "Replay a delivery (scope: operate)",
                        "responses": {"202": {"description": "Routed"}},
                    }
                },
                "/audit": {
                    "get": {
                        "summary": (
                            "List audited run-less operator actions (scope: read)"
                        ),
                        "responses": {"200": {"description": "The entries"}},
                    }
                },
                "/triggers": {
                    "get": {
                        "summary": (
                            "Webhooks, schedules, and manual roots (scope: read)"
                        ),
                        "responses": {"200": {"description": "The triggers"}},
                    }
                },
                "/connections": {
                    "get": {
                        "summary": (
                            "Secrets and connections, present or missing (scope: read)"
                        ),
                        "responses": {"200": {"description": "The dependencies"}},
                    }
                },
                **{
                    f"/schedules/{{key}}/{action}": {
                        "post": {
                            "summary": f"{action.title()} a schedule (scope: operate)",
                            "responses": {"202": {"description": "Applied"}},
                        }
                    }
                    for action in ("pause", "resume")
                },
                "/healthz": {"get": {"summary": "Liveness", "security": []}},
                "/readyz": {"get": {"summary": "Readiness", "security": []}},
                "/metrics": {"get": {"summary": "Prometheus metrics (scope: read)"}},
            },
        }
        return JSONResponse(document)

    return endpoint


def build_app(
    runtime: WorkflowRuntime,
    *,
    worker: bool = True,
    ingress: bool = True,
    drain: float | str = "25s",
    tokens: ScopedTokens | None = None,
) -> Starlette:
    """Compose the standalone service application.

    Args:
        runtime: The runtime to serve.
        worker: Whether this process executes steps.
        ingress: Whether this process accepts webhooks and API calls.
        drain: How long shutdown gives in-flight attempts to commit.
        tokens: Token scopes; read from the environment when omitted.

    Returns:
        The ASGI application, with lifespan wired to the runtime.
    """
    from contextlib import asynccontextmanager

    tokens = tokens if tokens is not None else ScopedTokens()

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        """Start the runtime with the app and drain it on shutdown.

        The server stops accepting requests before this exits, so the order
        is exactly the graceful sequence: ingress closes, then the worker
        gets the drain budget to commit what it holds.

        Args:
            app: The application being served.

        Yields:
            Nothing; the service runs while suspended here.
        """
        await runtime.startup(start_worker=worker)
        try:
            yield
        finally:
            await runtime.shutdown(drain=drain)
            # The service owns its store, so the store dies with the service
            # -- on this loop, while it still runs. A Postgres pool's
            # maintenance tasks do not exit for a bare loop-close
            # cancellation, which leaks the pool in production and hangs any
            # embedding that waits for the loop's tasks to finish.
            await _close_store(runtime.store)

    routes = [
        Route("/healthz", health_endpoint(), methods=["GET"]),
        Route("/readyz", ready_endpoint(runtime), methods=["GET"]),
        Route(
            "/metrics",
            metrics_endpoint(runtime, tokens.require("read")),
            methods=["GET"],
        ),
    ]
    if ingress:
        from reflex.workflow.approvals import APPROVAL_ROUTE, approval_endpoint
        from reflex.workflow.ingress import (
            WEBHOOK_ROUTE,
            collect_webhook_routes,
            webhook_endpoint,
        )

        if not tokens:
            logger.warning(
                f"No API token configured ({TOKEN_ENV} or scoped variants); "
                "the run API is refusing every request. Webhooks still work: "
                "they authenticate with their own signatures."
            )
        routes += [
            Route("/openapi.json", openapi_endpoint(runtime), methods=["GET"]),
            Route(
                "/runs",
                start_endpoint(runtime, tokens.require("start")),
                methods=["POST"],
            ),
            Route("/runs", list_runs_endpoint(runtime, tokens), methods=["GET"]),
            Route(
                "/runs/{run_id}",
                run_endpoint(runtime, tokens.require("read")),
                methods=["GET"],
            ),
            Route(
                "/runs/{run_id}/signals/{channel}",
                signal_endpoint(runtime, tokens),
                methods=["POST"],
            ),
            *(
                Route(
                    f"/runs/{{run_id}}/{action}",
                    operator_endpoint(runtime, tokens, action),
                    methods=["POST"],
                )
                for action in ("cancel", "retry", "resume")
            ),
            # Business-key addressing over the durable request-key index: the
            # caller that knows "order_123" reaches the order's run without
            # ever having stored the engine's run id.
            Route(
                "/workflows/{workflow_id}/keys/{request_key}",
                key_read_endpoint(runtime, tokens),
                methods=["GET"],
            ),
            Route(
                "/workflows/{workflow_id}/keys/{request_key}/signals/{channel}",
                key_signal_endpoint(runtime, tokens),
                methods=["POST"],
            ),
            Route(
                "/deadletters",
                deadletters_endpoint(runtime, tokens),
                methods=["GET"],
            ),
            Route(
                "/deadletters/{parked_id}/replay",
                deadletter_replay_endpoint(runtime, tokens),
                methods=["POST"],
            ),
            Route("/audit", audit_endpoint(runtime, tokens), methods=["GET"]),
            Route("/triggers", triggers_endpoint(runtime, tokens), methods=["GET"]),
            Route(
                "/connections",
                connections_endpoint(runtime, tokens),
                methods=["GET"],
            ),
            Route(
                "/schedules/{key:path}/pause",
                schedule_toggle_endpoint(runtime, tokens, True),
                methods=["POST"],
            ),
            Route(
                "/schedules/{key:path}/resume",
                schedule_toggle_endpoint(runtime, tokens, False),
                methods=["POST"],
            ),
            # The embedded-mode paths, kept byte-for-byte: a Stripe URL or a
            # minted approval link configured against an rx.App keeps working
            # when the deployment moves to the standalone service.
            Route(APPROVAL_ROUTE, approval_endpoint(runtime), methods=["GET", "POST"]),
        ]
        if collect_webhook_routes(runtime.definitions):
            routes.append(
                Route(WEBHOOK_ROUTE, webhook_endpoint(runtime), methods=["POST"])
            )
    return Starlette(routes=routes, lifespan=lifespan)
