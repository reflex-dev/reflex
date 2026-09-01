"""Tests for `rx.workflows.connect()` as a per-scope client.

The advertised use is a web process: a FastAPI route or a Django view opens a
client, starts a run, and returns. Two requests overlap all the time, and in a
multi-tenant deployment they may be pointed at different stores. A client that
published itself process-wide would let one request's work land in another
request's database, which is the one failure a tenant boundary must not have.
"""

import asyncio
import sqlite3
from typing import Any

import pytest
from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import WorkflowConfig, manual

import reflex as rx
from reflex.workflow.records import RunQuery
from reflex.workflow.runtime import workflows
from reflex.workflow.store import MemoryRunStore, SqliteRunStore


def _flow(workflow_id: str) -> Any:
    """Build a trivial workflow class.

    Args:
        workflow_id: The workflow identity to register under.

    Returns:
        The workflow class.
    """

    class Flow(rx.State):
        __workflow__ = WorkflowConfig(id=workflow_id)

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self):
            """Complete immediately.

            Returns:
                Completion.
            """
            return rx.complete(result=workflow_id)

    return Flow


async def test_two_clients_do_not_route_work_to_each_others_stores(
    forked_registration_context,
):
    """Overlapping clients each admit into their own store, not the last one open.

    Binding the active client to a context variable rather than a process
    global is what makes this hold: both tasks run in the same process, and
    one of them opened its client second.
    """
    flow = _flow("isolation.flow")
    store_a, store_b = MemoryRunStore(), MemoryRunStore()
    b_open = asyncio.Event()
    a_submitted = asyncio.Event()

    async def client_a() -> None:
        """Open first, then submit while the second client is also open."""
        async with workflows.connect(flow, store=store_a):
            await asyncio.wait_for(b_open.wait(), timeout=5)
            await workflows.submit(flow.start())
            a_submitted.set()

    async def client_b() -> None:
        """Open second and stay open across the other client's submit."""
        async with workflows.connect(flow, store=store_b):
            b_open.set()
            await asyncio.wait_for(a_submitted.wait(), timeout=5)
            await workflows.submit(flow.start())

    await asyncio.gather(client_a(), client_b())

    assert len(await store_a.list_runs(RunQuery())) == 1
    assert len(await store_b.list_runs(RunQuery())) == 1


async def test_a_client_closes_the_store_it_opened(
    tmp_path, forked_registration_context
):
    """A request-scoped client must not leak a connection per request."""
    flow = _flow("isolation.owned")
    database = tmp_path / "owned.db"
    async with workflows.connect(flow, database=str(database)) as runtime:
        opened = runtime.store
        await workflows.submit(flow.start())
    assert isinstance(opened, SqliteRunStore)
    # A closed sqlite3 connection refuses further work; if the store were
    # still open this would succeed and the connection would have leaked.
    with pytest.raises(sqlite3.ProgrammingError):
        await opened.list_runs(RunQuery())


async def test_a_client_leaves_a_caller_supplied_store_open(
    forked_registration_context,
):
    """A store the caller owns outlives the block that borrowed it."""
    flow = _flow("isolation.borrowed")
    store = MemoryRunStore()
    async with workflows.connect(flow, store=store):
        await workflows.submit(flow.start())
    assert len(await store.list_runs(RunQuery())) == 1


async def test_leaving_a_client_scope_restores_the_previous_one(
    forked_registration_context,
):
    """A client is a scope; leaving it must not leave the process bound."""
    flow = _flow("isolation.scoped")
    async with workflows.connect(flow, store=MemoryRunStore()):
        pass
    with pytest.raises(WorkflowRuntimeError):
        await workflows.submit(flow.start())
