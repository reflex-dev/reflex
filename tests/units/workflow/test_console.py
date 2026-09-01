"""The operator console: pages build, and its state layer reads and repairs.

The handlers are driven directly against a seeded SQLite store -- the same
way ``tests/units/test_state.py`` constructs states -- so the console's
logic is tested without a browser, and the one thing a browser would add
(rendering) is covered by building every page's component tree.
"""

import asyncio
import time

import pytest

from reflex.workflow import console as console_module
from reflex.workflow.console import (
    EventsState,
    FleetState,
    RunDetailState,
    RunsState,
    _age,
    console_app,
    events_page,
    fleet_page,
    run_detail_page,
    runs_page,
)
from reflex.workflow.records import (
    HistoryEventType,
    RunRecord,
    RunStatus,
    StepRecord,
    StepStatus,
)
from reflex.workflow.store import SqliteRunStore

NOW = time.time()


@pytest.fixture(autouse=True)
def harness_store():
    """Opt out of the shared store parameter; the console owns its store.

    Returns:
        The store kind this module uses.
    """
    return "sqlite"


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    """A SQLite database the console reads, with one failed run in it.

    Args:
        tmp_path: Temporary directory for the database.
        monkeypatch: Used to point the console at the database.

    Yields:
        The database path.
    """
    db = tmp_path / "console.db"
    monkeypatch.setenv(console_module.CONSOLE_DATABASE_ENV, str(db))
    monkeypatch.setenv("REFLEX_ACTOR", "ops-tester")
    console_module._runtime = None  # pyright: ignore[reportPrivateUsage]

    async def seed() -> None:
        """Write one failed run with a failed step."""
        store = SqliteRunStore(db)
        await store.admit(
            RunRecord(
                run_id="failedrun001",
                workflow_id="console.orders",
                definition_digest="d",
                status=RunStatus.FAILED,
                state={"total": 3},
                state_version=1,
                next_ordinal=1,
                error={"reason": "boom"},
                created_at=NOW - 600,
                updated_at=NOW - 60,
            ),
            StepRecord(
                run_id="failedrun001",
                ordinal=0,
                handler_id="place",
                status=StepStatus.FAILED,
                args={},
                error={"reason": "boom"},
                origin="root",
                created_at=NOW - 600,
                updated_at=NOW - 60,
            ),
            ((HistoryEventType.RUN_ADMITTED, {}),),
        )
        await store.ingest_channel_delivery(
            "console.orders", "shipped", "order_x", "evt_x", {"n": 1}, NOW
        )
        store.close()

    asyncio.run(seed())
    yield db
    asyncio.run(console_module.close_client())


def test_every_page_builds_and_the_app_registers():
    """Component trees build outside a running app, and pages register."""
    for page in (runs_page, run_detail_page, fleet_page, events_page):
        assert page() is not None
    console_app()


def test_age_reads_like_a_human():
    """Ages round to the unit an operator thinks in."""
    assert _age(time.time() - 5).endswith("s")
    assert _age(time.time() - 600).endswith("m")
    assert _age(time.time() - 7200).endswith("h")
    assert _age(time.time() - 3 * 86_400).endswith("d")


def test_runs_page_lists_and_filters(seeded):
    """The runs table shows the failed run, with a status filter that works.

    Args:
        seeded: The seeded database.
    """

    async def drive() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        """Refresh twice, unfiltered then filtered away.

        Returns:
            The rows before and after filtering.
        """
        state = RunsState()  # pyright: ignore[reportCallIssue]
        async for _ in state.refresh():  # pyright: ignore[reportGeneralTypeIssues]
            pass
        first = list(state.rows)
        state.set_status_filter("COMPLETED")
        async for _ in state.refresh():  # pyright: ignore[reportGeneralTypeIssues]
            pass
        return first, list(state.rows)

    unfiltered, filtered = asyncio.run(drive())
    assert [row["run_id"] for row in unfiltered] == ["failedrun001"]
    assert unfiltered[0]["status"] == "FAILED"
    assert unfiltered[0]["color"] == "red"
    assert filtered == []


def test_run_detail_shows_the_story_and_repairs_with_attribution(seeded):
    """Load, then retry with a reason; the history names the operator.

    Args:
        seeded: The seeded database.
    """

    async def drive() -> RunDetailState:
        """Load the run, retry it, reload.

        Returns:
            The state after the retry.
        """
        state = RunDetailState()  # pyright: ignore[reportCallIssue]
        await state.load_run("failedrun001")
        assert state.found
        assert state.status == "FAILED"
        assert state.steps[0]["handler"] == "place"
        assert '"total": 3' in state.state_json
        state.set_reason("vendor is back")
        await state.act("retry")
        return state

    state = asyncio.run(drive())
    assert state.notice == "retry applied"
    assert state.status == "PENDING", "retry re-opened the run"
    resumed = [event for event in state.history if event["type"] == "run_resumed"]
    assert resumed
    assert resumed[0]["actor"] == "ops-tester"
    assert resumed[0]["reason"] == "vendor is back"
    assert state.reason == "", "the reason is consumed by the action"


def test_run_detail_reports_a_missing_run(seeded):
    """An unknown id is a clear absence, not a crash.

    Args:
        seeded: The seeded database.
    """

    async def drive() -> bool:
        """Load a run that does not exist.

        Returns:
            Whether the state says it found one.
        """
        state = RunDetailState()  # pyright: ignore[reportCallIssue]
        await state.load_run("nope")
        return state.found

    assert asyncio.run(drive()) is False


def test_events_page_lists_parked_deliveries_and_replays(seeded):
    """The parked delivery shows under PENDING and replay reports honestly.

    Args:
        seeded: The seeded database.
    """

    async def drive() -> EventsState:
        """List pending deliveries and replay the one there.

        Returns:
            The state after the replay.
        """
        state = EventsState()  # pyright: ignore[reportCallIssue]
        state.set_status_filter("PENDING")
        await state.refresh()
        assert len(state.rows) == 1
        assert state.rows[0]["key"] == "order_x"
        await state.replay(state.rows[0]["parked_id"])
        return state

    state = asyncio.run(drive())
    assert state.notice == "replay: parked", "still no run for that key"


def test_fleet_page_reads_the_registry(seeded):
    """An empty fleet is an empty table, not an error.

    Args:
        seeded: The seeded database.
    """

    async def drive() -> FleetState:
        """Refresh the fleet view.

        Returns:
            The refreshed state.
        """
        state = FleetState()  # pyright: ignore[reportCallIssue]
        await state.refresh()
        return state

    state = asyncio.run(drive())
    assert state.workers == []
    assert state.releases == []


def test_the_cli_materializes_a_runnable_console_project(tmp_path, monkeypatch):
    """`reflex workflows console` writes a project whose app is the console.

    The scaffold is what `reflex run` needs and nothing more; it is
    regenerated each launch so an upgrade never serves stale files.

    Args:
        tmp_path: Where to write the project.
        monkeypatch: Used to intercept the launch.
    """
    import importlib.util

    from click.testing import CliRunner

    from reflex.workflow import cli

    launched: list[tuple] = []
    monkeypatch.setattr(
        cli,
        "_run_console_project",
        lambda root, host, port, env: launched.append((root, host, port, env)),
    )
    result = CliRunner().invoke(
        cli.workflows,
        [
            "console",
            "--project-dir",
            str(tmp_path / "proj"),
            "-d",
            str(tmp_path / "x.db"),
        ],
    )
    assert result.exit_code == 0, result.output
    root, host, port, env = launched[0]
    assert host == "127.0.0.1"
    assert port == 3000
    assert env["REFLEX_WORKFLOW_DATABASE"] == str(tmp_path / "x.db")
    assert (
        (root / "rxconfig.py")
        .read_text()
        .strip()
        .endswith("config = rx.Config(app_name='workflow_console')")
    )
    spec = importlib.util.spec_from_file_location(
        "scaffold", root / "workflow_console" / "workflow_console.py"
    )
    assert spec is not None
    source = (root / "workflow_console" / "workflow_console.py").read_text()
    assert "from reflex.workflow.console import console_app" in source
    assert "app = console_app()" in source
