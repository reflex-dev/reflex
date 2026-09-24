"""Benchmarks for linked ``rx.SharedState``.

Linking makes one ``SharedState`` substate of many client state trees resolve
to a single shared token's instance. Every event on a linked client pays for
that indirection, and every write fans out to the other clients linked to the
same token. These benchmarks measure both.

Everything runs against ``StateManagerMemory`` and an in-process
``EventNamespace`` whose socket emit is stubbed, so the numbers describe the
work Reflex does -- taking the shared token's lock, patching the linked state
into the tree, resolving deltas through it and re-driving one ``modify_state``
per other client -- rather than redis or websocket transport.

``private`` is the baseline for every comparison here. It is the same state
class on the same pipeline, never linked: an app that defines a ``SharedState``
but has not linked this client. It is not a shared-state-free baseline.
Registrations and the root's shared-state flags are isolated during collection
and execution, so other benchmark modules retain their original event path.
The difference between ``private`` and ``linked`` is the cost of resolving a
link, not the cost of the feature existing.
"""

import asyncio
import contextlib
import dataclasses
import traceback
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from typing import Any
from unittest import mock

import pytest
import pytest_asyncio
from pytest_codspeed import BenchmarkFixture
from reflex_base.constants import RouteVar
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.event import Event
from reflex_base.event.context import EventContext
from reflex_base.event.processor import BaseStateEventProcessor
from reflex_base.registry import RegistrationContext
from reflex_base.utils.format import format_event_handler

import reflex as rx
from reflex.app import App, EventNamespace
from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.token import BaseStateToken
from reflex.utils.token_manager import SocketRecord

# The shared token every linked client in a scenario points at. Link tokens
# cannot contain underscores.
SHARED_TOKEN = "benchmark-room"

# The client whose events are measured.
PRIMARY_TOKEN = "benchmark-client"

# Other clients in the widest fan-out scenario. Large enough that the
# per-client fan-out cost dominates the fixed cost of one event, so the two
# can be read apart against the single-client scenario.
FANOUT_CLIENTS = 8

# How many ``app.modify_state`` cycles one measured call drives. Entering the
# event loop costs a few microseconds no matter what happens inside it, so a
# single cycle would report mostly loop entry.
MODIFY_ITERATIONS = 10


# Importing SharedState registers its internal base, and subclassing it mutates
# State's shared-state flags. Keep both changes out of other benchmark modules.
with (
    RegistrationContext.ensure_context().fork() as SHARED_STATE_REGISTRATION,
    mock.patch.dict(rx.State.backend_vars),
    mock.patch.object(
        rx.State, "_always_dirty_substates", rx.State._always_dirty_substates.copy()
    ),
):
    from reflex.istate.shared import UPDATE_OTHER_CLIENT_TASKS, SharedStateBaseInternal

    class SharedCounterState(rx.SharedState):
        """A counter that clients link to a shared token."""

        counter: int = 0

        @rx.event
        def increment(self):
            """Increment the counter."""
            self.counter = self.counter + 1

        @rx.event
        def decrement(self):
            """Decrement the counter."""
            self.counter = self.counter - 1

        @rx.event
        async def link(self, token: str):
            """Link this client's counter to a shared token.

            Args:
                token: The shared token to link to.
            """
            await self._link_to(token)

        @rx.event
        async def unlink(self):
            """Unlink this client's counter from its shared token.

            The rehydrate events ``_unlink`` returns are dropped: replaying a full
            hydrate would swamp the unlink itself.
            """
            await self._unlink()


COUNTER_FULL_NAME = SharedCounterState.get_full_name()
COUNTER_FIELD = "counter" + FIELD_MARKER


@dataclasses.dataclass(frozen=True)
class Scenario:
    """How many clients a benchmark scenario has, and whether they are linked."""

    linked: bool
    other_clients: int


SCENARIOS: dict[str, Scenario] = {
    "private": Scenario(linked=False, other_clients=0),
    "linked": Scenario(linked=True, other_clients=0),
    "linked_1_client": Scenario(linked=True, other_clients=1),
    f"linked_{FANOUT_CLIENTS}_clients": Scenario(
        linked=True, other_clients=FANOUT_CLIENTS
    ),
}

ALL_SCENARIOS = list(SCENARIOS)

# Scenarios for the benchmarks that measure the linking machinery itself.
# Adding other clients there would only re-measure the fan-out that
# ``test_process_event`` already covers.
UNFANNED_SCENARIOS = ["private", "linked"]


def _other_token(index: int) -> str:
    """Build the client token of one of the other linked clients.

    Args:
        index: The client index.

    Returns:
        The client token.
    """
    return f"benchmark-other-{index}"


def _event(name: str, token: str, payload: dict[str, Any] | None = None) -> Event:
    """Build one event for a handler on ``SharedCounterState``.

    Args:
        name: The handler name on ``SharedCounterState``.
        token: The client token the event arrives on.
        payload: The handler's arguments, if any.

    Returns:
        The event to enqueue.
    """
    return Event(
        name=format_event_handler(SharedCounterState.event_handlers[name]),
        router_data={RouteVar.CLIENT_TOKEN: token, "query": {}, "pathname": "/"},
        payload=payload or {},
    )


def _counter_events(token: str) -> list[Event]:
    """Two increments followed by two decrements, returning to the start.

    Args:
        token: The client token the events arrive on.

    Returns:
        The counter event batch.
    """
    return [_event("increment", token) for _ in range(2)] + [
        _event("decrement", token) for _ in range(2)
    ]


def _link_events(token: str) -> list[Event]:
    """A link followed by the unlink that undoes it.

    Args:
        token: The client token the events arrive on.

    Returns:
        The link/unlink event batch.
    """
    return [
        _event("link", token, {"token": SHARED_TOKEN}),
        _event("unlink", token),
    ]


async def _drain_fanout(timeout: float = 5) -> None:
    """Wait for the updates the shared state spawned for the other clients.

    The fan-out is fire-and-forget: ``_do_update_other_tokens`` creates one
    task per other client and returns without awaiting them, so a benchmark
    that did not drain them would stop timing before the work it is measuring
    had run.

    Args:
        timeout: Maximum seconds to wait before cancelling stalled updates.

    Raises:
        asyncio.TimeoutError: If an update does not finish in time.
        AssertionError: If fan-out tasks remain after the batch finishes.
    """
    if pending := tuple(UPDATE_OTHER_CLIENT_TASKS):
        await asyncio.wait_for(asyncio.gather(*pending), timeout=timeout)
    assert not UPDATE_OTHER_CLIENT_TASKS, "Shared-state fan-out tasks leaked"


@dataclasses.dataclass(frozen=True)
class SharedStateHarness:
    """The scenario under benchmark and the operations measured against it."""

    app: App
    state_manager: StateManagerMemory
    processor: BaseStateEventProcessor
    loop: asyncio.AbstractEventLoop

    async def run_events(self, events: list[Event], token: str) -> None:
        """Process one batch of events for a client and settle the fan-out.

        Args:
            events: The batch to enqueue.
            token: The client token the events arrive on.
        """
        async with self.processor as processor:
            for future in asyncio.as_completed([
                await processor.enqueue(token, event) for event in events
            ]):
                await future
            await _drain_fanout()

    async def counter_events(self) -> None:
        """Process the counter batch for the measured client."""
        await self.run_events(_counter_events(PRIMARY_TOKEN), PRIMARY_TOKEN)

    async def link_events(self) -> None:
        """Link the measured client to the shared token, then unlink it."""
        await self.run_events(_link_events(PRIMARY_TOKEN), PRIMARY_TOKEN)

    async def modify_state(self) -> None:
        """Drive ``app.modify_state`` over the measured client's tree.

        This is the path a background task or an API route takes into a
        client's state: the same lock, link patching and delta resolution as an
        event, without the event queue around it. Half the cycles increment and
        half decrement, so the tree ends where it started.
        """
        token = BaseStateToken(ident=PRIMARY_TOKEN, cls=SharedCounterState)
        for iteration in range(MODIFY_ITERATIONS):
            async with self.app.modify_state(token) as root_state:
                counter_state = await root_state.get_state(SharedCounterState)
                if iteration % 2:
                    counter_state.counter -= 1
                else:
                    counter_state.counter += 1
        await _drain_fanout()


@contextlib.asynccontextmanager
async def _shared_state_app(
    scenario: Scenario,
    on_update: Callable[[str, Mapping[str, Mapping[str, Any]]], Any],
) -> AsyncIterator[SharedStateHarness]:
    """Wire an app, an in-memory state manager and an event processor together.

    The app carries a real ``EventNamespace`` with a connected socket record
    per client, because the fan-out skips disconnected tokens and routes its
    updates through ``EventNamespace.emit_update``. Only the socket emit itself
    is stubbed.

    Args:
        scenario: How many clients to register, and whether to link them.
        on_update: Called with the token and delta of every emitted update.

    Yields:
        The harness for the scenario.
    """

    def handle_backend_exception(ex: Exception) -> None:
        formatted_exc = "\n".join(traceback.format_exception(ex))
        pytest.fail(f"Event processor raised an unexpected exception:\n{formatted_exc}")

    async def emit_delta_impl(  # noqa: RUF029
        token: str, delta: Mapping[str, Mapping[str, Any]]
    ) -> None:
        on_update(token, delta)

    async def emit_event_impl(token: str, *events: Event) -> None:
        pass

    async def emit_impl(  # noqa: RUF029
        event: str, update: Any, to: str, **kwargs: Any
    ) -> None:
        on_update(sid_to_token[to], update.delta)

    with (
        SHARED_STATE_REGISTRATION.fork(),
        mock.patch.dict(rx.State.backend_vars, {"_reflex_internal_links": {}}),
        mock.patch.object(
            rx.State,
            "_always_dirty_substates",
            rx.State._always_dirty_substates | {SharedStateBaseInternal.get_name()},
        ),
    ):
        state_manager = StateManagerMemory()
        app = App()
        app._state_manager = state_manager
        namespace = EventNamespace("/event", app)
        app._event_namespace = namespace

        token_manager = namespace._token_manager
        sid_to_token = token_manager.sid_to_token
        client_tokens = [
            PRIMARY_TOKEN,
            *map(_other_token, range(scenario.other_clients)),
        ]
        for client_token in client_tokens:
            sid = f"sid-{client_token}"
            token_manager.token_to_socket[client_token] = SocketRecord(
                instance_id=token_manager.instance_id, sid=sid
            )
            sid_to_token[sid] = client_token

        processor = BaseStateEventProcessor(
            backend_exception_handler=handle_backend_exception,
            graceful_shutdown_timeout=5,
        )
        # Skip initial hydration because there is no frontend.
        with (
            mock.patch.object(processor, "_rehydrate", new=mock.AsyncMock()),
            mock.patch.object(namespace, "emit", new=emit_impl),
        ):
            processor._root_context = EventContext(
                token="",
                state_manager=state_manager,
                enqueue_impl=processor.enqueue_many,
                emit_delta_impl=emit_delta_impl,
                emit_event_impl=emit_event_impl,
            )
            # ``app.modify_state`` pushes the processor's root context when it
            # is called outside of one, as a background task or API route is.
            app._event_processor = processor
            harness = SharedStateHarness(
                app=app,
                state_manager=state_manager,
                processor=processor,
                loop=asyncio.get_running_loop(),
            )
            try:
                if scenario.linked:
                    for client_token in client_tokens:
                        await harness.run_events(
                            [_event("link", client_token, {"token": SHARED_TOKEN})],
                            client_token,
                        )
                else:
                    # Seed router data so the measured batch is not the event
                    # that first populates it.
                    await harness.counter_events()
                yield harness
            finally:
                try:
                    await _drain_fanout()
                finally:
                    await state_manager.close()


@pytest_asyncio.fixture
async def harness(request: pytest.FixtureRequest):
    """Set up one benchmark scenario, warmed so every sample measures the same work.

    Args:
        request: The fixture request carrying the scenario name.

    Yields:
        The harness for the scenario.
    """
    scenario = SCENARIOS[request.param]
    async with _shared_state_app(scenario, lambda *_: None) as harness:
        await harness.counter_events()
        await harness.modify_state()
        if not scenario.linked:
            # Only the unlinked scenario benchmarks linking, and only it can be
            # warmed for it: a link/unlink cycle ends unlinked, so running one
            # against a linked scenario would leave it in the wrong state.
            await harness.link_events()
        yield harness


def _benchmark(
    harness: SharedStateHarness,
    benchmark: BenchmarkFixture,
    operation: Callable[[], Awaitable[None]],
) -> None:
    """Measure one async operation on the harness's event loop.

    The benchmark body has to be synchronous, so it borrows the loop
    pytest-asyncio already set up rather than standing up a fresh one per
    iteration.

    Args:
        harness: The harness under benchmark.
        benchmark: The codspeed benchmark fixture.
        operation: The operation to measure.
    """
    benchmark(lambda: harness.loop.run_until_complete(operation()))


@pytest.mark.parametrize("harness", ALL_SCENARIOS, indirect=True)
def test_process_event(harness: SharedStateHarness, benchmark: BenchmarkFixture):
    """Benchmark four counter events on a client, with the fan-out they trigger.

    The batch returns the counter to its starting value, so every sample
    measures identical work. Against ``private``, the ``linked`` scenario adds
    the shared token's lock, the patch of the linked state into the tree and
    the router vars ``_patch_state`` re-dirties; the fan-out scenarios add one
    full ``modify_state`` and emitted update per other client per event.

    Args:
        harness: The parametrized scenario.
        benchmark: The codspeed benchmark fixture.
    """
    _benchmark(harness, benchmark, harness.counter_events)


@pytest.mark.parametrize("harness", UNFANNED_SCENARIOS, indirect=True)
def test_modify_state(harness: SharedStateHarness, benchmark: BenchmarkFixture):
    """Benchmark ``app.modify_state`` cycles over a client's state tree.

    The path a background task or an API route takes into client state, which
    resolves links the same way an event does but without the event queue
    around it, so the linking machinery is measured with less on top of it.

    Args:
        harness: The parametrized scenario.
        benchmark: The codspeed benchmark fixture.
    """
    _benchmark(harness, benchmark, harness.modify_state)


@pytest.mark.parametrize("harness", ["private"], indirect=True)
def test_link_and_unlink(harness: SharedStateHarness, benchmark: BenchmarkFixture):
    """Benchmark linking a client to a shared token and unlinking it again.

    What a client pays on the ``on_load`` that joins it to a room. Both halves
    patch with ``full_delta=True``, which re-marks every Var of the state being
    swapped in and resolves the delta from the root, so this is the expensive
    end of the feature. The cycle leaves the client unlinked again, so every
    sample links from the same starting point.

    Args:
        harness: The unlinked scenario.
        benchmark: The codspeed benchmark fixture.
    """
    _benchmark(harness, benchmark, harness.link_events)


@pytest.mark.parametrize(
    "other_clients", [0, 1, FANOUT_CLIENTS], ids=lambda n: f"{n}_other_clients"
)
async def test_fanout_updates_every_linked_client(other_clients: int):
    """Verify the counter batch reaches every other client linked to the token.

    The fan-out is what the linked scenarios are measuring, and it is silently
    skipped for a token with no connected socket, so assert the updates land
    rather than benchmarking an empty task set.

    How the fan-out tasks for one event interleave with the next event is left
    to the loop, so only the measured client's own updates are checked in
    order; for the others it is the count of updates -- one per event, per
    client -- and where the shared counter ends up.

    Args:
        other_clients: How many other clients to link to the shared token.
    """
    updates: dict[str, list[int]] = {}

    def record(token: str, delta: Mapping[str, Mapping[str, Any]]) -> None:
        if (counter_delta := delta.get(COUNTER_FULL_NAME)) is not None:
            updates.setdefault(token, []).append(counter_delta[COUNTER_FIELD])

    scenario = Scenario(linked=True, other_clients=other_clients)
    async with _shared_state_app(scenario, record) as harness:
        updates.clear()
        events = _counter_events(PRIMARY_TOKEN)
        await harness.run_events(events, PRIMARY_TOKEN)

        assert updates[PRIMARY_TOKEN] == [1, 2, 1, 0]
        for index in range(other_clients):
            assert len(updates[_other_token(index)]) == len(events)

        root_state = await harness.state_manager.get_state(
            BaseStateToken(ident=SHARED_TOKEN, cls=SharedCounterState)
        )
        counter_state = await root_state.get_state(SharedCounterState)
        assert counter_state.counter == 0
