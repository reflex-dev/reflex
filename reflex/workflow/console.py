"""The operator console: a Reflex app over a workflow store.

``reflex workflows console`` serves four pages — runs, one run's story, the
worker fleet, and channel deliveries — so an operator finds and resolves a
stuck run without SQL or the CLI. Every mutation goes through the same
kernel operations the CLI uses, carries the operator's name and reason, and
therefore lands in the run's own history.

The console is a read-and-repair surface, never a worker: its runtime opens
the store without claiming anything, exactly like ``rx.workflows.connect``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from typing import TYPE_CHECKING, Any, ClassVar

import reflex as rx
from reflex.workflow.records import (
    TERMINAL_RUN_STATUSES,
    ParkedStatus,
    RunQuery,
    RunStatus,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from reflex.workflow.runtime import WorkflowRuntime

CONSOLE_DATABASE_ENV = "REFLEX_WORKFLOW_DATABASE"

_runtime: WorkflowRuntime | None = None
_runtime_lock = asyncio.Lock()


async def _client() -> WorkflowRuntime:
    """Open (once) the client runtime the console reads and repairs through.

    Two pages loading at once must not each open a store: the lock makes the
    first opener the only opener, so the process holds one pool.

    Returns:
        The started, worker-less runtime.
    """
    global _runtime
    async with _runtime_lock:
        if _runtime is None:
            from reflex.workflow.runtime import WorkflowRuntime
            from reflex.workflow.store import resolve_store

            runtime = WorkflowRuntime(
                resolve_store(os.environ.get(CONSOLE_DATABASE_ENV))
            )
            await runtime.startup(start_worker=False)
            _runtime = runtime
    return _runtime


async def close_client() -> None:
    """Release the console's store, for the app's shutdown."""
    global _runtime
    async with _runtime_lock:
        if _runtime is not None:
            from reflex.workflow.runtime import _close_store

            await _runtime.shutdown()
            await _close_store(_runtime.store)
            _runtime = None


def _actor() -> str:
    """Who is operating this console, as recorded in run histories.

    Returns:
        The operator identity.
    """
    import getpass

    try:
        return os.environ.get("REFLEX_ACTOR") or getpass.getuser()
    except (KeyError, OSError):
        # A container uid with no passwd entry has no name to give.
        return "console"


def _age(then: float) -> str:
    """Render how long ago a timestamp was.

    Args:
        then: Epoch seconds.

    Returns:
        A short human age.
    """
    seconds = max(0.0, time.time() - then)
    if seconds < 90:
        return f"{seconds:.0f}s"
    if seconds < 5400:
        return f"{seconds / 60:.0f}m"
    if seconds < 129_600:
        return f"{seconds / 3600:.0f}h"
    return f"{seconds / 86_400:.0f}d"


STATUS_COLORS: dict[str, str] = {
    "PENDING": "gray",
    "RUNNING": "blue",
    "WAITING": "cyan",
    "NEEDS_ATTENTION": "amber",
    "COMPLETED": "green",
    "FAILED": "red",
    "CANCELLING": "orange",
    "CANCELLED": "orange",
    "TIMED_OUT": "red",
}


class RunsState(rx.State):
    """The runs page: list, filter, and jump into a run."""

    rows: list[dict[str, str]] = []
    workflow_filter: str = ""
    status_filter: str = ""
    loading: bool = False

    @rx.event
    async def refresh(self):
        """Load runs matching the current filters."""
        self.loading = True
        yield
        runtime = await _client()
        statuses = ()
        if self.status_filter:
            statuses = (RunStatus(self.status_filter),)
        runs = await runtime.kernel._store.list_runs(
            RunQuery(
                workflow_id=self.workflow_filter or None,
                statuses=statuses,
                limit=200,
            )
        )
        self.rows = [
            {
                "run_id": run.run_id,
                "short_id": run.run_id[:12],
                "workflow": run.workflow_id,
                "status": run.status.value,
                "color": STATUS_COLORS.get(run.status.value, "gray"),
                "release": run.release_id or "-",
                "age": _age(run.created_at),
                "updated": _age(run.updated_at),
            }
            for run in runs
        ]
        self.loading = False

    @rx.event
    def set_workflow_filter(self, value: str):
        """Set the workflow filter.

        Args:
            value: The workflow id substring.
        """
        self.workflow_filter = value

    @rx.event
    def set_status_filter(self, value: str):
        """Set the status filter.

        Args:
            value: The status value, or empty for all.
        """
        self.status_filter = "" if value == "all" else value


class RunDetailState(rx.State):
    """One run's whole story, and the levers to repair it."""

    run: str = ""
    found: bool = False
    workflow_id: str = ""
    status: str = ""
    color: str = "gray"
    release: str = ""
    state_json: str = ""
    result_json: str = ""
    error_json: str = ""
    steps: list[dict[str, str]] = []
    history: list[dict[str, str]] = []
    children: list[dict[str, str]] = []
    reason: str = ""
    notice: str = ""

    _actions: ClassVar[dict[str, str]] = {
        "cancel": "cancel",
        "retry": "retry",
        "skip": "skip",
        "resume": "resume",
    }

    @rx.event
    async def load(self):
        """Load the run named by the page's path parameter.

        ``run_id`` is the dynamic route argument. The framework exposes it on
        the state itself, so a declared field of that name would shadow it
        and is refused at page registration; it is read from the router and
        kept under ``run`` instead.
        """
        await self.load_run(self.router.page.params.get("run_id", ""))

    @rx.event
    async def load_run(self, run_id: str):
        """Load one run's story.

        Args:
            run_id: The run to show.
        """
        self.run = run_id
        runtime = await _client()
        snapshot = await runtime.kernel.get_run(self.run)
        if snapshot is None:
            self.found = False
            return
        self.found = True
        self.workflow_id = snapshot.workflow_id
        self.status = snapshot.status.value
        self.color = STATUS_COLORS.get(snapshot.status.value, "gray")
        self.release = snapshot.release_id or "-"
        self.state_json = json.dumps(snapshot.state, indent=2, default=str)
        self.result_json = (
            json.dumps(snapshot.result, indent=2, default=str)
            if snapshot.result is not None
            else ""
        )
        self.error_json = (
            json.dumps(snapshot.error, indent=2, default=str) if snapshot.error else ""
        )
        self.steps = [
            {
                "ordinal": str(step.ordinal),
                "handler": step.handler_id,
                "status": step.status.value,
                "color": STATUS_COLORS.get(step.status.value, "gray"),
                "attempts": str(step.attempts),
                "error": json.dumps(step.error, default=str) if step.error else "",
            }
            for step in snapshot.steps
        ]
        store = runtime.kernel._store
        events = await store.get_history(self.run)
        self.history = [
            {
                "type": event.type.value,
                "at": _age(event.at) + " ago",
                "actor": str(event.data.get("actor", "")),
                "reason": str(event.data.get("reason", "")),
                "data": json.dumps(
                    {
                        key: value
                        for key, value in event.data.items()
                        if key not in ("actor", "reason")
                    },
                    default=str,
                ),
            }
            for event in events
        ]
        kids: tuple = ()
        for step in snapshot.steps:
            # Children hang off join slots; the snapshot already names them.
            if step.origin == "join":
                kids = (*kids, *await store.list_children(self.run, step.ordinal))
        self.children = [
            {
                "run_id": kid.run_id,
                "short_id": kid.run_id[:12],
                "status": kid.status.value,
                "color": STATUS_COLORS.get(kid.status.value, "gray"),
            }
            for kid in kids
        ]

    @rx.event
    def set_reason(self, value: str):
        """Record the operator's reason for the next action.

        Args:
            value: The reason text.
        """
        self.reason = value

    @rx.event
    async def act(self, action: str):
        """Apply one operator action to this run, attributed.

        Args:
            action: One of cancel, retry, skip, or resume.
        """
        method = self._actions.get(action)
        if method is None:
            return
        runtime = await _client()
        applied = await getattr(runtime.kernel, method)(
            self.run, actor=_actor(), reason=self.reason or None
        )
        self.notice = (
            f"{action} applied"
            if applied
            else f"run does not accept {action} in its current state"
        )
        self.reason = ""
        await self.load_run(self.run)


class FleetState(rx.State):
    """Workers, their releases, and what each release still owns."""

    workers: list[dict[str, str]] = []
    releases: list[dict[str, str]] = []

    @rx.event
    async def refresh(self):
        """Load the registry and per-release active counts."""
        runtime = await _client()
        store = runtime.kernel._store
        registered = await store.list_workers()
        self.workers = [
            {
                "worker_id": worker.worker_id[:12],
                "release": worker.release_id or "-",
                "queues": ", ".join(worker.queues) or "all",
                "capacity": str(worker.capacity),
                "heartbeat": _age(worker.heartbeat_at) + " ago",
            }
            for worker in registered
        ]
        active = tuple(s for s in RunStatus if s not in TERMINAL_RUN_STATUSES)
        names = sorted({w.release_id for w in registered if w.release_id is not None})
        self.releases = [
            {
                "release": name,
                "active": str(
                    await store.count_runs(RunQuery(release_id=name, statuses=active))
                ),
            }
            for name in names
        ]


class EventsState(rx.State):
    """Channel deliveries: parked, delivered, and dead letters to replay."""

    rows: list[dict[str, str]] = []
    status_filter: str = "DEAD"
    notice: str = ""

    @rx.event
    async def refresh(self):
        """Load deliveries in the selected state."""
        runtime = await _client()
        store = runtime.kernel._store
        chosen = (
            None if self.status_filter == "all" else ParkedStatus(self.status_filter)
        )
        rows = await store.list_parked(status=chosen)
        self.rows = [
            {
                "parked_id": row.parked_id,
                "short_id": row.parked_id[:12],
                "workflow": row.workflow_id,
                "channel": row.channel,
                "key": row.correlation_key,
                "status": row.status.value,
                "reason": row.reason or "",
                "age": _age(row.created_at),
            }
            for row in rows
        ]

    @rx.event
    def set_status_filter(self, value: str):
        """Set the delivery-state filter.

        Args:
            value: PENDING, DELIVERED, DEAD, or all.
        """
        self.status_filter = value

    @rx.event
    async def replay(self, parked_id: str):
        """Route one delivery again, with the same event-id idempotency.

        Args:
            parked_id: The delivery to replay.
        """
        runtime = await _client()
        store = runtime.kernel._store
        disposition = await store.replay_parked(parked_id, time.time())
        self.notice = f"replay: {disposition}"
        await self.refresh()


def _shell(*children: Any) -> rx.Component:
    """Wrap a page in the console chrome.

    Args:
        children: The page content.

    Returns:
        The framed page.
    """
    return rx.container(
        rx.hstack(
            rx.heading("Workflows", size="5"),
            rx.spacer(),
            rx.link("Runs", href="/"),
            rx.link("Fleet", href="/fleet"),
            rx.link("Events", href="/events"),
            spacing="4",
            align="center",
            padding_y="12px",
        ),
        *children,
        size="4",
    )


def _status_badge(value: Any, color: Any) -> rx.Component:
    """Render a status as a colored badge.

    Args:
        value: The status text.
        color: The badge color.

    Returns:
        The badge.
    """
    return rx.badge(value, color_scheme=color)  # pyright: ignore[reportArgumentType]


def runs_page() -> rx.Component:
    """The runs listing page.

    Returns:
        The page component.
    """
    return _shell(
        rx.hstack(
            rx.input(
                placeholder="workflow id",
                on_change=RunsState.set_workflow_filter,
                width="240px",
            ),
            rx.select(
                ["all", *[status.value for status in RunStatus]],
                default_value="all",
                on_change=RunsState.set_status_filter,
            ),
            rx.button("Refresh", on_click=RunsState.refresh, loading=RunsState.loading),
            spacing="3",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("run"),
                    rx.table.column_header_cell("workflow"),
                    rx.table.column_header_cell("status"),
                    rx.table.column_header_cell("release"),
                    rx.table.column_header_cell("age"),
                    rx.table.column_header_cell("updated"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    RunsState.rows,
                    lambda row: rx.table.row(
                        rx.table.cell(
                            rx.link(row["short_id"], href="/run/" + row["run_id"])
                        ),
                        rx.table.cell(row["workflow"]),
                        rx.table.cell(_status_badge(row["status"], row["color"])),
                        rx.table.cell(row["release"]),
                        rx.table.cell(row["age"]),
                        rx.table.cell(row["updated"]),
                    ),
                )
            ),
            width="100%",
        ),
    )


def run_detail_page() -> rx.Component:
    """One run's story and its repair actions.

    Returns:
        The page component.
    """
    action_button = lambda label: rx.button(  # noqa: E731
        label.title(), on_click=RunDetailState.act(label), variant="soft"
    )
    return _shell(
        rx.cond(
            RunDetailState.found,
            rx.vstack(
                rx.hstack(
                    rx.heading(RunDetailState.run, size="4"),
                    _status_badge(RunDetailState.status, RunDetailState.color),
                    rx.text(RunDetailState.workflow_id),
                    rx.text("release: " + RunDetailState.release),
                    spacing="3",
                    align="center",
                ),
                rx.hstack(
                    rx.input(
                        placeholder="reason (recorded in history)",
                        value=RunDetailState.reason,
                        on_change=RunDetailState.set_reason,
                        width="320px",
                    ),
                    action_button("cancel"),
                    action_button("retry"),
                    action_button("skip"),
                    action_button("resume"),
                    rx.text(RunDetailState.notice, color_scheme="gray"),
                    spacing="2",
                ),
                rx.heading("Steps", size="3"),
                rx.table.root(
                    rx.table.body(
                        rx.foreach(
                            RunDetailState.steps,
                            lambda step: rx.table.row(
                                rx.table.cell(step["ordinal"]),
                                rx.table.cell(step["handler"]),
                                rx.table.cell(
                                    _status_badge(step["status"], step["color"])
                                ),
                                rx.table.cell("attempts: " + step["attempts"]),
                                rx.table.cell(step["error"]),
                            ),
                        )
                    ),
                    width="100%",
                ),
                rx.heading("State", size="3"),
                rx.code_block(RunDetailState.state_json, language="json"),
                rx.cond(
                    RunDetailState.result_json != "",
                    rx.vstack(
                        rx.heading("Result", size="3"),
                        rx.code_block(RunDetailState.result_json, language="json"),
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    RunDetailState.error_json != "",
                    rx.vstack(
                        rx.heading("Error", size="3"),
                        rx.code_block(RunDetailState.error_json, language="json"),
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    RunDetailState.children.length() > 0,  # pyright: ignore[reportAttributeAccessIssue]
                    rx.vstack(
                        rx.heading("Children", size="3"),
                        rx.foreach(
                            RunDetailState.children,
                            lambda kid: rx.hstack(
                                rx.link(kid["short_id"], href="/run/" + kid["run_id"]),
                                _status_badge(kid["status"], kid["color"]),
                                spacing="2",
                            ),
                        ),
                    ),
                    rx.fragment(),
                ),
                rx.heading("History", size="3"),
                rx.table.root(
                    rx.table.body(
                        rx.foreach(
                            RunDetailState.history,
                            lambda event: rx.table.row(
                                rx.table.cell(event["type"]),
                                rx.table.cell(event["at"]),
                                rx.table.cell(event["actor"]),
                                rx.table.cell(event["reason"]),
                                rx.table.cell(event["data"]),
                            ),
                        )
                    ),
                    width="100%",
                ),
                width="100%",
                spacing="4",
            ),
            rx.text("No such run."),
        ),
    )


def fleet_page() -> rx.Component:
    """Workers and releases.

    Returns:
        The page component.
    """
    return _shell(
        rx.button("Refresh", on_click=FleetState.refresh),
        rx.heading("Workers", size="3"),
        rx.table.root(
            rx.table.body(
                rx.foreach(
                    FleetState.workers,
                    lambda worker: rx.table.row(
                        rx.table.cell(worker["worker_id"]),
                        rx.table.cell("release: " + worker["release"]),
                        rx.table.cell(worker["queues"]),
                        rx.table.cell("capacity: " + worker["capacity"]),
                        rx.table.cell(worker["heartbeat"]),
                    ),
                )
            ),
            width="100%",
        ),
        rx.heading("Releases", size="3"),
        rx.foreach(
            FleetState.releases,
            lambda release: rx.text(
                release["release"] + ": " + release["active"] + " active run(s)"
            ),
        ),
    )


def events_page() -> rx.Component:
    """Channel deliveries and dead letters.

    Returns:
        The page component.
    """
    return _shell(
        rx.hstack(
            rx.select(
                ["DEAD", "PENDING", "DELIVERED", "all"],
                default_value="DEAD",
                on_change=EventsState.set_status_filter,
            ),
            rx.button("Refresh", on_click=EventsState.refresh),
            rx.text(EventsState.notice, color_scheme="gray"),
            spacing="3",
        ),
        rx.table.root(
            rx.table.body(
                rx.foreach(
                    EventsState.rows,
                    lambda row: rx.table.row(
                        rx.table.cell(row["short_id"]),
                        rx.table.cell(row["workflow"] + "." + row["channel"]),
                        rx.table.cell("key: " + row["key"]),
                        rx.table.cell(row["status"]),
                        rx.table.cell(row["reason"]),
                        rx.table.cell(row["age"]),
                        rx.table.cell(
                            rx.button(
                                "Replay",
                                on_click=EventsState.replay(row["parked_id"]),
                                size="1",
                                variant="soft",
                            )
                        ),
                    ),
                )
            ),
            width="100%",
        ),
    )


def console_app() -> rx.App:
    """Build the operator console application.

    Returns:
        The Reflex app serving the four console pages.
    """
    app = rx.App()

    @contextlib.asynccontextmanager
    async def hold_client_open() -> AsyncIterator[None]:
        """Keep the store open for the app's life and close it on shutdown.

        Yields:
            Control back to the app while it serves.
        """
        try:
            yield
        finally:
            await close_client()

    app.register_lifespan_task(hold_client_open)
    app.add_page(runs_page, route="/", on_load=RunsState.refresh, title="Runs")
    app.add_page(
        run_detail_page,
        route="/run/[run_id]",
        on_load=RunDetailState.load,
        title="Run",
    )
    app.add_page(fleet_page, route="/fleet", on_load=FleetState.refresh, title="Fleet")
    app.add_page(
        events_page, route="/events", on_load=EventsState.refresh, title="Events"
    )
    return app
