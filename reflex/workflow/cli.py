"""The ``reflex workflows`` command group.

Operators reach for a terminal when a run misbehaves, so listing, inspecting,
cancelling, and resuming runs must not require writing a script or opening the
app. These commands read the same store the app writes, so they work against a
running deployment or a stopped one.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import operator
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from reflex_base.utils import console

from reflex.workflow.records import RunQuery, RunStatus, attempts_made

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


def _cli_attribution(reason: str | None) -> dict[str, str]:
    """Who is running this command, and why, for the run's history.

    Args:
        reason: The operator's stated reason, if any.

    Returns:
        The attribution mapping.
    """
    import getpass

    actor = os.environ.get("REFLEX_ACTOR") or getpass.getuser()
    payload = {"actor": actor}
    if reason:
        payload["reason"] = reason
    return payload


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

    async def apply(store: RunStore) -> Any:
        """Resolve the run, then apply the action to it.

        Args:
            store: The open run store.

        Returns:
            Whether the action applied.
        """
        resolved = await _resolve_run_id(store, run_id)
        return await getattr(store, action)(resolved, time.time(), **extra)

    applied = _with_store(database, apply)
    if not applied:
        console.error(
            f"Run {run_id!r} is not in a state that allows {action.split('_')[0]!r}."
        )
        raise click.exceptions.Exit(1)
    console.print(f"Applied {action.split('_')[0]} to {run_id}.")


_PREFIX_SCAN_LIMIT = 10_000


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


async def _resolve_run_id(store: RunStore, run_id: str) -> str:
    """Accept an unambiguous id prefix wherever a run id is taken.

    ``list`` prints full ids but ``dev`` prints eight-character prefixes, and
    a person who has been reading the second naturally types one. An exact id
    is looked up directly and costs nothing extra; only a prefix pays for a
    scan.

    Args:
        store: The open run store.
        run_id: A full run id or a prefix of one.

    Returns:
        The full run id.

    Raises:
        Exit: If the prefix matches no run, or more than one.
    """
    if not run_id.strip():
        # `reflex workflows cancel "$RUN_ID"` with RUN_ID unset arrives here as
        # an empty string, which prefixes every run. With exactly one run in
        # the database that resolved and cancelled it, reporting success.
        console.error("No run id given. Pass the run to act on.")
        raise click.exceptions.Exit(1)
    if await store.get_run(run_id) is not None:
        return run_id
    # One more than the cap: a page that comes back full means there may be
    # further runs, while exactly the cap would otherwise read as truncated
    # and disable prefixes for a database holding precisely that many.
    scanned = await store.list_runs(RunQuery(limit=_PREFIX_SCAN_LIMIT + 1))
    matches = [run.run_id for run in scanned if run.run_id.startswith(run_id)]
    if len(scanned) > _PREFIX_SCAN_LIMIT:
        # The newest N runs, not all of them: a prefix that looks unique here
        # may match another run just outside the window, and resolving it
        # would cancel or complete the wrong one. There is no prefix query in
        # the store protocol to do better, so say what is true.
        console.error(
            f"This database holds more than {_PREFIX_SCAN_LIMIT:,} runs, so "
            f"{run_id!r} cannot be shown to match only one. Pass the full run "
            "id (reflex workflows list prints them), or purge finished runs."
        )
        raise click.exceptions.Exit(1)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        console.error(f"No run {run_id!r} in this database.")
        raise click.exceptions.Exit(1)
    listed = ", ".join(match[:12] for match in matches[:5])
    more = f" and {len(matches) - 5} more" if len(matches) > 5 else ""
    console.error(f"{run_id!r} matches several runs: {listed}{more}.")
    raise click.exceptions.Exit(1)


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

    import sqlite3

    try:
        return asyncio.run(session())
    except sqlite3.OperationalError as err:
        if "locked" not in str(err) and "busy" not in str(err):
            raise
        # Bounded contention against a busy worker is an operational fact,
        # not a traceback: say what happened and what to do.
        console.error(
            "The store is busy (a worker holds its write lock). Retry in a moment."
        )
        raise click.exceptions.Exit(1) from None


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


_DEV_WATCH_INTERVAL: float = 0.25


class _DevClock:
    """The clock `reflex workflows dev` reads, movable by --fast-forward.

    The kernel takes the time source as an argument, so a foreground dev
    session can hand it a clock it is allowed to push forward when the only
    thing left to wait for is a timer.

    Attributes:
        now: The current time in epoch seconds.
    """

    __slots__ = ("now",)

    def __init__(self, now: float):
        """Start the clock.

        Args:
            now: The starting time in epoch seconds.
        """
        self.now = now

    def __call__(self) -> float:
        """Read the clock.

        Returns:
            The current time in epoch seconds.
        """
        return self.now


def _format_time(when: float) -> str:
    """Render an epoch time the way a person reads a log line.

    Args:
        when: The time in epoch seconds.

    Returns:
        A local-time string.
    """
    import datetime

    return datetime.datetime.fromtimestamp(when).strftime("%Y-%m-%d %H:%M:%S")


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


@workflows.command()
@click.argument("target")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of a table.")
def triggers(target: str, as_json: bool):
    """List what starts the workflows in TARGET, and how.

    The answer to "is my cron actually registered, and what is the URL this
    provider should post to" -- questions whose only other answer is reading
    the source, which is exactly what an operator should never have to do to
    understand a deployment.
    """
    from reflex_base.workflow import ScheduleTrigger, WebhookTrigger

    from reflex.workflow.cron import CronSchedule
    from reflex.workflow.definition import compile_workflow

    try:
        module = _load_module(target)
    except Exception as err:
        console.error(f"Could not load {target!r}: {err}")
        raise click.exceptions.Exit(1) from None

    rows: list[dict[str, Any]] = []
    for value in vars(module).values():
        if not (isinstance(value, type) and "__workflow__" in vars(value)):
            continue
        definition = compile_workflow(value)
        for handler in definition.handlers.values():
            trigger = handler.trigger
            if isinstance(trigger, WebhookTrigger):
                rows.append({
                    "workflow": definition.workflow_id,
                    "handler": handler.name,
                    "kind": "webhook",
                    "detail": trigger.topic,
                    "path": f"/_workflow/webhook/{trigger.topic}",
                    "verified": trigger.verify is not None,
                    "dedupe_by": trigger.dedupe_by,
                })
            elif isinstance(trigger, ScheduleTrigger):
                import time

                schedule = CronSchedule(trigger.cron)
                upcoming = schedule.next_after(time.time())
                rows.append({
                    "workflow": definition.workflow_id,
                    "handler": handler.name,
                    "kind": "schedule",
                    "detail": trigger.cron,
                    "next_fire": upcoming,
                })
            elif trigger is not None:
                rows.append({
                    "workflow": definition.workflow_id,
                    "handler": handler.name,
                    "kind": "manual",
                    "detail": "started from code or the API",
                })

    if as_json:
        click.echo(json.dumps(rows, indent=2, default=str))
        return
    if not rows:
        console.print(f"No triggers declared in {target!r}.")
        return
    click.echo(f"{'KIND':10}{'WORKFLOW':28}{'HANDLER':16}DETAIL")
    for row in sorted(rows, key=operator.itemgetter("kind", "workflow")):
        click.echo(
            f"{row['kind']:10}{row['workflow']:28}{row['handler']:16}{row['detail']}"
        )
        if row["kind"] == "webhook":
            guard = "signature verified" if row["verified"] else "UNVERIFIED"
            click.echo(f"{'':54}POST {row['path']}  ({guard})")
        elif row["kind"] == "schedule" and row.get("next_fire"):
            import datetime

            when = datetime.datetime.fromtimestamp(
                row["next_fire"], tz=datetime.timezone.utc
            )
            click.echo(f"{'':54}next {when:%Y-%m-%d %H:%M} UTC")


@workflows.command()
@database_option
@click.argument("target")
def doctor(database: str | None, target: str):
    """Check that TARGET's deployment is actually configured to run.

    Preflight for the things whose absence is silent: a webhook secret that
    is not set, an approval key that is missing, a store that cannot be
    reached. Each of those turns into "why did nothing happen", answered
    today by reading the database. Answer it here instead, before deploying.
    """
    from reflex.workflow.definition import compile_workflow, discover_workflows
    from reflex.workflow.health import describe_connections, problems
    from reflex.workflow.records import RunQuery
    from reflex.workflow.store import DATABASE_ENV

    try:
        module = _load_module(target)
    except Exception as err:
        console.error(f"Could not load {target!r}: {err}")
        raise click.exceptions.Exit(1) from None

    definitions = tuple(compile_workflow(cls) for cls in discover_workflows(module))
    if not definitions:
        console.error(f"No workflow classes in {target!r}.")
        raise click.exceptions.Exit(1)

    rows = describe_connections(definitions)
    failures = problems(rows)
    where = database or os.environ.get(DATABASE_ENV) or "the default ./workflow.db"
    try:
        _with_store(database, lambda store: store.list_runs(RunQuery(limit=1)))
    except Exception as err:
        failures.append(f"Store unreachable ({where}): {err}")
    else:
        console.print(f"Store reachable: {where}.")

    for row in rows:
        if row["severity"] == "note":
            console.print(f"note: {row['message']}")
    for problem in failures:
        console.error(problem)
    if failures:
        raise click.exceptions.Exit(1)
    console.print(f"{len(definitions)} workflow(s) ready to serve.")


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
    click.echo(
        f"    reflex workflows dev {module} {klass}.start --arg order=ord-1"
        " --fast-forward"
    )
    console.print("")
    console.print(
        "  (--fast-forward skips the workflow's one-day wait. Without it the "
        "run really waits a day, which is the point of durability.)"
    )
    console.print("")
    console.print("Or serve it as a worker and start runs from your own code:")
    click.echo(f"    reflex workflows worker {module}")
    console.print("")
    console.print("  From a script, a FastAPI route, or a Django view:")
    click.echo(f"    async with rx.workflows.connect({klass}):")
    click.echo(f"        await rx.workflows.submit({klass}.start(order='ord-1'))")


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
@click.option(
    "--fast-forward",
    is_flag=True,
    help="Skip a run's sleeps instead of waiting for them in real time.",
)
def dev(
    database: str | None,
    target: str,
    start: str | None,
    args: tuple[str, ...],
    fast_forward: bool,
):
    """Run TARGET's workflows in the foreground, printing every transition.

    The loop for building a workflow: start one, watch each step, attempt,
    retry and wait as it happens, and stop when the run ends. Pass START as
    the handler to launch (`Workflow.handler`), with --arg name=value for its
    payload; without it, this just serves and reports whatever arrives.

    Timers are real by default, so a handler that returns ``rx.after("1d",
    ...)`` leaves the run asleep for a day and this command says so and keeps
    serving. Pass --fast-forward to jump the clock to each wake time as the
    run reaches it, which runs the whole path in seconds.
    """
    import asyncio
    import sys
    import time

    from reflex_base.utils.exceptions import WorkflowDefinitionError

    from reflex.workflow.kernel import WorkflowObserver
    from reflex.workflow.records import (
        TERMINAL_RUN_STATUSES,
        HistoryEventType,
        step_claimable_at,
        step_wake_at,
    )
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
            sys.stdout.flush()
            if event_type in _terminal_events():
                finished.set()

    clock = _DevClock(time.time())

    async def watch_sleeps(run_id: str) -> None:
        """Report -- or skip -- the times a run is waiting for.

        A run that returned ``rx.after("1d", ...)`` is not stuck, but a
        terminal that prints nothing for a day looks identical to one that is.
        This says when the run wakes, and with --fast-forward moves the clock
        there so the rest of the path runs now.

        Args:
            run_id: The run to watch.
        """
        announced: set[float] = set()
        while True:
            await asyncio.sleep(_DEV_WATCH_INTERVAL)
            snapshot = await rx_workflows.get_run(run_id)
            if snapshot is None or snapshot.status in TERMINAL_RUN_STATUSES:
                return
            now = clock()
            if any(step_claimable_at(step, now) for step in snapshot.steps):
                continue
            wakes = [
                wake
                for step in snapshot.steps
                if (wake := step_wake_at(step)) is not None and wake > now
            ]
            if not wakes:
                continue
            wake = min(wakes)
            if fast_forward:
                clock.now = wake
                click.echo(f"  {run_id[:8]} fast-forward       +{wake - now:.0f}s")
                sys.stdout.flush()
            elif wake not in announced:
                announced.add(wake)
                console.print(
                    f"Run {run_id[:8]} sleeps until "
                    f"{_format_time(wake)} (in {wake - now:.0f}s). Serving until "
                    "then; --fast-forward skips it."
                )

    async def serve() -> None:
        """Run the kernel until the started run ends, or forever."""
        runtime = WorkflowRuntime(
            resolve_store(database), clock=clock, observer=Narrator()
        )
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
            watcher = asyncio.create_task(watch_sleeps(handle.run_id))
            try:
                await finished.wait()
            finally:
                watcher.cancel()
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
@click.option(
    "--drain",
    default=None,
    help=(
        "How long a stopping worker lets running attempts finish. Defaults to "
        "REFLEX_WORKFLOW_DRAIN, or 30s."
    ),
)
def worker(
    database: str | None,
    target: str,
    queues: tuple[str, ...],
    concurrency: int | None,
    drain: str | None,
):
    """Run workflows from TARGET with no frontend and no web server.

    TARGET is a Python file or dotted module defining workflow classes. This
    is the deployment shape for a background worker: a plain process that
    claims steps from the shared store and executes them. Scale by starting
    more of them, and narrow what a process takes with --queue.

    The workflows do not have to live in a Reflex app -- a module importable
    from a FastAPI service, a Django project, or a bare script works, because
    a worker needs only the definitions and the store.

    On SIGTERM or Ctrl-C the worker stops claiming and gives the attempts it
    is already running --drain to commit, so a rolling deploy hands over
    cleanly instead of leaving steps claimed until their leases lapse.
    """
    import asyncio
    import signal

    from reflex_base.utils.exceptions import WorkflowDefinitionError
    from reflex_base.workflow import parse_duration

    from reflex.workflow.runtime import WorkflowRuntime, configured_drain

    if drain is None:
        drain_seconds = configured_drain()
    else:
        try:
            drain_seconds = parse_duration(drain)
        except Exception as err:
            console.error(f"--drain {drain!r} is not a duration: {err}")
            raise click.exceptions.Exit(1) from None

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
        stopping = asyncio.Event()
        loop = asyncio.get_running_loop()
        for signal_name in ("SIGTERM", "SIGINT"):
            handled = getattr(signal, signal_name, None)
            if handled is not None:
                with contextlib.suppress(NotImplementedError):
                    loop.add_signal_handler(handled, stopping.set)

        async with runtime.running(drain=drain_seconds):
            # The kernel's worker does the work; this task only waits for the
            # operator (or the platform) to stop the process.
            await stopping.wait()
            console.print(f"Stopping; finishing running attempts ({drain_seconds:g}s).")
        console.print("Worker stopped.")

    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        console.print("Worker stopped.")


@workflows.command()
@database_option
@click.option("--workflow", "-w", default=None, help="Only this workflow id.")
@click.option("--label", "-l", "labels", multiple=True, help="Filter as key=value.")
@click.option(
    "--digest",
    default=None,
    help="Only runs admitted against this definition digest.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of a table.")
def stats(
    database: str | None,
    workflow: str | None,
    labels: tuple[str, ...],
    digest: str | None,
    as_json: bool,
):
    """Count runs by status: is this deployment healthy, in one screen.

    The two numbers that matter are how many runs are still open and how many
    stopped needing a person. Everything else is context. --json makes this a
    scrape for whatever collects metrics, so an alert on "runs needing
    attention" does not require reading the workflow database.

    With --digest it answers the other operational question: is anything still
    running the release I am about to replace.
    """
    from reflex.workflow.records import TERMINAL_RUN_STATUSES, RunQuery

    label_filter = dict(pair.split("=", 1) for pair in labels if "=" in pair)

    async def counts(store: RunStore) -> dict[str, int]:
        """Count runs per status.

        Args:
            store: The open store.

        Returns:
            The count for each status that has any runs.
        """
        found: dict[str, int] = {}
        for status in RunStatus:
            query = RunQuery(
                workflow_id=workflow,
                definition_digest=digest,
                statuses=(status,),
                labels=label_filter or None,
            )
            total = await store.count_runs(query)
            if total:
                found[status.value] = total
        return found

    found = _with_store(database, counts)
    total = sum(found.values())
    open_runs = sum(
        count
        for status, count in found.items()
        if RunStatus(status) not in TERMINAL_RUN_STATUSES
    )
    attention = found.get(RunStatus.NEEDS_ATTENTION.value, 0)

    if as_json:
        click.echo(
            json.dumps({
                "workflow": workflow,
                "digest": digest,
                "total": total,
                "open": open_runs,
                "needs_attention": attention,
                "by_status": found,
            })
        )
        return

    if not total:
        console.print("No runs yet.")
        return
    click.echo(f"{'STATUS':<20}{'RUNS':>8}")
    for status in RunStatus:
        count = found.get(status.value)
        if count:
            click.echo(f"{status.value:<20}{count:>8}")
    console.print("")
    console.print(f"{total} run(s); {open_runs} open, {attention} needing attention.")


@workflows.command()
@database_option
@click.option(
    "--older-than",
    required=True,
    help="Delete terminal runs whose last update is older than this, e.g. 30d.",
)
@click.option("--workflow", "-w", default=None, help="Only this workflow id.")
@click.option("--yes", is_flag=True, help="Delete without asking.")
@click.option("--reason", default=None, help="Why, recorded in the audit log.")
def purge(
    database: str | None,
    older_than: str,
    workflow: str | None,
    yes: bool,
    reason: str | None,
):
    """Delete finished runs older than a cutoff, reclaiming the store.

    Terminal data grows forever otherwise. Purging a run also forgets its
    deduplication key, so a provider redelivery arriving after the retention
    window is admitted as a new run -- keep the window longer than the
    provider's redelivery horizon.
    """
    import time

    from reflex_base.workflow import parse_duration

    try:
        cutoff = time.time() - parse_duration(older_than)
    except Exception as err:
        console.error(f"--older-than {older_than!r} is not a duration: {err}")
        raise click.exceptions.Exit(1) from None
    if not yes:
        click.confirm(
            f"Delete terminal runs untouched for {older_than}"
            f"{' in ' + workflow if workflow else ''}?",
            abort=True,
        )
    deleted = _with_store(
        database,
        lambda store: store.purge_runs(
            cutoff, workflow_id=workflow, attribution=_cli_attribution(reason)
        ),
    )
    console.print(f"Purged {deleted} run(s).")


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
        resolved = await _resolve_run_id(store, run_id)
        return (
            await store.get_run(resolved),
            await store.get_steps(resolved),
            await store.get_history(resolved) if history else (),
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
                            "attempts": attempts_made(step),
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
        attempts = f"{attempts_made(step)}"
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


def _run_server(app: Any, host: str, port: int) -> None:
    """Serve an ASGI app; separated so tests can intercept it.

    Args:
        app: The ASGI application.
        host: The interface to bind.
        port: The port to bind.
    """
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info", lifespan="on")


@workflows.command()
@database_option
@click.argument("target")
@click.option("--host", default="0.0.0.0", help="Interface to bind.")
@click.option("--port", default=8000, type=int, help="Port to bind.")
@click.option(
    "--queue",
    "queues",
    multiple=True,
    help="Execute only these queues. Repeatable; default serves every queue.",
)
@click.option(
    "--ingress-only",
    is_flag=True,
    help="Accept webhooks and API calls but execute nothing.",
)
@click.option(
    "--worker-only",
    is_flag=True,
    help="Execute steps but accept nothing; keeps /healthz, /readyz, /metrics.",
)
@click.option(
    "--drain",
    default=None,
    help=(
        "How long shutdown lets running attempts finish. Defaults to "
        "REFLEX_WORKFLOW_DRAIN, or 30s."
    ),
)
def serve(
    database: str | None,
    target: str,
    host: str,
    port: int,
    queues: tuple[str, ...],
    ingress_only: bool,
    worker_only: bool,
    drain: str | None,
):
    """Serve TARGET's workflows as a standalone service: ingress, API, worker.

    One process, no frontend, no rx.App: webhook and approval ingress, the
    run HTTP API (POST /runs, GET /runs, signals, operator actions), health
    and readiness probes, Prometheus metrics, an OpenAPI document, and the
    worker loop. Scale the halves separately with --ingress-only and
    --worker-only against the same database.

    The API authenticates with bearer tokens: REFLEX_WORKFLOW_API_TOKEN grants
    everything; REFLEX_WORKFLOW_API_TOKEN_READ, _START, _SIGNAL, and _OPERATE
    each grant one scope. Webhooks authenticate with provider signatures.

    On SIGTERM the server stops accepting requests, then gives running
    attempts --drain to commit, so a rolling deploy hands over cleanly.
    """
    from reflex_base.utils.exceptions import WorkflowDefinitionError
    from reflex_base.workflow import parse_duration

    from reflex.workflow.runtime import WorkflowRuntime, configured_drain
    from reflex.workflow.serve import build_app
    from reflex.workflow.store import resolve_store

    if ingress_only and worker_only:
        console.error("--ingress-only and --worker-only exclude each other.")
        raise click.exceptions.Exit(1)
    if drain is None:
        drain_seconds = configured_drain()
    else:
        try:
            drain_seconds = parse_duration(drain)
        except Exception as err:
            console.error(f"--drain {drain!r} is not a duration: {err}")
            raise click.exceptions.Exit(1) from None

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

    runtime = WorkflowRuntime(resolve_store(database), queues=queues or None)
    try:
        for workflow_cls in classes:
            runtime.register(workflow_cls)
    except WorkflowDefinitionError as err:
        console.error(f"Cannot serve {target!r}: {err}")
        raise click.exceptions.Exit(1) from None
    app = build_app(
        runtime,
        worker=not ingress_only,
        ingress=not worker_only,
        drain=drain_seconds,
    )
    served = ", ".join(sorted(d.workflow_id for d in runtime.definitions))
    mode = (
        "ingress only"
        if ingress_only
        else "worker only"
        if worker_only
        else "ingress + worker"
    )
    console.print(f"Serving {served} on {host}:{port} ({mode}).")
    _run_server(app, host, port)


@workflows.command()
@database_option
@click.option(
    "--can-retire",
    "retire_release",
    default=None,
    help=(
        "Exit 0 when no active run is pinned to this release, 1 otherwise; "
        "the gate a deploy runs before stopping that release's workers."
    ),
)
def fleet(database: str | None, retire_release: str | None):
    """Show registered workers and the runs each release still owns.

    A worker that stopped cleanly disappears; one that crashed stays listed
    with a stale heartbeat, which is exactly what this page should show.
    """
    import time

    from reflex.workflow.records import TERMINAL_RUN_STATUSES, RunQuery, RunStatus

    active = tuple(s for s in RunStatus if s not in TERMINAL_RUN_STATUSES)

    async def read(store: RunStore):
        """Collect workers and per-release active counts.

        Args:
            store: The open run store.

        Returns:
            The workers, the release counts, and the gate answer.
        """
        workers = await store.list_workers()
        releases = sorted({w.release_id for w in workers if w.release_id is not None})
        if retire_release is not None and retire_release not in releases:
            releases.append(retire_release)
        counts = {
            release: await store.count_runs(
                RunQuery(release_id=release, statuses=active)
            )
            for release in releases
        }
        return workers, counts

    workers, counts = _with_store(database, read)
    if retire_release is not None:
        held = counts.get(retire_release, 0)
        if held:
            console.error(
                f"Release {retire_release!r} still owns {held} active "
                f"run{'s' if held != 1 else ''}; retiring its workers now "
                "would strand them until their leases lapse."
            )
            raise click.exceptions.Exit(1)
        console.print(f"Release {retire_release!r} owns no active runs.")
        return
    if not workers:
        console.print("No workers registered.")
    now = time.time()
    for worker in workers:
        age = now - worker.heartbeat_at
        queues = ", ".join(worker.queues) or "all queues"
        console.print(
            f"{worker.worker_id[:12]}  release={worker.release_id or '-'}  "
            f"{queues}  capacity={worker.capacity}  "
            f"heartbeat {age:.0f}s ago"
        )
    for release, held in counts.items():
        console.print(f"release {release}: {held} active run(s)")


@workflows.command()
@database_option
@click.option(
    "--status",
    type=click.Choice(["pending", "delivered", "dead"]),
    default=None,
    help="Show only deliveries in this state; default shows dead letters.",
)
@click.option("--all", "show_all", is_flag=True, help="Show every delivery state.")
@click.option(
    "--replay",
    "replay_id",
    default=None,
    help="Re-attempt routing of one delivery by its id.",
)
@click.option("--reason", default=None, help="Why, recorded in the audit log.")
def deadletters(
    database: str | None,
    status: str | None,
    show_all: bool,
    replay_id: str | None,
    reason: str | None,
):
    """Inspect and replay correlated webhook deliveries.

    A delivery that arrived before its run waits PENDING; one nothing can
    take is DEAD with a reason. Replay routes a delivery again with the same
    event-id idempotency, so replaying one that already landed is a no-op.
    """
    from reflex.workflow.records import ParkedStatus

    async def act(store: RunStore):
        """Run the inspection or replay.

        Args:
            store: The open run store.

        Returns:
            The rows to render, or the replay disposition.
        """
        if replay_id is not None:
            return await store.replay_parked(
                replay_id, time.time(), _cli_attribution(reason)
            )
        chosen = (
            None
            if show_all
            else ParkedStatus(status.upper())
            if status
            else ParkedStatus.DEAD
        )
        return await store.list_parked(status=chosen)

    import time

    result = _with_store(database, act)
    if replay_id is not None:
        console.print(f"Replay: {result}")
        raise click.exceptions.Exit(
            0 if result in ("resolved", "buffered", "duplicate") else 1
        )
    if not result:
        console.print("No matching deliveries.")
        return
    for row in result:
        target = row.run_id or f"key={row.correlation_key!r}"
        detail = f" reason={row.reason}" if row.reason else ""
        console.print(
            f"{row.parked_id}  {row.status.value:<9} {row.workflow_id}."
            f"{row.channel}  {target}{detail}"
        )


@workflows.command()
@database_option
@click.argument("run_id")
@click.option("--reason", default=None, help="Why, recorded in the run's history.")
def cancel(database: str | None, run_id: str, reason: str | None):
    """Request cancellation of a run.

    The running worker finalizes it; if no worker is running, it is cancelled
    the next time one starts.
    """
    import time

    async def request(store: RunStore) -> bool:
        """Record the intent against the resolved run.

        Args:
            store: The open run store.

        Returns:
            Whether intent was recorded.
        """
        return await store.request_cancel(
            await _resolve_run_id(store, run_id),
            time.time(),
            _cli_attribution(reason),
        )

    recorded = _with_store(database, request)
    if not recorded:
        console.error(f"Run {run_id!r} is unknown or already finished.")
        raise click.exceptions.Exit(1)
    console.print(f"Cancellation requested for {run_id}.")


@workflows.command()
@database_option
@click.argument("run_id")
@click.option("--reason", default=None, help="Why, recorded in the run's history.")
def retry(database: str | None, run_id: str, reason: str | None):
    """Re-open a failed run at the step that failed.

    The step runs again with a fresh attempt budget; the original failure
    stays in the run's history.
    """
    _operator_action(
        database, run_id, "retry_run", attribution=_cli_attribution(reason)
    )


@workflows.command()
@database_option
@click.argument("run_id")
@click.option("--reason", default=None, help="Why, recorded in the run's history.")
def skip(database: str | None, run_id: str, reason: str | None):
    """Skip the step blocking a stopped run and let it continue.

    For a step that cannot succeed and is not worth failing the run over. It
    is recorded as an operator decision, not as an outcome.
    """
    _operator_action(
        database, run_id, "skip_step", attribution=_cli_attribution(reason)
    )


def _finalize(
    database: str | None,
    run_id: str,
    status: RunStatus,
    *,
    result: Any = None,
    error: dict[str, Any] | None = None,
    reason: str | None = None,
):
    """End a run by operator decision.

    Goes through the kernel rather than the store because finalizing a child
    run has to deliver its arrival to the parent's join slot in the same
    transaction -- otherwise a parent waits forever on a child an operator
    already closed. No worker is started, so nothing executes here.

    Args:
        database: Connection URL or SQLite path, or None for the default.
        run_id: The run to finalize.
        status: The terminal status to record.
        result: Result to record when completing.
        error: Error payload to record when failing.
        reason: Why, recorded in the run's history.

    Raises:
        Exit: When the run is unknown, already finished, or has a claimed step.
    """
    from reflex.workflow.kernel import WorkflowKernel

    async def finish(store: RunStore) -> bool:
        """Resolve the run, then finalize it through a kernel.

        Args:
            store: The open run store.

        Returns:
            Whether the run was finalized.
        """
        return await WorkflowKernel([], store).force_finalize(
            await _resolve_run_id(store, run_id),
            status=status,
            result=result,
            error=error,
            actor=_cli_attribution(None)["actor"],
            reason=reason,
        )

    finalized = _with_store(database, finish)
    if not finalized:
        console.error(
            f"Run {run_id!r} is unknown, already finished, or has a step a "
            "worker still holds. Cancel it first if a worker is on it."
        )
        raise click.exceptions.Exit(1)
    console.print(f"Run {run_id} recorded as {status.value} by operator decision.")


@workflows.command()
@database_option
@click.argument("run_id")
@click.option("--reason", default=None, help="Why, recorded in the run's history.")
@click.option(
    "--result", "result_json", default=None, help="Result to record, as JSON."
)
def complete(
    database: str | None,
    run_id: str,
    result_json: str | None,
    reason: str | None,
):
    """End a run as completed by operator decision.

    For a run no code path will finish: a wait nobody will answer, a branch
    whose provider is gone. Refused while a worker holds a step -- cancel
    first. If the run is a child, its parent hears about it in the same
    transaction.
    """
    result = None
    if result_json is not None:
        try:
            result = json.loads(result_json)
        except json.JSONDecodeError as err:
            console.error(f"--result is not JSON: {err}")
            raise click.exceptions.Exit(1) from None
    _finalize(database, run_id, RunStatus.COMPLETED, result=result, reason=reason)


@workflows.command()
@database_option
@click.argument("run_id")
@click.option("--reason", required=True, help="Why the run is being given up on.")
def fail(database: str | None, run_id: str, reason: str):
    """End a run as failed by operator decision.

    The reason is recorded on the run, so the history says a person decided
    this rather than leaving a failure with no explanation.
    """
    _finalize(
        database, run_id, RunStatus.FAILED, error={"reason": reason}, reason=reason
    )


@workflows.command()
@database_option
@click.argument("run_id")
@click.option("--reason", default=None, help="Why, recorded in the run's history.")
def resume(database: str | None, run_id: str, reason: str | None):
    """Re-open a run suspended for operator attention."""
    import time

    async def reopen(store: RunStore) -> bool:
        """Resolve the run, then re-open it.

        Args:
            store: The open run store.

        Returns:
            Whether a suspended run was re-opened.
        """
        return await store.resume_run(
            await _resolve_run_id(store, run_id),
            time.time(),
            _cli_attribution(reason),
        )

    resumed = _with_store(database, reopen)
    if not resumed:
        console.error(f"Run {run_id!r} is not suspended.")
        raise click.exceptions.Exit(1)
    console.print(f"Resumed {run_id}; its next step will run.")


CONSOLE_APP_NAME = "workflow_console"


def materialize_console_project(root: Path) -> Path:
    """Write the minimal Reflex project that serves the operator console.

    A Reflex app needs a project directory -- ``rxconfig.py`` and an app
    module -- and the console is a library module, so the CLI writes that
    scaffold rather than asking the operator to. Rewritten on every launch,
    so an upgrade never serves a stale scaffold.

    Args:
        root: The directory to write the project into.

    Returns:
        The project root.
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "rxconfig.py").write_text(
        f"import reflex as rx\n\nconfig = rx.Config(app_name={CONSOLE_APP_NAME!r})\n"
    )
    package = root / CONSOLE_APP_NAME
    package.mkdir(exist_ok=True)
    (package / "__init__.py").write_text("")
    (package / f"{CONSOLE_APP_NAME}.py").write_text(
        '"""The operator console, served by `reflex workflows console`."""\n\n'
        "from reflex.workflow.console import console_app\n\n"
        "app = console_app()\n"
    )
    return root


def _run_console_project(root: Path, host: str, port: int, env: dict) -> None:
    """Launch ``reflex run`` in the console project; separated for tests.

    Args:
        root: The materialized project root.
        host: The backend bind address.
        port: The frontend port.
        env: The environment for the child process.
    """
    import subprocess

    subprocess.run(
        [
            sys.executable,
            "-m",
            "reflex",
            "run",
            "--backend-host",
            host,
            "--frontend-port",
            str(port),
        ],
        cwd=root,
        env=env,
        check=False,
    )


@workflows.command(name="console")
@database_option
@click.option(
    "--host",
    default="127.0.0.1",
    help=(
        "Interface to bind. Loopback by default: the console has no login of "
        "its own, so exposing it is a deliberate choice behind your proxy."
    ),
)
@click.option("--port", default=3000, type=int, help="Port to serve on.")
@click.option(
    "--project-dir",
    default=None,
    help="Where to write the console's Reflex project; defaults to a cache dir.",
)
@click.argument("target", required=False)
def console_command(
    database: str | None,
    host: str,
    port: int,
    project_dir: str | None,
    target: str | None,
):
    """Serve the operator console: runs, one run's story, fleet, and events.

    Pass TARGET -- the module of workflow classes -- to also see what starts
    each workflow: webhook URLs and their verification, schedules and their
    next occurrence. The console registers them read-only.

    Every action taken here goes through the same operations as the CLI,
    carries your name (REFLEX_ACTOR, else the login user) and your reason,
    and lands in the run's own history. The console never executes steps;
    it reads and repairs.
    """
    from reflex.workflow.store import DATABASE_ENV

    root = (
        Path(project_dir)
        if project_dir
        else Path.home() / ".cache" / "reflex-workflows" / "console"
    )
    materialize_console_project(root)
    env = dict(os.environ)
    if database:
        env[DATABASE_ENV] = database
    if target:
        # Resolved to an absolute path so the scaffold's working directory
        # does not change what the console imports.
        env["REFLEX_WORKFLOW_CONSOLE_TARGET"] = (
            str(Path(target).resolve()) if Path(target).exists() else target
        )
    if host not in ("127.0.0.1", "localhost", "::1"):
        console.warn(
            f"Binding the console to {host}: it has no login of its own. Put "
            "it behind a proxy that authenticates operators and stamps "
            "REFLEX_ACTOR, or keep it on loopback."
        )
    console.print(f"Serving the operator console on http://{host}:{port}")
    _run_console_project(root, host, port, env)


@workflows.command()
@database_option
@click.option("--action", default=None, help="Show only this action.")
@click.option("--limit", default=50, type=int, help="Entries to show.")
def audit(database: str | None, action: str | None, limit: int):
    """Show operator actions that have no run to carry them.

    Run-level actions live in each run's history (see `show --history`);
    this is the log for the rest -- dead-letter replays and purges -- with
    who asked and why.
    """

    async def read(store: RunStore):
        """List the entries.

        Args:
            store: The open run store.

        Returns:
            The entries, newest first.
        """
        return await store.list_audit(action=action, limit=limit)

    entries = _with_store(database, read)
    if not entries:
        console.print("No audited actions.")
        return
    for entry in entries:
        why = f"  -- {entry.reason}" if entry.reason else ""
        console.print(
            f"{entry.audit_id[:12]}  {entry.actor:<16} {entry.action:<14} "
            f"{entry.target}  {json.dumps(entry.detail)}{why}"
        )
