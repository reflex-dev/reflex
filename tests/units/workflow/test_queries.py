"""Tests for listing and filtering runs, which operator surfaces are built on."""

import pytest
from reflex_base.workflow import WorkflowConfig, manual

import reflex as rx
from reflex.workflow.records import (
    RunQuery,
    RunRecord,
    RunStatus,
    StepRecord,
    StepStatus,
)
from reflex.workflow.store import MemoryRunStore, SqliteRunStore
from reflex.workflow.testing import WorkflowTestHarness

NOW = 1_000_000.0


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    """A run store of each implementation.

    Args:
        request: The fixture request carrying the store kind.
        tmp_path: Temporary directory for the SQLite database.

    Yields:
        The store instance.
    """
    if request.param == "memory":
        yield MemoryRunStore()
    else:
        sqlite_store = SqliteRunStore(tmp_path / "workflow.db")
        yield sqlite_store
        sqlite_store.close()


async def _admit(
    store,
    run_id,
    *,
    workflow_id="ops.q",
    status=RunStatus.PENDING,
    labels=None,
    created_at=NOW,
):
    run = RunRecord(
        run_id=run_id,
        workflow_id=workflow_id,
        definition_digest="digest",
        status=status,
        state={},
        state_version=0,
        next_ordinal=1,
        labels=labels,
        created_at=created_at,
        updated_at=created_at,
    )
    step = StepRecord(
        run_id=run_id,
        ordinal=0,
        handler_id="go",
        status=StepStatus.READY,
        args={},
        origin="root",
        created_at=created_at,
        updated_at=created_at,
    )
    await store.admit(run, step, ())


async def test_list_runs_orders_newest_first_and_paginates(store):
    for index in range(5):
        await _admit(store, f"run{index}", created_at=NOW + index)
    page = await store.list_runs(RunQuery(limit=2))
    assert [run.run_id for run in page] == ["run4", "run3"]
    nextpage = await store.list_runs(
        RunQuery(limit=2, created_before=(page[-1].created_at, page[-1].run_id))
    )
    assert [run.run_id for run in nextpage] == ["run2", "run1"]


async def test_list_runs_filters_by_workflow_and_status(store):
    await _admit(store, "a", workflow_id="ops.q", status=RunStatus.COMPLETED)
    await _admit(store, "b", workflow_id="ops.q", status=RunStatus.FAILED)
    await _admit(store, "c", workflow_id="other.q", status=RunStatus.COMPLETED)
    by_workflow = await store.list_runs(RunQuery(workflow_id="ops.q"))
    assert {run.run_id for run in by_workflow} == {"a", "b"}
    by_status = await store.list_runs(RunQuery(statuses=(RunStatus.COMPLETED,)))
    assert {run.run_id for run in by_status} == {"a", "c"}
    both = await store.list_runs(
        RunQuery(workflow_id="ops.q", statuses=(RunStatus.FAILED,))
    )
    assert [run.run_id for run in both] == ["b"]


async def test_list_runs_filters_by_labels(store):
    await _admit(store, "a", labels={"customer": "acme", "tier": "pro"})
    await _admit(store, "b", labels={"customer": "acme", "tier": "free"})
    await _admit(store, "c", labels={"customer": "globex"})
    await _admit(store, "d", labels=None)
    acme = await store.list_runs(RunQuery(labels={"customer": "acme"}))
    assert {run.run_id for run in acme} == {"a", "b"}
    pro = await store.list_runs(RunQuery(labels={"customer": "acme", "tier": "pro"}))
    assert [run.run_id for run in pro] == ["a"]
    missing = await store.list_runs(RunQuery(labels={"customer": "nobody"}))
    assert missing == ()


async def test_list_runs_through_the_kernel(forked_registration_context):
    class Listed(rx.State):
        __workflow__ = WorkflowConfig(id="ops.listed")
        n: int = 0

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self, n: int):
            self.n = n

    async with WorkflowTestHarness(Listed) as harness:
        for index, customer in enumerate(("acme", "acme", "globex")):
            await harness.kernel.start(Listed.go(index), labels={"customer": customer})
        await harness.run_until_idle()

        assert len(await harness.kernel.list_runs()) == 3
        acme = await harness.kernel.list_runs(labels={"customer": "acme"})
        assert len(acme) == 2
        completed = await harness.kernel.list_runs(statuses=[RunStatus.COMPLETED])
        assert len(completed) == 3
        assert await harness.kernel.list_runs(workflow_id="nope") == ()
