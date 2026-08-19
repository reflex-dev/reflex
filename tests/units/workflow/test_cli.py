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
    by_handler = {step["handler_id"]: step for step in payload["steps"]}
    assert by_handler["start"]["attempts"] == 1, (
        "a step that succeeded on its first try ran once, not zero times"
    )
    assert by_handler["finish"]["attempts"] == 0


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


def test_stats_counts_runs_by_status(seeded):
    """The health screen: how many runs exist, and how many are still open."""
    database, _, _ = seeded
    result = _invoke("stats", "-d", database)
    assert result.exit_code == 0, result.output
    assert RunStatus.WAITING.value in result.output
    assert "open" in result.output


def test_stats_json_is_scrapeable(seeded):
    """An alert on runs needing attention must not read the database."""
    database, _, _ = seeded
    result = _invoke("stats", "-d", database, "--json")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["total"] == sum(payload["by_status"].values())
    assert payload["open"] == payload["total"], "neither seeded run is terminal"
    assert payload["needs_attention"] == payload["by_status"].get(
        RunStatus.NEEDS_ATTENTION.value, 0
    )
    assert payload["needs_attention"] == 1, "the suspended run is the one to page on"


def test_stats_filters_to_one_workflow(seeded):
    """A shared store holds every workflow; an owner asks about theirs."""
    database, _, _ = seeded
    result = _invoke("stats", "-d", database, "-w", "nope.nothing", "--json")
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "workflow": "nope.nothing",
        "total": 0,
        "open": 0,
        "needs_attention": 0,
        "by_status": {},
    }


def test_complete_ends_a_stuck_run_by_operator_decision(seeded):
    """A wait nobody will answer is closed from the CLI, not the database."""
    database, waiting, _ = seeded
    result = _invoke("complete", "-d", database, waiting, "--result", '{"ok": true}')
    assert result.exit_code == 0, result.output
    shown = _invoke("show", "-d", database, waiting, "--json")
    payload = json.loads(shown.output)
    assert payload["status"] == RunStatus.COMPLETED.value
    assert payload["result"] == {"ok": True}


def test_fail_records_the_operator_s_reason(seeded):
    """A run given up on says why, so history is not a silent failure."""
    database, waiting, _ = seeded
    result = _invoke("fail", "-d", database, waiting, "--reason", "provider retired")
    assert result.exit_code == 0, result.output
    payload = json.loads(_invoke("show", "-d", database, waiting, "--json").output)
    assert payload["status"] == RunStatus.FAILED.value
    assert "provider retired" in json.dumps(payload["error"])


def test_finalizing_an_unknown_run_fails(seeded):
    """Nothing to finalize is an error, not a silent success."""
    database, _, _ = seeded
    result = _invoke("complete", "-d", database, "no-such-run")
    assert result.exit_code == 1
    assert "unknown" in result.output


def test_complete_refuses_a_result_that_is_not_json(seeded):
    """A typo in --result must not be recorded as the string the operator typed."""
    database, waiting, _ = seeded
    result = _invoke("complete", "-d", database, waiting, "--result", "{oops")
    assert result.exit_code == 1
    assert "not JSON" in result.output
