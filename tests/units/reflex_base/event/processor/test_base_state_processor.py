"""Tests for BaseStateEventProcessor, specifically the _rehydrate path."""

import traceback
from collections.abc import Mapping
from typing import Any

import pytest
import pytest_asyncio
from reflex_base.constants import CompileVars
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.event.context import EventContext
from reflex_base.event.processor import BaseStateEventProcessor
from reflex_base.registry import RegistrationContext

import reflex as rx
from reflex import event
from reflex.app import App
from reflex.event import Event
from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.token import BaseStateToken
from reflex.middleware.middleware import Middleware
from reflex.state import OnLoadInternalState, State, StateUpdate


@pytest.fixture
def _real_base_state_processor_obj() -> BaseStateEventProcessor:
    """A BaseStateEventProcessor with real (unmocked) _rehydrate.

    Returns:
        A fresh BaseStateEventProcessor instance.
    """

    def handle_backend_exception(ex: Exception) -> None:
        formatted_exc = "\n".join(traceback.format_exception(ex))
        pytest.fail(f"Event processor raised an unexpected exception:\n{formatted_exc}")

    return BaseStateEventProcessor(
        backend_exception_handler=handle_backend_exception,
        graceful_shutdown_timeout=2,
    )


@pytest.fixture
def emitted_deltas() -> list[tuple[str, Mapping[str, Mapping[str, Any]]]]:
    """List to capture emitted deltas.

    Returns:
        An empty list for collecting deltas.
    """
    return []


@pytest.fixture
def emitted_events() -> list[tuple[str, tuple[Event, ...]]]:
    """List to capture emitted events.

    Returns:
        An empty list for collecting events.
    """
    return []


@pytest_asyncio.fixture
async def real_base_state_processor(
    _real_base_state_processor_obj: BaseStateEventProcessor,
    emitted_deltas: list,
    emitted_events: list,
    clean_registration_context: RegistrationContext,
):
    """A fully wired BaseStateEventProcessor with real _rehydrate.

    Yields the processor (not yet started). The test must use ``async with processor`` to
    control the lifecycle and assert on emitted deltas after stop.

    Args:
        _real_base_state_processor_obj: The unmocked processor instance.
        emitted_deltas: List to capture emitted deltas.
        emitted_events: List to capture emitted events.
        clean_registration_context: Isolated registration context for the test.

    Yields:
        The configured but not-yet-started BaseStateEventProcessor.
    """
    clean_registration_context.register_base_state(OnLoadInternalState)
    state_manager = StateManagerMemory()

    async def emit_delta_impl(  # noqa: RUF029
        token: str, delta: Mapping[str, Mapping[str, Any]]
    ) -> None:
        emitted_deltas.append((token, delta))

    async def emit_event_impl(token: str, *events: Event) -> None:  # noqa: RUF029
        emitted_events.append((token, events))

    root_ctx = EventContext(
        token="",
        state_manager=state_manager,
        enqueue_impl=_real_base_state_processor_obj.enqueue_many,
        emit_delta_impl=emit_delta_impl,
        emit_event_impl=emit_event_impl,
    )
    _real_base_state_processor_obj._root_context = root_ctx

    yield _real_base_state_processor_obj

    await state_manager.close()


@pytest.fixture
def wired_app(
    app_module_mock,
    real_base_state_processor: BaseStateEventProcessor,
) -> App:
    """An App registered as the app module's app and sharing the processor's state manager.

    Args:
        app_module_mock: The mock app module fixture.
        real_base_state_processor: The unmocked BaseStateEventProcessor.

    Returns:
        The wired App instance.
    """
    app = app_module_mock.app = App()
    assert real_base_state_processor._root_context is not None
    app._state_manager = real_base_state_processor._root_context.state_manager
    return app


async def test_rehydrate_sets_is_hydrated_on_fresh_token(
    wired_app: App,
    real_base_state_processor: BaseStateEventProcessor,
    emitted_deltas: list[tuple[str, Mapping[str, Mapping[str, Any]]]],
    token: str,
):
    """A non-hydrate event against a fresh token triggers _rehydrate, emitting is_hydrated=True.

    When a token has never been seen before (no router_data on the state),
    and the event is not itself the hydrate event, the processor calls
    _rehydrate which runs State.hydrate. With no on_load events defined,
    hydrate sets is_hydrated=True directly.

    Args:
        wired_app: The App wired to the processor's state manager.
        real_base_state_processor: The unmocked BaseStateEventProcessor.
        emitted_deltas: List to capture emitted deltas.
        token: The client token.
    """

    class MyState(State):
        @event
        def noop(self):
            pass

    async with real_base_state_processor as processor:
        await processor.enqueue(
            token,
            Event.from_event_type(MyState.noop())[0],
        )
        await processor.join(1)

    state_name = State.get_full_name()
    is_hydrated_key = CompileVars.IS_HYDRATED + FIELD_MARKER
    hydrated_deltas = [
        d
        for _, d in emitted_deltas
        if state_name in d and d[state_name].get(is_hydrated_key) is True
    ]
    assert len(hydrated_deltas) >= 1, (
        f"Expected at least one delta with is_hydrated=True, got deltas: {emitted_deltas}"
    )


async def test_preprocess_update_routes_frontend_events_to_client(
    wired_app: App,
    real_base_state_processor: BaseStateEventProcessor,
    emitted_events: list[tuple[str, tuple[Event, ...]]],
    token: str,
):
    """Frontend-only events in a middleware preprocess update reach the client.

    Regression: a blocking middleware (e.g. an auth gate) returns a
    ``StateUpdate`` whose events are frontend specs like ``rx.toast``
    (``_call_function``) or ``rx.redirect`` (``_redirect``). Those have no
    registered backend handler, so they must be emitted to the client instead
    of enqueued on the backend queue (where they raise ``KeyError``).

    Args:
        wired_app: The App wired to the processor's state manager.
        real_base_state_processor: The unmocked BaseStateEventProcessor.
        emitted_events: List to capture events emitted to the client.
        token: The client token.
    """

    class GatedState(State):
        @event
        def do_thing(self):
            pass

    class BlockingMiddleware(Middleware):
        async def preprocess(self, app, state, event) -> StateUpdate:
            return StateUpdate(
                events=Event.from_event_type([
                    rx.toast("Action not allowed"),
                    rx.redirect("/login"),
                ])
            )

    wired_app.add_middleware(BlockingMiddleware())
    real_base_state_processor.middleware = wired_app

    async with real_base_state_processor as p:
        await p.enqueue(token, Event.from_event_type(GatedState.do_thing())[0])
        await p.join(1)

    client_event_names = {e.name for _, events in emitted_events for e in events}
    assert "_call_function" in client_event_names
    assert "_redirect" in client_event_names


async def test_background_event_does_not_discard_concurrent_foreground_write(
    wired_app: App,
    real_base_state_processor: BaseStateEventProcessor,
    emitted_deltas: list[tuple[str, Mapping[str, Mapping[str, Any]]]],
    token: str,
):
    """A foreground write racing a background task's completion reaches a delta.

    Regression: after dropping the state lock, the background branch passed
    ``root_state`` into ``process_event``, whose trailing ``chain_updates``
    snapshotted dirty vars, suspended (delta resolution / emit), and then ran
    ``_clean()`` -- all unlocked. On a shared state tree (opportunistic
    locking, or the in-memory manager used here) a foreground handler's write
    landing inside that snapshot->clean window was cleaned before any delta
    harvested it: the value never reached the frontend.

    The gates below force exactly that interleaving: the background task's
    trailing delta resolution (via the uncached async computed var) signals
    the foreground handler to write, then resumes -- pre-fix its ``_clean()``
    discarded the write mid-foreground-handler.

    Args:
        wired_app: The App wired to the processor's state manager.
        real_base_state_processor: The unmocked BaseStateEventProcessor.
        emitted_deltas: List to capture emitted deltas.
        token: The client token.
    """
    import asyncio
    import contextlib

    bg_started = asyncio.Event()
    bg_resolving = asyncio.Event()
    fg_wrote = asyncio.Event()
    hold_resolution = [False]

    class BgRaceState(State):
        victim: str = ""

        @rx.var(cache=False)
        async def window(self) -> int:
            # Uncached: recomputed in every delta. Once armed, the background
            # task's trailing delta resolution parks here until the foreground
            # handler has written -- holding the snapshot->clean window open.
            if hold_resolution[0]:
                bg_resolving.set()
                await fg_wrote.wait()
            return 0

        @event(background=True)
        async def bg(self):
            hold_resolution[0] = True
            bg_started.set()

        @event
        async def fg(self):
            # Bounded: with the fix, the background task does no trailing
            # delta work, so nothing ever sets bg_resolving.
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(bg_resolving.wait(), timeout=0.5)
            self.victim = "written"
            fg_wrote.set()
            # Yield so the background task's (pre-fix) clean can land while
            # this handler is still mid-flight, as a real await would allow.
            for _ in range(20):
                await asyncio.sleep(0)

    # Seed router_data up front so no event triggers _rehydrate (whose
    # full-dict resolution would park on the armed gate before the foreground
    # handler could run) and no event needs to carry router_data of its own.
    assert real_base_state_processor._root_context is not None
    state_manager = real_base_state_processor._root_context.state_manager
    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=State)
    ) as seed_root:
        seed_root.router_data = {"pathname": "/", "query": {}}
    try:
        async with real_base_state_processor as processor:
            await processor.enqueue(token, Event.from_event_type(BgRaceState.bg())[0])
            await asyncio.wait_for(bg_started.wait(), timeout=2)
            await processor.enqueue(token, Event.from_event_type(BgRaceState.fg())[0])
            await processor.join(5)
    finally:
        # The uncached computed var registered BgRaceState as an always-dirty
        # substate on the shared State class; later tests' state trees don't
        # contain it and would KeyError in get_delta (see reload_state_module).
        State._always_dirty_substates.discard(BgRaceState.get_name())

    state_name = BgRaceState.get_full_name()
    victim_key = "victim" + FIELD_MARKER
    delivered = [
        d[state_name][victim_key]
        for _, d in emitted_deltas
        if state_name in d and d[state_name].get(victim_key) == "written"
    ]
    assert delivered, (
        "The foreground handler's write never reached any delta; it was "
        "cleaned by the background task's unlocked trailing update. Deltas: "
        f"{emitted_deltas}"
    )
