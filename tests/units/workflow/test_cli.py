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
        "digest": None,
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


def test_finalizing_an_unknown_run_fails(seeded, caplog):
    """Nothing to finalize is an error, not a silent success.

    A run that does not exist now says exactly that. The older message
    offered three possibilities at once -- unknown, already finished, or
    held by a worker -- which is still right for a run that does exist, and
    unhelpfully vague for one that does not.

    Args:
        seeded: The database and its run ids.
        caplog: Captured log records.
    """
    database, _, _ = seeded
    result = _invoke("complete", "-d", database, "no-such-run")
    assert result.exit_code == 1
    assert "No run" in caplog.text


def test_finalizing_a_finished_run_says_why(seeded, caplog):
    """A run that exists but cannot be finalized keeps the fuller message.

    Args:
        seeded: The database and its run ids.
        caplog: Captured log records.
    """
    database, waiting, _ = seeded
    assert _invoke("complete", "-d", database, waiting).exit_code == 0
    again = _invoke("complete", "-d", database, waiting)
    assert again.exit_code == 1
    assert "already finished" in caplog.text


def test_complete_refuses_a_result_that_is_not_json(seeded, caplog):
    """A typo in --result must not be recorded as the string the operator typed."""
    database, waiting, _ = seeded
    result = _invoke("complete", "-d", database, waiting, "--result", "{oops")
    assert result.exit_code == 1
    assert "not JSON" in caplog.text


def test_purge_deletes_only_stale_terminal_runs(seeded):
    """Retention is an operator command, not out-of-band SQL."""
    database, waiting, _ = seeded
    kept = _invoke("purge", "-d", database, "--older-than", "0s", "--yes")
    assert kept.exit_code == 0, kept.output
    assert "Purged 0 run(s)" in kept.output, "no seeded run is terminal yet"

    done = _invoke("complete", "-d", database, waiting, "--result", '"ok"')
    assert done.exit_code == 0, done.output
    purged = _invoke("purge", "-d", database, "--older-than", "0s", "--yes")
    assert purged.exit_code == 0, purged.output
    assert "Purged 1 run(s)" in purged.output
    assert _invoke("show", "-d", database, waiting).exit_code == 1


def test_a_run_id_prefix_is_enough(seeded):
    """`dev` prints eight-character prefixes, so the CLI has to take them.

    Reading one surface and typing into another is the normal way an operator
    uses these commands, and "No run 'ca40d354'" for an id the tool itself
    printed is a dead end.

    Args:
        seeded: The database and its run ids.
    """
    database, waiting_id, _ = seeded
    full = _invoke("show", "-d", database, waiting_id, "--json")
    assert full.exit_code == 0, full.output
    short = _invoke("show", "-d", database, waiting_id[:8], "--json")
    assert short.exit_code == 0, short.output
    assert json.loads(short.output)["run_id"] == waiting_id


def test_an_ambiguous_prefix_refuses_and_names_the_candidates(seeded):
    """Acting on the wrong run is worse than being asked to be specific.

    Args:
        seeded: The database and its run ids.
    """
    database, waiting_id, suspended_id = seeded
    shared = ""
    for index in range(1, 33):
        if waiting_id[:index] != suspended_id[:index]:
            break
        shared = waiting_id[:index]
    if not shared:
        pytest.skip("the two seeded run ids share no prefix this time")
    result = _invoke("show", "-d", database, shared)
    assert result.exit_code == 1
    assert "matches several runs" in result.output


def test_an_unknown_prefix_still_says_so(seeded, caplog):
    """The no-match message must not be lost to the new prefix path.

    Args:
        seeded: The database and its run ids.
        caplog: Captured log records.
    """
    database, _, _ = seeded
    result = _invoke("show", "-d", database, "nosuchrun")
    assert result.exit_code == 1
    assert "No run" in caplog.text


def test_operator_actions_take_a_prefix_too(seeded):
    """Every command that takes a run id resolves the same way.

    Args:
        seeded: The database and its run ids.
    """
    database, _, suspended_id = seeded
    result = _invoke("resume", "-d", database, suspended_id[:8])
    assert result.exit_code == 0, result.output
    run = _load_run(database, suspended_id)
    assert run is not None
    assert run.status is not RunStatus.NEEDS_ATTENTION


def test_cancel_records_the_operator_and_their_reason(tmp_path, monkeypatch):
    """`--reason` and the invoking user land in the run's history.

    Args:
        tmp_path: Working directory for the database.
        monkeypatch: Used to pin the actor.
    """
    import asyncio
    import json as jsonlib
    import sqlite3
    import subprocess
    import sys
    import time

    from reflex.workflow.records import (
        HistoryEventType,
        RunRecord,
        RunStatus,
        StepRecord,
        StepStatus,
    )
    from reflex.workflow.store import SqliteRunStore

    db = tmp_path / "attr.db"
    now = time.time()

    async def seed() -> None:
        """Admit one long-waiting run."""
        store = SqliteRunStore(db)
        await store.admit(
            RunRecord(
                run_id="auditrun1",
                workflow_id="cli.audit",
                definition_digest="d",
                status=RunStatus.WAITING,
                state={},
                state_version=1,
                next_ordinal=2,
                created_at=now,
                updated_at=now,
            ),
            StepRecord(
                run_id="auditrun1",
                ordinal=0,
                handler_id="go",
                status=StepStatus.READY,
                args={},
                due_at=now + 86_400,
                origin="root",
                created_at=now,
                updated_at=now,
            ),
            ((HistoryEventType.RUN_ADMITTED, {}),),
        )
        store.close()

    asyncio.run(seed())
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from reflex.workflow.cli import workflows; workflows()",
            "cancel",
            "auditrun1",
            "--reason",
            "fat-fingered order",
            "-d",
            str(db),
        ],
        env={**__import__("os").environ, "REFLEX_ACTOR": "alek"},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-500:]

    connection = sqlite3.connect(db)
    try:
        rows = [
            jsonlib.loads(row[0])
            for row in connection.execute(
                "SELECT data FROM workflow_history WHERE run_id = 'auditrun1'"
                " AND type = ?",
                (HistoryEventType.RUN_CANCEL_REQUESTED.value,),
            ).fetchall()
        ]
    finally:
        connection.close()
    assert rows == [{"actor": "alek", "reason": "fat-fingered order"}]


def test_replay_and_audit_commands_account_for_the_operator(tmp_path):
    """`deadletters --replay --reason` writes an audit entry `audit` shows.

    Args:
        tmp_path: Working directory for the database.
    """
    import asyncio
    import subprocess
    import sys

    from reflex.workflow.store import SqliteRunStore

    db = tmp_path / "audit.db"

    async def seed() -> str:
        """Park one delivery.

        Returns:
            Its parked id.
        """
        store = SqliteRunStore(db)
        await store.ingest_channel_delivery(
            "cli.audit", "shipped", "order_1", "evt_1", {"n": 1}, 1_000_000.0
        )
        rows = await store.list_parked()
        store.close()
        return rows[0].parked_id

    parked_id = asyncio.run(seed())
    runner = "from reflex.workflow.cli import workflows; workflows()"
    env = {**__import__("os").environ, "REFLEX_ACTOR": "alek"}
    replay = subprocess.run(
        [
            sys.executable,
            "-c",
            runner,
            "deadletters",
            "--replay",
            parked_id,
            "--reason",
            "carrier back",
            "-d",
            str(db),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert replay.returncode == 1, "still parked: no run for the key yet"
    listing = subprocess.run(
        [sys.executable, "-c", runner, "audit", "-d", str(db)],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert listing.returncode == 0, listing.stderr[-400:]
    assert "alek" in listing.stdout
    assert "replay_parked" in listing.stdout
    assert "carrier back" in listing.stdout


def test_schedules_pause_is_audited_from_the_cli(tmp_path):
    """`schedules pause KEY --reason` writes an audit entry `audit` shows.

    Args:
        tmp_path: Working directory for the database.
    """
    import subprocess
    import sys

    db = tmp_path / "sched.db"
    runner = "from reflex.workflow.cli import workflows; workflows()"
    env = {**__import__("os").environ, "REFLEX_ACTOR": "alek"}
    paused = subprocess.run(
        [
            sys.executable,
            "-c",
            runner,
            "schedules",
            "pause",
            "cli.flow:tick",
            "--reason",
            "vendor outage",
            "-d",
            str(db),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert paused.returncode == 0, paused.stderr[-400:]
    assert "paused" in paused.stdout
    listing = subprocess.run(
        [sys.executable, "-c", runner, "audit", "-d", str(db)],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert "pause_schedule" in listing.stdout
    assert "cli.flow:tick" in listing.stdout
    assert "vendor outage" in listing.stdout
