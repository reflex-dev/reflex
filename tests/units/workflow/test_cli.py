"""Tests for the reflex workflows command group."""

import asyncio
import json

import pytest
from click.testing import CliRunner
from reflex_base.workflow import WorkflowConfig, manual, needs_attention

import reflex as rx
from reflex.workflow.cli import workflows
from reflex.workflow.records import RunStatus
from reflex.workflow.store import SqliteRunStore
from reflex.workflow.testing import WorkflowTestHarness


@pytest.fixture
def seeded(forked_registration_context, tmp_path):
    """A database with one waiting run and one suspended run.

    Args:
        forked_registration_context: Isolates state registration.
        tmp_path: Temporary directory for the database.

    Returns:
        The database path and the two run ids.
    """

    class OpsFlow(rx.State):
        __workflow__ = WorkflowConfig(id="ops.cli")
        cid: str = ""

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self, cid: str):
            """Start work for a customer.

            Args:
                cid: The customer identifier.

            Returns:
                A delayed finish, or a suspension for the flagged customer.
            """
            self.cid = cid
            if cid == "flagged":
                return needs_attention("manual_check")
            return rx.after("1h", OpsFlow.finish)

        @rx.event(durable=True, effect="none")
        def finish(self):
            """Finish the work."""

    db_path = tmp_path / "workflow.db"

    async def seed():
        store = SqliteRunStore(db_path)
        async with WorkflowTestHarness(OpsFlow, store=store) as harness:
            waiting = await harness.start(OpsFlow.start("acme"), labels={"tier": "pro"})
            suspended = await harness.start(OpsFlow.start("flagged"))
        store.close()
        return waiting.run_id, suspended.run_id

    waiting_id, suspended_id = asyncio.run(seed())
    return str(db_path), waiting_id, suspended_id


def _load_run(database: str, run_id: str):
    """Read a run back from the database the CLI just wrote.

    Args:
        database: Path to the SQLite database.
        run_id: The run to read.

    Returns:
        The run record, or None.
    """

    async def load():
        store = SqliteRunStore(database)
        try:
            return await store.get_run(run_id)
        finally:
            store.close()

    return asyncio.run(load())


def _invoke(*args):
    """Run a CLI command and return its result.

    Args:
        args: The command line arguments.

    Returns:
        The click result.
    """
    return CliRunner().invoke(workflows, list(args))


def test_list_shows_runs_newest_first(seeded):
    database, _, _ = seeded
    result = _invoke("list", "-d", database)
    assert result.exit_code == 0
    assert "ops.cli" in result.output
    assert result.output.count("ops.cli") == 2


def test_list_filters_by_status_and_label(seeded):
    database, waiting, suspended = seeded
    by_status = _invoke("list", "-d", database, "-s", "NEEDS_ATTENTION", "--json")
    assert by_status.exit_code == 0
    rows = json.loads(by_status.output)
    assert [row["run_id"] for row in rows] == [suspended]

    by_label = _invoke("list", "-d", database, "-l", "tier=pro", "--json")
    rows = json.loads(by_label.output)
    assert [row["run_id"] for row in rows] == [waiting]


def test_list_reports_when_nothing_matches(seeded):
    database, _, _ = seeded
    result = _invoke("list", "-d", database, "-w", "nope.nothing")
    assert result.exit_code == 0
    assert "No runs matched" in result.output


def test_show_renders_steps_and_history(seeded):
    database, waiting, _ = seeded
    result = _invoke("show", "-d", database, waiting, "--history")
    assert result.exit_code == 0
    assert waiting in result.output
    assert "start" in result.output
    assert "run_admitted" in result.output


def test_show_json_carries_state_and_steps(seeded):
    database, waiting, _ = seeded
    result = _invoke("show", "-d", database, waiting, "--json")
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["state"] == {"cid": "acme"}
    assert payload["status"] == RunStatus.WAITING.value
    assert [step["handler_id"] for step in payload["steps"]] == ["start", "finish"]


def test_show_unknown_run_fails(seeded):
    database, _, _ = seeded
    result = _invoke("show", "-d", database, "no-such-run")
    assert result.exit_code == 1


def test_cancel_records_intent(seeded):
    database, waiting, _ = seeded
    result = _invoke("cancel", "-d", database, waiting)
    assert result.exit_code == 0
    assert "Cancellation requested" in result.output

    run = _load_run(database, waiting)
    assert run is not None
    assert run.cancel_requested

    # Cancelling twice is refused rather than silently repeated.
    assert _invoke("cancel", "-d", database, waiting).exit_code == 0


def test_resume_reopens_only_suspended_runs(seeded):
    database, waiting, suspended = seeded
    assert _invoke("resume", "-d", database, waiting).exit_code == 1

    result = _invoke("resume", "-d", database, suspended)
    assert result.exit_code == 0
    assert "Resumed" in result.output

    run = _load_run(database, suspended)
    assert run is not None
    assert run.status is RunStatus.PENDING
