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
    POLL_SECONDS,
    EventsState,
    FleetState,
    LoginState,
    RunDetailState,
    RunsState,
    _admitted,
    _age,
    _still_on,
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
        await state.load_runs()
        first = list(state.rows)
        state.set_status_filter("COMPLETED")
        await state.load_runs()
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
        await state.act_as(LoginState(), "retry")  # pyright: ignore[reportCallIssue]
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
        await state.load_deliveries()
        assert len(state.rows) == 1
        assert state.rows[0]["key"] == "order_x"
        await state.replay_as(LoginState(), state.rows[0]["parked_id"])  # pyright: ignore[reportCallIssue]
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
        await state.load_fleet()
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


def test_login_accepts_scoped_tokens_and_names_the_principal(monkeypatch):
    """A bound token signs as its principal; an unbound one as the typed name.

    Args:
        monkeypatch: Used to configure tokens.
    """
    monkeypatch.setenv("REFLEX_WORKFLOW_API_TOKEN_READ", "tok-read")
    monkeypatch.setenv("REFLEX_WORKFLOW_API_TOKEN_OPERATE", "tok-ops")
    monkeypatch.setenv("REFLEX_WORKFLOW_API_TOKEN_PRINCIPALS", "alek=tok-ops")

    wrong = LoginState()  # pyright: ignore[reportCallIssue]
    wrong.set_token("nope")
    assert wrong.login() is None
    assert wrong.error == "that token is not recognized"
    assert not wrong.authenticated

    bound = LoginState()  # pyright: ignore[reportCallIssue]
    bound.set_token("tok-ops")
    bound.set_display_name("ignored when bound")
    assert bound.login() is not None, "success redirects to the runs page"
    assert bound.scopes == ["operate"]
    assert bound.name == "alek"
    assert bound.token == "", "the secret is not kept in state after login"

    typed = LoginState()  # pyright: ignore[reportCallIssue]
    typed.set_token("tok-read")
    typed.set_display_name("guest reader")
    typed.login()
    assert typed.scopes == ["read"]
    assert typed.name == "guest reader"


def test_scopes_gate_reads_and_mutations_only_when_tokens_exist(monkeypatch):
    """No tokens means an open console; any token means scopes are enforced.

    Args:
        monkeypatch: Used to configure tokens.
    """
    for var in (
        "REFLEX_WORKFLOW_API_TOKEN",
        "REFLEX_WORKFLOW_API_TOKEN_READ",
        "REFLEX_WORKFLOW_API_TOKEN_OPERATE",
    ):
        monkeypatch.delenv(var, raising=False)
    anonymous = LoginState()  # pyright: ignore[reportCallIssue]
    assert _admitted(anonymous, "read")
    assert _admitted(anonymous, "operate")

    monkeypatch.setenv("REFLEX_WORKFLOW_API_TOKEN_READ", "tok-read")
    assert not _admitted(anonymous, "read"), "a configured token makes login mandatory"
    reader = LoginState()  # pyright: ignore[reportCallIssue]
    reader.set_token("tok-read")
    reader.login()
    assert _admitted(reader, "read")
    assert not _admitted(reader, "operate")


def test_a_read_only_login_cannot_repair(seeded, monkeypatch):
    """The operate scope gates every mutation, with a notice not a crash.

    Args:
        seeded: The seeded database.
        monkeypatch: Used to configure tokens.
    """
    monkeypatch.setenv("REFLEX_WORKFLOW_API_TOKEN_READ", "tok-read")
    reader = LoginState()  # pyright: ignore[reportCallIssue]
    reader.set_token("tok-read")
    reader.login()

    async def drive() -> tuple[str, str, str]:
        """Attempt a retry and a replay as the reader.

        Returns:
            The run's status after the attempt and both notices.
        """
        detail = RunDetailState()  # pyright: ignore[reportCallIssue]
        await detail.load_run("failedrun001")
        await detail.act_as(reader, "retry")
        events = EventsState()  # pyright: ignore[reportCallIssue]
        await events.replay_as(reader, "whatever")
        return detail.status, detail.notice, events.notice

    status, notice, replay_notice = asyncio.run(drive())
    assert status == "FAILED", "nothing changed"
    assert notice == "retry needs the operate scope"
    assert replay_notice == "replay needs the operate scope"


def test_watchers_stop_when_the_browser_leaves_their_page():
    """A page watcher polls only while its page is mounted."""
    assert _still_on("/", "/")
    assert not _still_on("/fleet", "/")
    assert _still_on("/run/abc123", "/run/")
    assert not _still_on("/", "/run/")
    assert _still_on("/events", "/events")
    assert POLL_SECONDS < 5, "faster than a person reads, slower than a busy loop"


def test_every_page_registers_a_live_watcher():
    """Each page state has a watcher and the app still registers with them."""
    for state in (RunsState, RunDetailState, FleetState, EventsState):
        assert hasattr(state, "watch")
    console_app()


def test_console_replays_are_audited_under_the_operators_name(seeded):
    """The console's replay lands in the audit log as the login's name.

    Args:
        seeded: The seeded database.
    """
    from reflex.workflow.console import AuditState

    async def drive() -> tuple[list[dict[str, str]], str]:
        """Replay the parked delivery as a named login, then read the log.

        Returns:
            The audit rows and the replaying login's name.
        """
        login = LoginState()  # pyright: ignore[reportCallIssue]
        login.name = "ops-console"
        events = EventsState()  # pyright: ignore[reportCallIssue]
        events.set_status_filter("PENDING")
        await events.load_deliveries()
        await events.replay_as(login, events.rows[0]["parked_id"])
        audit = AuditState()  # pyright: ignore[reportCallIssue]
        await audit.load_audit()
        return audit.rows, login.name

    rows, name = asyncio.run(drive())
    assert len(rows) == 1
    assert rows[0]["actor"] == name
    assert rows[0]["action"] == "replay_parked"
