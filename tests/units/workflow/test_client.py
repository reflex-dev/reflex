"""The remote client, driven against a real in-process service.

No mocks: the client's requests go through ``httpx`` into the ASGI app that
``reflex workflows serve`` runs, so what is tested is the wire contract --
routes, bodies, status codes, dispositions -- not the client's idea of it.
"""

import httpx
import pytest
from pydantic import BaseModel
from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import Signal, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.client import RemoteRun, RemoteWorkflowError, RemoteWorkflows
from reflex.workflow.records import HistoryEventType, RunStatus
from reflex.workflow.runtime import WorkflowRuntime
from reflex.workflow.serve import SCOPES, ScopedTokens, build_app
from reflex.workflow.store import MemoryRunStore


class Receipt(BaseModel):
    """What an order run produces."""

    order_id: str
    total: int


class Orders(rx.State):
    """A root that completes at once, and one that waits for a shipment."""

    __workflow__ = WorkflowConfig(id="client.orders")
    shipped = Signal()

    @rx.event(durable=True, trigger=manual(), effect="none")
    def place(self, order_id: str, total: int = 10):
        """Complete with a receipt.

        Args:
            order_id: The order.
            total: Its total.

        Returns:
            Completion.
        """
        return rx.complete(result={"order_id": order_id, "total": total})

    @rx.event(durable=True, trigger=manual(), effect="none")
    def track(self, order_id: str):
        """Wait for the shipment.

        Args:
            order_id: The order.

        Returns:
            The wait.
        """
        return rx.wait_for(Orders.shipped, then=Orders.close, timeout=rx.never)

    @rx.event(durable=True, effect="none")
    def close(self, payload):
        """Finish with the shipment.

        Args:
            payload: The delivered payload.

        Returns:
            Completion.
        """
        return rx.complete(result=payload)


def _tokens() -> ScopedTokens:
    """One token per scope, plus one with every scope.

    Returns:
        The scope mapping.
    """
    grants = {f"tk_{scope}": frozenset({scope}) for scope in SCOPES}
    grants["tk_all"] = frozenset(SCOPES)
    return ScopedTokens(grants=grants)


@pytest.fixture
async def service(forked_registration_context):
    """A started, worker-less runtime behind the service app.

    The worker is off so the test drives the kernel between client calls and
    every state transition is deterministic.

    Args:
        forked_registration_context: Isolated state registry.

    Yields:
        The runtime and a factory for clients bound to the app.
    """
    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(Orders)
    app = build_app(runtime, worker=False, drain=0, tokens=_tokens())
    await runtime.startup(start_worker=False)

    def remote(token: str = "tk_all", actor: str | None = "alice") -> RemoteWorkflows:
        """Bind a client to the in-process app.

        Args:
            token: The bearer token to present.
            actor: The actor claim to send.

        Returns:
            The client.
        """
        return RemoteWorkflows(
            "http://flows.test/",
            token,
            actor=actor,
            client=httpx.AsyncClient(transport=httpx.ASGITransport(app=app)),
        )

    yield runtime, remote
    await runtime.shutdown()


async def test_start_read_and_typed_result_round_trip(service):
    """The basic loop a script runs: start, wait, read the result as a type.

    Args:
        service: The runtime and client factory.
    """
    runtime, remote = service
    async with remote() as flows:
        started = await flows.start(
            Orders, "place", {"order_id": "o-1", "total": 42}, request_key="o-1"
        )
        assert started.started
        assert started.run_id is not None
        await runtime.kernel.run_until_idle()

        run = await flows.get(started.run_id)
        assert isinstance(run, RemoteRun)
        assert (run.workflow_id, run.status) == ("client.orders", RunStatus.COMPLETED)
        assert [step["handler"] for step in run.steps] == ["place"]

        receipt = await flows.result(started.run_id, as_type=Receipt)
        assert receipt == Receipt(order_id="o-1", total=42)
        assert await flows.result(started.run_id) == {"order_id": "o-1", "total": 42}

        again = await flows.start(
            "client.orders", "place", {"order_id": "o-1"}, request_key="o-1"
        )
        assert (again.disposition, again.run_id) == ("deduplicated", started.run_id)
        by_key = await flows.get_by_key(Orders, "o-1")
        assert by_key is not None
        assert by_key.run_id == started.run_id
        assert await flows.get_by_key(Orders, "never") is None
        assert await flows.get("nope") is None
        assert await flows.ready()


async def test_signals_carry_the_kernel_dispositions(service):
    """Every disposition the kernel produces comes back as the same word.

    Args:
        service: The runtime and client factory.
    """
    runtime, remote = service
    async with remote() as flows:
        started = await flows.start(
            Orders, "track", {"order_id": "o-2"}, request_key="o-2"
        )
        assert started.run_id is not None
        await runtime.kernel.run_until_idle()

        assert (
            await flows.signal_by_key(
                Orders, "o-2", "shipped", {"parcel": "P"}, key="e1"
            )
            == "resolved"
        )
        assert (
            await flows.signal_by_key(
                Orders, "o-2", "shipped", {"parcel": "P"}, key="e1"
            )
            == "duplicate"
        )
        assert (
            await flows.signal_by_key(Orders, "missing", "shipped", {}) == "unknown_key"
        )
        assert await flows.signal("nope", "shipped", {}) == "unknown_run"
        await runtime.kernel.run_until_idle()
        assert await flows.signal(started.run_id, "shipped", {}) == "run_terminal"
        assert await flows.result(started.run_id) == {"parcel": "P"}

        with pytest.raises(RemoteWorkflowError) as refused:
            await flows.signal(started.run_id, "no_such_channel", {})
        assert refused.value.status == 400
        assert "no_such_channel" in refused.value.detail


async def test_operator_actions_apply_once_and_carry_the_actor(service):
    """Cancel applies to a waiting run, not to a finished one, and names who asked.

    Args:
        service: The runtime and client factory.
    """
    runtime, remote = service
    async with remote(actor="alice") as flows:
        started = await flows.start(Orders, "track", {"order_id": "o-3"})
        assert started.run_id is not None
        await runtime.kernel.run_until_idle()

        assert await flows.cancel(started.run_id, reason="customer withdrew") is True
        await runtime.kernel.run_until_idle()
        run = await flows.wait(started.run_id, timeout="1s", poll_interval=0.01)
        assert run.status is RunStatus.CANCELLED
        assert await flows.cancel(started.run_id) is False, "already terminal"
        assert await flows.retry("nope") is False, "unknown runs are not applied"

        history = await runtime.kernel._store.get_history(started.run_id)  # pyright: ignore[reportPrivateUsage]
        requested = [
            event
            for event in history
            if event.type is HistoryEventType.RUN_CANCEL_REQUESTED
        ]
        assert len(requested) == 1
        assert requested[0].data.get("actor") == "alice"
        assert requested[0].data.get("reason") == "customer withdrew"


async def test_listing_filters_by_workflow_status_and_labels(service):
    """The list mirrors the query the CLI and console run.

    Args:
        service: The runtime and client factory.
    """
    runtime, remote = service
    async with remote() as flows:
        acme = await flows.start(
            Orders, "place", {"order_id": "a"}, labels={"tenant": "acme"}
        )
        await flows.start(Orders, "place", {"order_id": "b"}, labels={"tenant": "beta"})
        await runtime.kernel.run_until_idle()

        everything = await flows.list(workflow=Orders)
        assert len(everything) == 2
        only_acme = await flows.list(labels={"tenant": "acme"})
        assert [run.run_id for run in only_acme] == [acme.run_id]
        assert only_acme[0].labels == {"tenant": "acme"}
        assert await flows.list(statuses=[RunStatus.FAILED]) == []
        assert await flows.list(statuses=["completed"], limit=1) != []


async def test_refusals_raise_instead_of_looking_like_outcomes(service):
    """A token without the scope, a bad token, and bad arguments all raise.

    Args:
        service: The runtime and client factory.
    """
    _, remote = service
    async with remote(token="tk_read") as reader:
        with pytest.raises(RemoteWorkflowError) as forbidden:
            await reader.start(Orders, "place", {"order_id": "x"})
        assert forbidden.value.status == 403

    async with remote(token="not-a-token") as stranger:
        with pytest.raises(RemoteWorkflowError) as unauthorized:
            await stranger.get("anything")
        assert unauthorized.value.status == 401

    async with remote() as flows:
        with pytest.raises(RemoteWorkflowError) as bad_args:
            await flows.start(Orders, "place", {})
        assert bad_args.value.status == 400
        assert "missing required arguments" in bad_args.value.detail
        with pytest.raises(RemoteWorkflowError) as unknown:
            await flows.start("no.such.workflow", "place", {"order_id": "x"})
        assert unknown.value.status == 404


async def test_waiting_gives_up_on_time_and_names_the_state(service):
    """A run that never finishes is reported as still waiting, not hung on.

    Args:
        service: The runtime and client factory.
    """
    runtime, remote = service
    async with remote() as flows:
        started = await flows.start(Orders, "track", {"order_id": "o-4"})
        assert started.run_id is not None
        await runtime.kernel.run_until_idle()
        with pytest.raises(WorkflowRuntimeError, match="WAITING"):
            await flows.wait(started.run_id, timeout="0.05s", poll_interval=0.01)
        with pytest.raises(WorkflowRuntimeError, match="unknown"):
            await flows.wait("nope", timeout="0.05s", poll_interval=0.01)
