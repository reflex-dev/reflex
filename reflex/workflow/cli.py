"""The ``reflex workflows`` command group.

Operators reach for a terminal when a run misbehaves, so listing, inspecting,
cancelling, and resuming runs must not require writing a script or opening the
app. These commands read the same store the app writes, so they work against a
running deployment or a stopped one.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
from typing import TYPE_CHECKING, Any

import click
from reflex_base.utils import console

from reflex.workflow.records import RunStatus

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from reflex.workflow.store import RunStore

DEFAULT_DB_FILENAME = "workflow.db"


def _open_store(database: str | None) -> RunStore:
    """Open the run store the app persists to.

    A ``postgres://`` or ``postgresql://`` target opens the Postgres store;
    anything else is a path to a SQLite file.

    Args:
        database: Connection URL or SQLite path, or None for the default.

    Returns:
        The store.
    """
    target = database or os.environ.get("REFLEX_WORKFLOW_DATABASE")
    if target is not None and target.startswith(("postgres://", "postgresql://")):
        from reflex.workflow.postgres import PostgresRunStore

        return PostgresRunStore(target)

    from reflex.workflow.store import SqliteRunStore

    return SqliteRunStore(target or DEFAULT_DB_FILENAME)


def _with_store(database: str | None, work: Callable[[RunStore], Awaitable[Any]]):
    """Open a store, run one unit of work against it, and close it.

    Everything happens inside a single event loop. A pooled store binds its
    connections to the loop that opened them, so a command that ran each query
    in its own ``asyncio.run`` would fail on close, and the failure would only
    appear against Postgres.

    Args:
        database: Connection URL or SQLite path, or None for the default.
        work: What to do with the open store.

    Returns:
        Whatever the work returned.
    """

    async def session() -> Any:
        """Open the store, do the work, and close it.

        Returns:
            The work's result.
        """
        store = _open_store(database)
        try:
            return await work(store)
        finally:
            closer = getattr(store, "close", None)
            if closer is not None:
                closed = closer()
                if inspect.isawaitable(closed):
                    await closed

    return asyncio.run(session())


def _age(seconds: float) -> str:
    """Render an age compactly.

    Args:
        seconds: How long ago, in seconds.

    Returns:
        A short human-readable age.
    """
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return f"{int(seconds // size)}{unit}"
    return f"{int(seconds)}s"


database_option = click.option(
    "--database",
    "-d",
    default=None,
    help=(
        "Workflow database: a Postgres URL, or a path to a SQLite file. "
        "Defaults to $REFLEX_WORKFLOW_DATABASE, then ./workflow.db."
    ),
)


@click.group()
def workflows():
    """Inspect and steer durable workflow runs."""


@workflows.command("list")
@database_option
@click.option("--workflow", "-w", default=None, help="Only this workflow id.")
@click.option(
    "--status",
    "-s",
    "statuses",
    multiple=True,
    type=click.Choice([status.value for status in RunStatus], case_sensitive=False),
    help="Only these run statuses. Repeatable.",
)
@click.option("--label", "-l", "labels", multiple=True, help="Filter as key=value.")
@click.option("--limit", "-n", default=20, show_default=True, help="Rows to show.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of a table.")
def list_runs(
    database: str | None,
    workflow: str | None,
    statuses: tuple[str, ...],
    labels: tuple[str, ...],
    limit: int,
    as_json: bool,
):
    """List runs, newest first."""
    from reflex.workflow.records import RunQuery

    label_filter = dict(pair.split("=", 1) for pair in labels if "=" in pair)
    query = RunQuery(
        workflow_id=workflow,
        statuses=tuple(RunStatus(value.upper()) for value in statuses),
        labels=label_filter or None,
        limit=limit,
    )
    runs = _with_store(database, lambda store: store.list_runs(query))

    if as_json:
        click.echo(
            json.dumps(
                [
                    {
                        "run_id": run.run_id,
                        "workflow_id": run.workflow_id,
                        "status": run.status.value,
                        "labels": run.labels,
                        "created_at": run.created_at,
                    }
                    for run in runs
                ],
                indent=2,
            )
        )
        return
    if not runs:
        console.print("No runs matched.")
        return
    newest = max(run.created_at for run in runs)
    click.echo(f"{'RUN':34}{'WORKFLOW':28}{'STATUS':17}AGE")
    for run in runs:
        click.echo(
            f"{run.run_id:34}{run.workflow_id:28}{run.status.value:17}"
            f"{_age(newest - run.created_at)}"
        )


@workflows.command()
@database_option
@click.argument("run_id")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of a table.")
@click.option("--history", is_flag=True, help="Include the run's history.")
def show(database: str | None, run_id: str, as_json: bool, history: bool):
    """Show one run's state, steps, and optionally its history."""

    async def load(store: RunStore):
        """Read the run, its slots, and optionally its history.

        Args:
            store: The open run store.

        Returns:
            The run, its steps, and its history events.
        """
        return (
            await store.get_run(run_id),
            await store.get_steps(run_id),
            await store.get_history(run_id) if history else (),
        )

    run, steps, events = _with_store(database, load)
    if run is None:
        console.error(f"No run {run_id!r} in this database.")
        raise click.exceptions.Exit(1)

    if as_json:
        click.echo(
            json.dumps(
                {
                    "run_id": run.run_id,
                    "workflow_id": run.workflow_id,
                    "status": run.status.value,
                    "state": run.state,
                    "result": run.result,
                    "error": run.error,
                    "steps": [
                        {
                            "ordinal": step.ordinal,
                            "handler_id": step.handler_id,
                            "status": step.status.value,
                            "attempts": step.attempts,
                            "recoveries": step.recoveries,
                        }
                        for step in steps
                    ],
                    "history": [
                        {"seq": event.seq, "type": event.type.value, "at": event.at}
                        for event in events
                    ],
                },
                indent=2,
                default=str,
            )
        )
        return

    click.echo(f"run      {run.run_id}")
    click.echo(f"workflow {run.workflow_id}")
    click.echo(f"status   {run.status.value}")
    if run.result is not None:
        click.echo(f"result   {run.result}")
    if run.error is not None:
        click.echo(f"error    {run.error}")
    click.echo(f"state    {run.state}")
    click.echo("")
    click.echo(f"{'#':<4}{'HANDLER':28}{'STATUS':17}ATTEMPTS")
    for step in steps:
        attempts = f"{step.attempts}"
        if step.recoveries:
            attempts += f" (+{step.recoveries} recovered)"
        click.echo(
            f"{step.ordinal:<4}{step.handler_id:28}{step.status.value:17}{attempts}"
        )
    if history:
        click.echo("")
        for event in events:
            click.echo(f"{event.seq:<4}{event.type.value}")


@workflows.command()
@database_option
@click.argument("run_id")
def cancel(database: str | None, run_id: str):
    """Request cancellation of a run.

    The running worker finalizes it; if no worker is running, it is cancelled
    the next time one starts.
    """
    import time

    recorded = _with_store(
        database, lambda store: store.request_cancel(run_id, time.time())
    )
    if not recorded:
        console.error(f"Run {run_id!r} is unknown or already finished.")
        raise click.exceptions.Exit(1)
    console.print(f"Cancellation requested for {run_id}.")


@workflows.command()
@database_option
@click.argument("run_id")
def resume(database: str | None, run_id: str):
    """Re-open a run suspended for operator attention."""
    import time

    resumed = _with_store(database, lambda store: store.resume_run(run_id, time.time()))
    if not resumed:
        console.error(f"Run {run_id!r} is not suspended.")
        raise click.exceptions.Exit(1)
    console.print(f"Resumed {run_id}; its next step will run.")
