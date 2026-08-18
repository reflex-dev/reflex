"""The ``reflex workflows`` command group.

Operators reach for a terminal when a run misbehaves, so listing, inspecting,
cancelling, and resuming runs must not require writing a script or opening the
app. These commands read the same store the app writes, so they work against a
running deployment or a stopped one.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import click
from reflex_base.utils import console

from reflex.workflow.records import RunStatus

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from reflex.workflow.store import RunStore

DEFAULT_DB_FILENAME = "workflow.db"


def _open_store(database: str | None) -> RunStore:
    """Open the run store the app persists to.

    Args:
        database: Path to the SQLite database, or None for the default.

    Returns:
        The store.
    """
    from reflex.workflow.store import SqliteRunStore

    return SqliteRunStore(database or DEFAULT_DB_FILENAME)


def _run(coroutine: Awaitable[Any]) -> Any:
    """Run one store coroutine to completion.

    Args:
        coroutine: The coroutine to run.

    Returns:
        Its result.
    """
    return asyncio.run(coroutine)  # pyright: ignore[reportArgumentType]


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
    help="Path to the workflow database. Defaults to ./workflow.db.",
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
    store = _open_store(database)
    try:
        runs = _run(
            store.list_runs(
                RunQuery(
                    workflow_id=workflow,
                    statuses=tuple(RunStatus(value.upper()) for value in statuses),
                    labels=label_filter or None,
                    limit=limit,
                )
            )
        )
    finally:
        _close(store)

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
    store = _open_store(database)
    try:
        run = _run(store.get_run(run_id))
        if run is None:
            console.error(f"No run {run_id!r} in this database.")
            raise click.exceptions.Exit(1)
        steps = _run(store.get_steps(run_id))
        events = _run(store.get_history(run_id)) if history else ()
    finally:
        _close(store)

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

    store = _open_store(database)
    try:
        recorded = _run(store.request_cancel(run_id, time.time()))
    finally:
        _close(store)
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

    store = _open_store(database)
    try:
        resumed = _run(store.resume_run(run_id, time.time()))
    finally:
        _close(store)
    if not resumed:
        console.error(f"Run {run_id!r} is not suspended.")
        raise click.exceptions.Exit(1)
    console.print(f"Resumed {run_id}; its next step will run.")


def _close(store: RunStore) -> None:
    """Close a store that holds a connection.

    Args:
        store: The store to close.
    """
    closer = getattr(store, "close", None)
    if closer is not None:
        closer()
