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
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from reflex_base.utils import console

from reflex.workflow.records import RunStatus

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable

    from reflex.workflow.definition import WorkflowDefinition
    from reflex.workflow.store import RunStore


def webhook_root_names(definitions: Iterable[WorkflowDefinition]) -> list[str]:
    """Name the roots that can only be started by an HTTP delivery.

    A worker process serves no HTTP, so these are exactly the workflows it can
    execute but never begin.

    Args:
        definitions: The compiled workflow definitions being served.

    Returns:
        Sorted "workflow_id.handler" names, empty when none are webhook roots.
    """
    return sorted(
        f"{definition.workflow_id}.{handler.name}"
        for definition in definitions
        for handler in definition.handlers.values()
        if getattr(handler.trigger, "kind", None) == "webhook"
    )


def _operator_action(database: str | None, run_id: str, action: str, **extra):
    """Apply one operator action to a run, reporting what happened.

    Args:
        database: Connection URL or SQLite path, or None for the default.
        run_id: The run to act on.
        action: The store method to call.
        extra: Extra keyword arguments for the store method.

    Raises:
        Exit: When the run was not in a state the action allows.
    """
    import time

    applied = _with_store(
        database,
        lambda store: getattr(store, action)(run_id, time.time(), **extra),
    )
    if not applied:
        console.error(
            f"Run {run_id!r} is not in a state that allows {action.split('_')[0]!r}."
        )
        raise click.exceptions.Exit(1)
    console.print(f"Applied {action.split('_')[0]} to {run_id}.")


def _open_store(database: str | None) -> RunStore:
    """Open the run store the app persists to.

    Args:
        database: Connection URL or SQLite path, or None to resolve the same
            way the app does: ``REFLEX_WORKFLOW_DATABASE``, then the local
            default file.

    Returns:
        The store.
    """
    from reflex.workflow.store import resolve_store

    return resolve_store(database)


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


def _terminal_events() -> frozenset:
    """The history events that mean a run has stopped for good.

    Returns:
        The terminal event types.
    """
    from reflex.workflow.records import HistoryEventType

    return frozenset((
        HistoryEventType.RUN_COMPLETED,
        HistoryEventType.RUN_FAILED,
        HistoryEventType.RUN_CANCELLED,
        HistoryEventType.RUN_TIMED_OUT,
        HistoryEventType.RUN_NEEDS_ATTENTION,
    ))


@click.group()
def workflows():
    """Inspect and steer durable workflow runs."""


_SCAFFOLD = '''"""A durable workflow.

Run it:

    reflex workflows dev {module}.py {klass}.start --arg order=ord-1

Serve it as a background worker:

    reflex workflows worker {module}.py

Point it at Postgres for more than one worker:

    REFLEX_WORKFLOW_DATABASE=postgresql://... reflex workflows worker {module}.py
"""

import reflex as rx


def charge_card(order: str) -> dict:
    """Stand in for a real call to a payment provider.

    Args:
        order: The order being charged.

    Returns:
        The provider's response.
    """
    return {{"charge_id": f"ch_{{order}}"}}


class {klass}(rx.State):
    """Charges an order, then follows up a day later."""

    __workflow__ = rx.WorkflowConfig(id="{workflow_id}")

    order: str = ""
    charge_id: str = ""

    @rx.event(
        durable=True,
        trigger=rx.manual(),
        effect="idempotent_write",
        retry=rx.Retry(max_attempts=5),
    )
    async def start(self, order: str):
        """Charge the order, then wait a day before following up.

        Args:
            order: The order to charge.

        Returns:
            The next step, due tomorrow.
        """
        self.order = order
        # rx.step records its result, so a retry of this handler replays the
        # charge instead of making it twice.
        charge = await rx.step("charge", charge_card, order)
        self.charge_id = charge["charge_id"]
        return rx.after("1d", {klass}.follow_up)

    @rx.event(durable=True, effect="idempotent_write")
    def follow_up(self):
        """Run a day after the charge, whatever happened in between.

        Returns:
            Completion.
        """
        return rx.complete(result={{"order": self.order, "charge": self.charge_id}})
'''


@workflows.command("init")
@click.argument("name", default="workflows")
def init_workflow(name: str):
    """Write a runnable workflow module to NAME.py and say what to do next.

    The workflow-only starting point: one file, no app, no frontend, nothing
    to configure. It uses the pieces worth knowing on the first day -- a
    durable step, a recorded side effect, a retry policy, and a timer that
    survives restarts -- and the commands printed afterwards run it.
    """
    module = Path(f"{name}.py")
    if module.exists():
        console.error(f"{module} already exists; choose another name.")
        raise click.exceptions.Exit(1)

    stem = module.stem.replace("-", "_")
    klass = "".join(part.title() for part in stem.split("_")) or "Orders"
    module.write_text(
        _SCAFFOLD.format(
            module=stem, klass=klass, workflow_id=f"{stem}.{klass.lower()}"
        )
    )
    console.print(f"Wrote {module}.")
    console.print("")
    console.print("Run it once, watching every step:")
    console.print(f"    reflex workflows dev {module} {klass}.start --arg order=ord-1")
    console.print("")
    console.print("Or serve it as a worker and start runs from your own code:")
    console.print(f"    reflex workflows worker {module}")


@workflows.command()
@database_option
@click.argument("target")
@click.argument("start", required=False)
@click.option(
    "--arg",
    "args",
    multiple=True,
    help="Argument for the started handler, as name=value. Repeatable.",
)
def dev(database: str | None, target: str, start: str | None, args: tuple[str, ...]):
    """Run TARGET's workflows in the foreground, printing every transition.

    The loop for building a workflow: start one, watch each step, attempt,
    retry and wait as it happens, and stop when the run ends. Pass START as
    the handler to launch (`Workflow.handler`), with --arg name=value for its
    payload; without it, this just serves and reports whatever arrives.

    Timers are real here. Use WorkflowTestHarness to skip days instantly.
    """
    import asyncio

    from reflex_base.utils.exceptions import WorkflowDefinitionError

    from reflex.workflow.kernel import WorkflowObserver
    from reflex.workflow.records import HistoryEventType
    from reflex.workflow.runtime import WorkflowRuntime
    from reflex.workflow.runtime import workflows as rx_workflows
    from reflex.workflow.store import resolve_store

    try:
        module = _load_module(target)
    except Exception as err:
        console.error(f"Could not load {target!r}: {err}")
        raise click.exceptions.Exit(1) from None

    classes = {
        name: value
        for name, value in vars(module).items()
        if isinstance(value, type) and "__workflow__" in vars(value)
    }
    if not classes:
        console.error(f"No workflow classes in {target!r}.")
        raise click.exceptions.Exit(1)

    finished = asyncio.Event()

    class Narrator(WorkflowObserver):
        """Prints every transition as it is recorded."""

        def on_event(
            self,
            event_type: HistoryEventType,
            run_id: str,
            workflow_id: str,
            data: dict[str, Any],
        ) -> None:
            """Print one transition.

            Args:
                event_type: What happened.
                run_id: The run it happened to.
                workflow_id: That run's workflow identity.
                data: The event payload.
            """
            detail = " ".join(
                f"{key}={value!r}"
                for key, value in data.items()
                if key not in ("error", "traceback")
            )
            click.echo(f"  {run_id[:8]} {event_type.value:<22}{detail}")
            if "error" in data and isinstance(data["error"], dict):
                click.echo(f"           {data['error'].get('message', data['error'])}")
            if event_type in _terminal_events():
                finished.set()

    async def serve() -> None:
        """Run the kernel until the started run ends, or forever."""
        runtime = WorkflowRuntime(resolve_store(database), observer=Narrator())
        try:
            for workflow_cls in classes.values():
                runtime.register(workflow_cls)
        except WorkflowDefinitionError as err:
            console.error(f"Cannot serve {target!r}: {err}")
            raise click.exceptions.Exit(1) from None

        async with runtime.running():
            if start is None:
                console.print("Serving; nothing started. Ctrl-C to stop.")
                await asyncio.Event().wait()
                return
            class_name, _, handler_name = start.partition(".")
            workflow_cls = classes.get(class_name)
            if workflow_cls is None or not handler_name:
                console.error(
                    f"{start!r} is not Workflow.handler; available: "
                    f"{', '.join(sorted(classes))}."
                )
                raise click.exceptions.Exit(1)
            payload = dict(pair.split("=", 1) for pair in args if "=" in pair)
            spec = getattr(workflow_cls, handler_name)
            handle = await rx_workflows.submit(spec(**payload) if payload else spec)
            console.print(f"Started {handle.run_id} ({handle.disposition}).")
            await finished.wait()
            snapshot = await handle.snapshot()
            if snapshot is not None:
                console.print(f"Run {snapshot.status.value}: {snapshot.result}")

    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        console.print("Stopped.")


@workflows.command()
@database_option
@click.argument("target")
@click.option(
    "--queue",
    "queues",
    multiple=True,
    help="Serve only these queues. Repeatable; default serves every queue.",
)
@click.option("--concurrency", default=None, type=int, help="Attempts to run at once.")
def worker(
    database: str | None,
    target: str,
    queues: tuple[str, ...],
    concurrency: int | None,
):
    """Run workflows from TARGET with no frontend and no web server.

    TARGET is a Python file or dotted module defining workflow classes. This
    is the deployment shape for a background worker: a plain process that
    claims steps from the shared store and executes them. Scale by starting
    more of them, and narrow what a process takes with --queue.

    The workflows do not have to live in a Reflex app -- a module importable
    from a FastAPI service, a Django project, or a bare script works, because
    a worker needs only the definitions and the store.
    """
    import asyncio

    from reflex_base.utils.exceptions import WorkflowDefinitionError

    from reflex.workflow.runtime import WorkflowRuntime

    try:
        module = _load_module(target)
    except Exception as err:
        console.error(f"Could not load {target!r}: {err}")
        raise click.exceptions.Exit(1) from None

    classes = [
        value
        for value in vars(module).values()
        if isinstance(value, type) and "__workflow__" in vars(value)
    ]
    if not classes:
        console.error(
            f"No workflow classes in {target!r}. A workflow is an rx.State "
            "subclass with __workflow__ = rx.WorkflowConfig(id=...)."
        )
        raise click.exceptions.Exit(1)

    async def serve() -> None:
        """Run the kernel until interrupted."""
        from reflex.workflow.kernel import DEFAULT_MAX_CONCURRENCY
        from reflex.workflow.store import resolve_store

        runtime = WorkflowRuntime(
            resolve_store(database),
            queues=queues or None,
            max_concurrency=concurrency or DEFAULT_MAX_CONCURRENCY,
        )
        try:
            for workflow_cls in classes:
                runtime.register(workflow_cls)
        except WorkflowDefinitionError as err:
            # The compiler's message names the fix; a traceback out of a
            # worker's startup names only the compiler. Refusing to start at
            # all beats serving a half-registered set, where the workflows
            # that did compile run and the rest vanish silently.
            console.error(f"Cannot serve {target!r}: {err}")
            raise click.exceptions.Exit(1) from None
        served = ", ".join(sorted(d.workflow_id for d in runtime.definitions))
        console.print(
            f"Serving {served} on "
            f"{'queues ' + ', '.join(queues) if queues else 'every queue'}."
        )
        webhook_roots = webhook_root_names(runtime.definitions)
        if webhook_roots:
            # A worker has no HTTP server, so it executes runs but cannot
            # receive the requests that start these. Left unsaid, the symptom
            # is a workflow that simply never runs and a worker that looks
            # perfectly healthy.
            console.warn(
                f"{', '.join(webhook_roots)} start from webhooks, which this "
                "worker does not serve. Run the app (or another process "
                "serving the workflow endpoints) to receive them; this worker "
                "will execute the runs they admit. Schedules and timers do "
                "fire here."
            )
        async with runtime.running():
            # The kernel's worker does the work; this task only waits for the
            # operator (or the platform) to stop the process.
            await asyncio.Event().wait()

    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        console.print("Worker stopped.")


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
@click.argument("target")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
def check(target: str, as_json: bool):
    """Compile every workflow in a module without running anything.

    TARGET is a path to a Python file or a dotted module name. Each workflow
    class it defines is compiled through the same rules the app applies at
    registration, so what passes here registers cleanly. Made for generation
    loops: a tool that writes workflow code calls this, reads the errors --
    which name the fix -- and repairs its output before anyone runs it.
    """
    from reflex_base.utils.exceptions import WorkflowDefinitionError

    from reflex.workflow.definition import compile_workflow

    try:
        module = _load_module(target)
    except Exception as err:
        if as_json:
            click.echo(json.dumps({"ok": False, "error": str(err), "workflows": []}))
        else:
            console.error(f"Could not load {target!r}: {err}")
        raise click.exceptions.Exit(1) from None

    classes = [
        value
        for value in vars(module).values()
        if isinstance(value, type) and "__workflow__" in vars(value)
    ]
    reports: list[dict[str, Any]] = []
    seen_ids: dict[str, str] = {}
    for workflow_cls in classes:
        report: dict[str, Any] = {"class": workflow_cls.__name__}
        try:
            definition = compile_workflow(workflow_cls)
        except WorkflowDefinitionError as err:
            report["ok"] = False
            report["error"] = str(err)
            reports.append(report)
            continue
        report["workflow_id"] = definition.workflow_id
        owner = seen_ids.setdefault(definition.workflow_id, workflow_cls.__name__)
        if owner != workflow_cls.__name__:
            report["ok"] = False
            report["error"] = (
                f"workflow id {definition.workflow_id!r} is also declared by "
                f"{owner}; ids must be unique."
            )
        else:
            report["ok"] = True
        reports.append(report)

    ok = bool(reports) and all(report["ok"] for report in reports)
    if as_json:
        payload: dict[str, Any] = {"ok": ok, "workflows": reports}
        if not reports:
            payload["error"] = "no workflow classes found"
        click.echo(json.dumps(payload, indent=2))
    elif not reports:
        console.error(
            f"No workflow classes in {target!r}. A workflow is an rx.State "
            "subclass with __workflow__ = rx.WorkflowConfig(id=...)."
        )
    else:
        for report in reports:
            if report["ok"]:
                click.echo(f"ok   {report['workflow_id']} ({report['class']})")
            else:
                click.echo(f"FAIL {report['class']}: {report['error']}")
    if not ok:
        raise click.exceptions.Exit(1)


def _load_module(target: str):
    """Import the module a check target names.

    Args:
        target: A ``.py`` path or a dotted module name.

    Returns:
        The imported module.

    Raises:
        FileNotFoundError: If a path target does not exist.
        ImportError: If the module cannot be imported.
    """
    import importlib
    import importlib.util

    if target.endswith(".py"):
        path = Path(target).resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            msg = f"cannot build an import spec for {path}"
            raise ImportError(msg)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    # A dotted name is resolved from the project root, the way `python -m`
    # would: the console script's sys.path does not include the working
    # directory, and "myapp.workflows" failing from the project's own root
    # is indistinguishable from a typo to the person running it.
    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    return importlib.import_module(target)


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
def retry(database: str | None, run_id: str):
    """Re-open a failed run at the step that failed.

    The step runs again with a fresh attempt budget; the original failure
    stays in the run's history.
    """
    _operator_action(database, run_id, "retry_run")


@workflows.command()
@database_option
@click.argument("run_id")
def skip(database: str | None, run_id: str):
    """Skip the step blocking a stopped run and let it continue.

    For a step that cannot succeed and is not worth failing the run over. It
    is recorded as an operator decision, not as an outcome.
    """
    _operator_action(database, run_id, "skip_step")


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
