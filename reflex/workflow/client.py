"""Start, observe, and signal runs over HTTP, from any process.

``rx.workflows.connect()`` is for a process that shares the store: it opens
the database. A service in another deployment -- a FastAPI app on another
team's cluster, a script on a laptop, a partner's integration -- should hold a
scoped API token, never database credentials. ``RemoteWorkflows`` is that
caller's client: the same operations over ``reflex workflows serve``'s HTTP
API, answering with the same dispositions the kernel does.

Refusals raise rather than return: a 403 must never read like a run that did
not start. Outcomes the API expresses as dispositions (``deduplicated``,
``unknown_run``, ``run_terminal``) come back as values, exactly as they do
in-process.

Operator surfaces -- dead letters, the audit log, triggers, schedules -- stay
on the CLI and the console; this client is the run-facing half.
"""

from __future__ import annotations

import dataclasses
import time
from typing import TYPE_CHECKING, Any, Final, TypeVar, overload
from urllib.parse import quote

from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import DurationLike, parse_duration

from reflex.workflow.records import TERMINAL_RUN_STATUSES, RunStatus

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    import httpx

DEFAULT_TIMEOUT: Final = 10.0
DEFAULT_POLL_INTERVAL: Final = 0.5

T = TypeVar("T")


class RemoteWorkflowError(WorkflowRuntimeError):
    """The service refused a request.

    Attributes:
        status: The HTTP status the service answered with.
        detail: The service's explanation.
    """

    def __init__(self, status: int, detail: str):
        """Record the refusal.

        Args:
            status: The HTTP status.
            detail: The service's explanation.
        """
        super().__init__(f"workflow service answered {status}: {detail}")
        self.status = status
        self.detail = detail


@dataclasses.dataclass(frozen=True, slots=True)
class RemoteStart:
    """What admission did with a submission.

    Attributes:
        disposition: ``started``, ``deduplicated``, ``coalesced``, ``skipped``,
            or ``rejected`` -- the same words as in-process.
        run_id: The created or prior run, when the disposition names one.
    """

    disposition: str
    run_id: str | None

    @property
    def started(self) -> bool:
        """Whether this submission created the run rather than finding one.

        Returns:
            True when a new run was admitted.
        """
        return self.disposition == "started"


@dataclasses.dataclass(frozen=True, slots=True)
class RemoteRun:
    """A run as the service reports it.

    Attributes:
        run_id: The run's identity.
        workflow_id: Its workflow.
        status: Its status.
        result: What it produced, once completed.
        error: Its terminal or suspension error, if any.
        release: The release it is pinned to, when the service reports one.
        labels: Its labels, when the service reports them (listings do).
        steps: Its steps, when the service reports them (single reads do).
    """

    run_id: str
    workflow_id: str
    status: RunStatus
    result: Any = None
    error: dict[str, Any] | None = None
    release: str | None = None
    labels: dict[str, str] = dataclasses.field(default_factory=dict)
    steps: tuple[dict[str, Any], ...] = ()

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> RemoteRun:
        """Read a run out of any of the service's run-shaped responses.

        Args:
            payload: The response body.

        Returns:
            The run.
        """
        return cls(
            run_id=payload["run_id"],
            workflow_id=payload["workflow"],
            status=RunStatus(payload["status"]),
            result=payload.get("result"),
            error=payload.get("error"),
            release=payload.get("release"),
            labels=dict(payload.get("labels") or {}),
            steps=tuple(payload.get("steps") or ()),
        )

    @property
    def terminal(self) -> bool:
        """Whether the run has reached a final state.

        Returns:
            True for completed, failed, cancelled, and timed-out runs.
        """
        return self.status in TERMINAL_RUN_STATUSES


def _workflow_id(workflow: str | type) -> str:
    """Accept a workflow class or its id.

    Args:
        workflow: The class carrying ``__workflow__``, or the id itself.

    Returns:
        The workflow id.
    """
    if isinstance(workflow, str):
        return workflow
    return workflow.__workflow__.id


def _detail(response: httpx.Response) -> str:
    """Read the service's explanation from a refusal.

    Args:
        response: The refusing response.

    Returns:
        The ``error`` field when the body is the API's JSON shape, else the
        raw text.
    """
    try:
        body = response.json()
    except ValueError:
        return response.text
    if isinstance(body, dict) and "error" in body:
        return str(body["error"])
    return response.text


class RemoteWorkflows:
    """A client for a ``reflex workflows serve`` service.

    Use it as a context manager so the connection pool closes::

        async with RemoteWorkflows("https://flows.internal", token) as flows:
            started = await flows.start(Orders, "place", {"order_id": "o-1"})
            receipt = await flows.result(started.run_id, as_type=Receipt)

    Attributes:
        base_url: The service's origin.
    """

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        *,
        actor: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        """Bind to a service.

        Args:
            base_url: The service's origin, e.g. ``https://flows.internal``.
            token: The bearer token; its scopes decide what the service
                allows. A token bound to a principal names the actor on the
                service's side and wins over ``actor``.
            actor: Who is acting, recorded on operator actions when the token
                is not bound to a principal (sent as ``X-Actor``).
            client: The HTTP client to use; one is created on first use.
            timeout: Seconds to wait on one request.
        """
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._actor = actor
        self._client = client
        self._timeout = timeout

    async def __aenter__(self) -> RemoteWorkflows:
        """Enter the client.

        Returns:
            This client.
        """
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Close the connection pool.

        Args:
            exc: The exception triple, unused.
        """
        await self.aclose()

    async def aclose(self) -> None:
        """Close the connection pool."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def start(
        self,
        workflow: str | type,
        handler: str,
        args: Mapping[str, Any] | None = None,
        *,
        request_key: str | None = None,
        labels: Mapping[str, str] | None = None,
    ) -> RemoteStart:
        """Admit a run (scope ``start``).

        Args:
            workflow: The workflow class or id.
            handler: The manual root handler's stable id or Python name.
            args: The handler's arguments.
            request_key: Idempotent admission key; a repeat returns the same
                run as ``deduplicated``.
            labels: Indexing labels, searchable on every surface.

        Returns:
            The admission outcome.

        Raises:
            RemoteWorkflowError: If the service refused -- unknown workflow or
                handler, arguments that do not fit, or a token without the
                scope.
        """
        body: dict[str, Any] = {
            "workflow": _workflow_id(workflow),
            "handler": handler,
            "args": dict(args or {}),
        }
        if request_key is not None:
            body["request_key"] = request_key
        if labels:
            body["labels"] = dict(labels)
        response = await self._request("POST", "/runs", json=body)
        if response.status_code != 202:
            raise RemoteWorkflowError(response.status_code, _detail(response))
        payload = response.json()
        return RemoteStart(payload["disposition"], payload.get("run_id"))

    async def get(self, run_id: str) -> RemoteRun | None:
        """Read one run (scope ``read``).

        Args:
            run_id: The run.

        Returns:
            The run with its steps, or None when the service does not know it.
        """
        response = await self._request("GET", f"/runs/{quote(run_id, safe='')}")
        if response.status_code == 404:
            return None
        self._expect(response, 200)
        return RemoteRun.from_payload(response.json())

    async def get_by_key(
        self, workflow: str | type, request_key: str
    ) -> RemoteRun | None:
        """Read the run a business key admitted (scope ``read``).

        Args:
            workflow: The workflow class or id.
            request_key: The admission key.

        Returns:
            The run, or None when the key admitted nothing.
        """
        response = await self._request(
            "GET",
            f"/workflows/{quote(_workflow_id(workflow), safe='')}"
            f"/keys/{quote(request_key, safe='')}",
        )
        if response.status_code == 404:
            return None
        self._expect(response, 200)
        return RemoteRun.from_payload(response.json())

    async def list(
        self,
        *,
        workflow: str | type | None = None,
        statuses: Iterable[RunStatus | str] = (),
        labels: Mapping[str, str] | None = None,
        limit: int = 50,
    ) -> list[RemoteRun]:
        """List runs, newest first (scope ``read``).

        Args:
            workflow: Restrict to one workflow.
            statuses: Restrict to these statuses.
            labels: Require every one of these label values.
            limit: At most this many, capped by the service at 500.

        Returns:
            Run summaries: identity, status, labels, and release.
        """
        params: list[tuple[str, Any]] = [("limit", str(limit))]
        if workflow is not None:
            params.append(("workflow", _workflow_id(workflow)))
        params.extend(
            ("status", status.value if isinstance(status, RunStatus) else status)
            for status in statuses
        )
        params.extend((f"label.{key}", value) for key, value in (labels or {}).items())
        response = await self._request("GET", "/runs", params=params)
        self._expect(response, 200)
        return [RemoteRun.from_payload(row) for row in response.json()["runs"]]

    async def signal(
        self,
        run_id: str,
        channel: str,
        payload: Any = None,
        *,
        key: str | None = None,
    ) -> str:
        """Deliver a signal to a run's channel (scope ``signal``).

        Args:
            run_id: The run.
            channel: The channel name.
            payload: The signal payload.
            key: Sender idempotency key; a repeat is ``duplicate``.

        Returns:
            The disposition: ``resolved``, ``buffered``, ``duplicate``,
            ``unknown_run``, ``run_terminal``, or ``expired``.

        Raises:
            RemoteWorkflowError: If the channel is unknown or the payload does
                not fit its model.
        """
        return await self._deliver(
            f"/runs/{quote(run_id, safe='')}/signals/{quote(channel, safe='')}",
            payload,
            key,
        )

    async def signal_by_key(
        self,
        workflow: str | type,
        request_key: str,
        channel: str,
        payload: Any = None,
        *,
        key: str | None = None,
    ) -> str:
        """Deliver a signal to the run a business key admitted (scope ``signal``).

        Args:
            workflow: The workflow class or id.
            request_key: The admission key.
            channel: The channel name.
            payload: The signal payload.
            key: Sender idempotency key.

        Returns:
            The disposition, ``unknown_key`` when the key admitted nothing.

        Raises:
            RemoteWorkflowError: If the channel is unknown or the payload does
                not fit its model.
        """
        return await self._deliver(
            f"/workflows/{quote(_workflow_id(workflow), safe='')}"
            f"/keys/{quote(request_key, safe='')}/signals/{quote(channel, safe='')}",
            payload,
            key,
        )

    async def cancel(self, run_id: str, *, reason: str | None = None) -> bool:
        """Ask a run to stop (scope ``operate``).

        Args:
            run_id: The run.
            reason: Why, recorded in the run's history beside the actor.

        Returns:
            Whether the request applied; False for an unknown run or one
            already terminal.
        """
        return await self._operate("cancel", run_id, reason)

    async def retry(self, run_id: str, *, reason: str | None = None) -> bool:
        """Re-open a failed run's failed step (scope ``operate``).

        Args:
            run_id: The run.
            reason: Why, recorded in the run's history beside the actor.

        Returns:
            Whether the action applied.
        """
        return await self._operate("retry", run_id, reason)

    async def resume(self, run_id: str, *, reason: str | None = None) -> bool:
        """Re-open a run suspended for attention (scope ``operate``).

        Args:
            run_id: The run.
            reason: Why, recorded in the run's history beside the actor.

        Returns:
            Whether the action applied.
        """
        return await self._operate("resume", run_id, reason)

    async def wait(
        self,
        run_id: str,
        *,
        timeout: DurationLike = "30s",
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> RemoteRun:
        """Poll until the run reaches a terminal state.

        Args:
            run_id: The run.
            timeout: How long to wait before giving up.
            poll_interval: Seconds between reads.

        Returns:
            The terminal run.

        Raises:
            WorkflowRuntimeError: If the run is unknown or does not finish in
                time.
        """
        import asyncio

        deadline = time.monotonic() + parse_duration(timeout)
        while True:
            run = await self.get(run_id)
            if run is None:
                msg = f"Run {run_id!r} is unknown to {self.base_url}."
                raise WorkflowRuntimeError(msg)
            if run.terminal:
                return run
            if time.monotonic() >= deadline:
                msg = (
                    f"Run {run_id!r} did not finish within {timeout!r}; "
                    f"it is {run.status.value}."
                )
                raise WorkflowRuntimeError(msg)
            await asyncio.sleep(poll_interval)

    @overload
    async def result(
        self,
        run_id: str,
        *,
        as_type: type[T],
        timeout: DurationLike = "30s",
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> T: ...

    @overload
    async def result(
        self,
        run_id: str,
        *,
        as_type: None = None,
        timeout: DurationLike = "30s",
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> Any: ...

    async def result(
        self,
        run_id: str,
        *,
        as_type: type[Any] | None = None,
        timeout: DurationLike = "30s",
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> Any:
        """Wait for the run to finish and return what it produced.

        The same contract as ``RunHandle.result``: a result crosses the wire
        as JSON, so pass ``as_type`` to validate it back into the declared
        shape -- a real validation naming the run, not a cast.

        Args:
            run_id: The run.
            as_type: Type to validate and coerce the result into.
            timeout: How long to wait before giving up.
            poll_interval: Seconds between reads.

        Returns:
            The run's result, coerced to ``as_type`` when one was given.

        Raises:
            WorkflowRuntimeError: If the run is unknown, does not finish in
                time, finishes in any state other than completed, or produced
                a result that does not fit ``as_type``.
        """
        run = await self.wait(run_id, timeout=timeout, poll_interval=poll_interval)
        if run.status is not RunStatus.COMPLETED:
            detail = f": {run.error}" if run.error else ""
            msg = f"Run {run_id!r} finished {run.status.value}{detail}"
            raise WorkflowRuntimeError(msg)
        if as_type is None:
            return run.result
        from pydantic import TypeAdapter, ValidationError

        try:
            return TypeAdapter(as_type).validate_python(run.result)
        except ValidationError as error:
            msg = (
                f"Run {run_id!r} produced a result that does not fit "
                f"{getattr(as_type, '__name__', as_type)}: {error}"
            )
            raise WorkflowRuntimeError(msg) from error

    async def ready(self) -> bool:
        """Ask whether the service can do useful work right now.

        Returns:
            True when its readiness probe answers 200.
        """
        response = await self._request("GET", "/readyz")
        return response.status_code == 200

    async def _deliver(self, path: str, payload: Any, key: str | None) -> str:
        """Post a signal and read its disposition.

        Args:
            path: The signal route.
            payload: The signal payload.
            key: Sender idempotency key, if any.

        Returns:
            The disposition.

        Raises:
            RemoteWorkflowError: If the service refused the delivery outright.
        """
        headers = {"Idempotency-Key": key} if key else None
        response = await self._request("POST", path, json=payload, headers=headers)
        if response.status_code in (202, 404, 409):
            return response.json()["disposition"]
        raise RemoteWorkflowError(response.status_code, _detail(response))

    async def _operate(self, action: str, run_id: str, reason: str | None) -> bool:
        """Apply one operator action.

        Args:
            action: ``cancel``, ``retry``, or ``resume``.
            run_id: The run.
            reason: Why, if given.

        Returns:
            Whether it applied.

        Raises:
            RemoteWorkflowError: If the service refused for a reason other than
                the run's state.
        """
        response = await self._request(
            "POST",
            f"/runs/{quote(run_id, safe='')}/{action}",
            json={"reason": reason} if reason else {},
        )
        if response.status_code == 202:
            return True
        if response.status_code in (404, 409):
            return False
        raise RemoteWorkflowError(response.status_code, _detail(response))

    def _expect(self, response: httpx.Response, status: int) -> None:
        """Require a status, raising the service's explanation otherwise.

        Args:
            response: The response.
            status: The status the caller handles.

        Raises:
            RemoteWorkflowError: If the status differs.
        """
        if response.status_code != status:
            raise RemoteWorkflowError(response.status_code, _detail(response))

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: list[tuple[str, Any]] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        """Send one request with the client's credentials.

        Args:
            method: The HTTP method.
            path: The route, relative to the base URL.
            json: The JSON body, if any.
            params: Query parameters, if any.
            headers: Extra headers, if any.

        Returns:
            The response, for statuses the caller interprets.

        Raises:
            RemoteWorkflowError: On an authorization refusal or a server error,
                which no caller can interpret as an outcome.
        """
        import httpx

        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        sent: dict[str, str] = dict(headers or {})
        if self._token:
            sent["Authorization"] = f"Bearer {self._token}"
        if self._actor:
            sent["X-Actor"] = self._actor
        response = await self._client.request(
            method,
            f"{self.base_url}{path}",
            json=json,
            params=params,
            headers=sent,
        )
        if response.status_code in (401, 403) or response.status_code >= 500:
            raise RemoteWorkflowError(response.status_code, _detail(response))
        return response
