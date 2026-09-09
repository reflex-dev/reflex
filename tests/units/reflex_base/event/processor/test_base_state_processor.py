"""Tests for BaseStateEventProcessor, specifically the _rehydrate path."""

import asyncio
import contextlib
import dataclasses
import logging
import traceback
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from reflex_base.constants import CompileVars, RouteVar
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.environment import environment
from reflex_base.event.context import EventContext
from reflex_base.event.processor import BaseStateEventProcessor
from reflex_base.registry import RegistrationContext

import reflex as rx
from reflex import event
from reflex.app import App
from reflex.event import Event
from reflex.istate.manager import StateManager
from reflex.istate.manager.disk import StateManagerDisk
from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.redis import StateManagerRedis
from reflex.istate.manager.token import BaseStateToken
from reflex.middleware.middleware import Middleware
from reflex.state import BaseState, OnLoadInternalState, State, StateUpdate
from tests.units.mock_redis import mock_redis

# Class-level registries on State that registering a substate, or installing a
# dynamic route arg, writes into with no removal path.
_STATE_REGISTRIES = (
    "vars",
    "computed_vars",
    "_var_dependencies",
    "_potentially_dirty_states",
    "_always_dirty_computed_vars",
    "_always_dirty_substates",
    "_interval_computed_var_names",
    "_fast_attr_names",
)


def _snapshot_registry(value: Any) -> Any:
    """Copy a registry deeply enough that mutating the original cannot reach it.

    Args:
        value: The registry to copy.

    Returns:
        The copy, or the value itself when it is immutable.
    """
    if isinstance(value, dict):
        return {k: set(v) if isinstance(v, set) else v for k, v in value.items()}
    if isinstance(value, set):
        return set(value)
    return value


def _restore_registry(cls: type[BaseState], name: str, value: Any) -> None:
    """Put a registry back, in place where the container is shared by reference.

    Args:
        cls: The state class to restore on.
        name: The registry name.
        value: The snapshotted value.
    """
    current = getattr(cls, name)
    if isinstance(current, (dict, set)):
        current.clear()
        current.update(value)  # pyright: ignore[reportArgumentType]
    else:
        setattr(cls, name, value)


def _state_tree(cls: type[BaseState]) -> list[type[BaseState]]:
    """The state class and every substate registered under it.

    Args:
        cls: The root of the tree.

    Returns:
        The class followed by its substates, depth first.
    """
    return [cls, *(s for sub in cls.get_substates() for s in _state_tree(sub))]


@pytest.fixture(autouse=True)
def _isolate_state_class_registries(clean_registration_context: RegistrationContext):
    """Undo what a test leaves on state classes that outlive it.

    Defining a substate writes into ``State``'s dependency dicts, and
    ``add_page`` on a dynamic route installs the arg on ``State`` and copies it
    into the ``vars`` of every substate registered at the time -- including
    framework ones like ``OnLoadInternalState``.

    Args:
        clean_registration_context: Requested so this tears down while the
            test's substate registrations are still resolvable.

    Yields:
        None.
    """
    snapshot = {
        name: _snapshot_registry(getattr(State, name)) for name in _STATE_REGISTRIES
    }
    known_vars = set(State.computed_vars)

    yield

    for name in set(State.computed_vars) - known_vars:
        with contextlib.suppress(AttributeError):
            delattr(State, name)
        for cls in _state_tree(State):
            cls.vars.pop(name, None)
            cls.inherited_vars.pop(name, None)
    for name, value in snapshot.items():
        _restore_registry(State, name, value)


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
async def processor_state_manager(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """The state manager backing the processor.

    Defaults to the in-memory manager. Tests that care about how much of the
    state tree a manager materializes parametrize this indirectly with
    "in_process", "disk" or "redis".

    Args:
        request: pytest request object, whose optional param selects the manager.
        monkeypatch: pytest monkeypatch fixture.
        tmp_path: Per-test directory for the disk manager to persist into.

    Yields:
        The state manager.
    """
    kind = getattr(request, "param", "in_process")
    state_manager: StateManager
    if kind == "redis":
        state_manager = StateManagerRedis(redis=mock_redis())
    elif kind == "disk":
        # Resolved once in __post_init__, and the manager both purges and
        # persists there, so keep it out of the process-wide states directory.
        monkeypatch.setenv(environment.REFLEX_STATES_WORKDIR.name, str(tmp_path))
        state_manager = StateManagerDisk()
    else:
        state_manager = StateManagerMemory()

    yield state_manager

    await state_manager.close()


@pytest.fixture
def real_base_state_processor(
    _real_base_state_processor_obj: BaseStateEventProcessor,
    emitted_deltas: list,
    emitted_events: list,
    clean_registration_context: RegistrationContext,
    processor_state_manager: StateManager,
):
    """A fully wired BaseStateEventProcessor with real _rehydrate.

    Yields the processor (not yet started). The test must use ``async with processor`` to
    control the lifecycle and assert on emitted deltas after stop.

    Args:
        _real_base_state_processor_obj: The unmocked processor instance.
        emitted_deltas: List to capture emitted deltas.
        emitted_events: List to capture emitted events.
        clean_registration_context: Isolated registration context for the test.
        processor_state_manager: The state manager to back the processor.

    Returns:
        The configured but not-yet-started BaseStateEventProcessor.
    """
    clean_registration_context.register_base_state(OnLoadInternalState)
    state_manager = processor_state_manager

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

    return _real_base_state_processor_obj


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

    Every step is gate-driven, in both worlds: pre-fix, the background
    task's trailing delta resolution (via the uncached async computed var)
    parks until the foreground handler has written, and the background
    event's future completes strictly after its trailing ``_clean()``; on
    fixed code that future completes without any trailing resolution and
    the foreground handler proceeds immediately.

    Args:
        wired_app: The App wired to the processor's state manager.
        real_base_state_processor: The unmocked BaseStateEventProcessor.
        emitted_deltas: List to capture emitted deltas.
        token: The client token.
    """
    bg_started = asyncio.Event()
    bg_resolving = asyncio.Event()
    fg_wrote = asyncio.Event()
    hold_resolution = [False]
    bg_future_box: list = []

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
            # Enter the context once so the never-entered compatibility flush
            # (which runs under the lock) stays out of this choreography; arm
            # the gate only afterwards so the context exit resolves unparked.
            async with self:
                pass
            hold_resolution[0] = True
            bg_started.set()

        @event
        async def fg(self):
            # Proceed once the background trailing resolution has taken its
            # snapshot (pre-fix code parks it on fg_wrote), or once the
            # background event has fully completed without one (fixed code).
            waiter = asyncio.ensure_future(bg_resolving.wait())
            await asyncio.wait(
                [waiter, *bg_future_box], return_when=asyncio.FIRST_COMPLETED
            )
            waiter.cancel()
            self.victim = "written"
            fg_wrote.set()
            # Pre-fix, the parked resolution now resumes, emits, and cleans;
            # the background event's future completes strictly after that
            # clean, so awaiting it guarantees the clean landed before this
            # handler's own delta snapshot. On fixed code it is already done.
            await asyncio.wait(bg_future_box)

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
            bg_future_box.append(
                await processor.enqueue(
                    token, Event.from_event_type(BgRaceState.bg())[0]
                )
            )
            started = asyncio.ensure_future(bg_started.wait())
            await asyncio.wait([started], timeout=2)
            started.cancel()
            assert bg_started.is_set(), "background handler never started"
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


async def test_background_yield_inside_context_flushes_delta_before_event(
    wired_app: App,
    real_base_state_processor: BaseStateEventProcessor,
    token: str,
):
    """A yield inside ``async with self`` emits the delta before the event.

    A background generator suspended at a yield inside its proxy context
    still holds the state lock, so flushing the delta there is safe and
    preserves the documented ordering: frontend events are processed with
    the latest state. Only yields outside the context (no lock) must skip
    the flush.

    Args:
        wired_app: The App wired to the processor's state manager.
        real_base_state_processor: The unmocked BaseStateEventProcessor.
        token: The client token.
    """
    timeline: list[tuple[str, Any]] = []
    root_ctx = real_base_state_processor._root_context
    assert root_ctx is not None

    async def record_delta(tok: str, delta: Mapping[str, Mapping[str, Any]]) -> None:  # noqa: RUF029
        timeline.append(("delta", delta))

    async def record_event(tok: str, *events: Event) -> None:  # noqa: RUF029
        timeline.append(("event", tuple(ev.name for ev in events)))

    object.__setattr__(root_ctx, "emit_delta_impl", record_delta)
    object.__setattr__(root_ctx, "emit_event_impl", record_event)

    class BgYieldOrderState(State):
        marker: str = ""

        @event(background=True)
        async def bg_yield(self):
            async with self:
                self.marker = "set"
                yield rx.call_script("void 0")

    state_manager = root_ctx.state_manager
    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=State)
    ) as seed_root:
        seed_root.router_data = {"pathname": "/", "query": {}}

    async with real_base_state_processor as processor:
        await processor.enqueue(
            token, Event.from_event_type(BgYieldOrderState.bg_yield())[0]
        )
        await processor.join(5)

    state_name = BgYieldOrderState.get_full_name()
    marker_key = "marker" + FIELD_MARKER
    delta_index = next(
        (
            index
            for index, (kind, payload) in enumerate(timeline)
            if kind == "delta" and payload.get(state_name, {}).get(marker_key) == "set"
        ),
        None,
    )
    event_index = next(
        (
            index
            for index, (kind, payload) in enumerate(timeline)
            if kind == "event" and "_call_script" in payload
        ),
        None,
    )
    assert delta_index is not None, f"marker delta never emitted: {timeline}"
    assert event_index is not None, f"yielded event never emitted: {timeline}"
    assert delta_index < event_index, (
        "The yielded frontend event was emitted before the delta for the "
        f"mutation made in the same proxy context: {timeline}"
    )


async def test_background_event_without_context_still_flushes_a_delta(
    wired_app: App,
    real_base_state_processor: BaseStateEventProcessor,
    emitted_deltas: list[tuple[str, Mapping[str, Mapping[str, Any]]]],
    token: str,
):
    """A background handler with no ``async with self`` still flushes a delta.

    Backward compatibility: before the unlocked trailing flush was removed,
    every background event emitted a delta, which is what refreshed uncached
    computed vars for apps driving re-renders off a bare background tick.
    That flush now runs under the state lock instead of disappearing.

    Args:
        wired_app: The App wired to the processor's state manager.
        real_base_state_processor: The unmocked BaseStateEventProcessor.
        emitted_deltas: List to capture emitted deltas.
        token: The client token.
    """

    class NoContextBgState(State):
        @rx.var(cache=False)
        def beat(self) -> int:
            return 7

        @event(background=True)
        async def bg(self):
            pass

    assert real_base_state_processor._root_context is not None
    state_manager = real_base_state_processor._root_context.state_manager
    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=State)
    ) as seed_root:
        seed_root.router_data = {"pathname": "/", "query": {}}

    try:
        async with real_base_state_processor as processor:
            await processor.enqueue(
                token, Event.from_event_type(NoContextBgState.bg())[0]
            )
            await processor.join(5)
    finally:
        State._always_dirty_substates.discard(NoContextBgState.get_name())

    state_name = NoContextBgState.get_full_name()
    beat_key = "beat" + FIELD_MARKER
    assert any(d.get(state_name, {}).get(beat_key) == 7 for _, d in emitted_deltas), (
        f"no delta refreshed the uncached var: {emitted_deltas}"
    )


async def test_background_event_raising_without_context_still_flushes_a_delta(
    wired_app: App,
    real_base_state_processor: BaseStateEventProcessor,
    emitted_deltas: list[tuple[str, Mapping[str, Mapping[str, Any]]]],
    token: str,
):
    """A background handler that raises before ``async with self`` still flushes.

    Regression: the compatibility flush for handlers that never enter their
    proxy context ran only after a normal return, so a raising handler
    propagated the exception before the flush and no delta was emitted --
    unlike every non-raising no-context background handler. The flush now
    runs in a finally, and the exception still reaches the backend
    exception handler afterwards.

    Args:
        wired_app: The App wired to the processor's state manager.
        real_base_state_processor: The unmocked BaseStateEventProcessor.
        emitted_deltas: List to capture emitted deltas.
        token: The client token.
    """
    handled: list[Exception] = []

    class RaisingBgState(State):
        @rx.var(cache=False)
        def beat(self) -> int:
            return 11

        @event(background=True)
        async def bg_raises(self):
            msg = "boom"
            raise RuntimeError(msg)

    real_base_state_processor.backend_exception_handler = handled.append

    assert real_base_state_processor._root_context is not None
    state_manager = real_base_state_processor._root_context.state_manager
    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=State)
    ) as seed_root:
        seed_root.router_data = {"pathname": "/", "query": {}}

    try:
        async with real_base_state_processor as processor:
            await processor.enqueue(
                token, Event.from_event_type(RaisingBgState.bg_raises())[0]
            )
            await processor.join(5)
    finally:
        State._always_dirty_substates.discard(RaisingBgState.get_name())

    state_name = RaisingBgState.get_full_name()
    beat_key = "beat" + FIELD_MARKER
    assert any(d.get(state_name, {}).get(beat_key) == 11 for _, d in emitted_deltas), (
        f"no delta refreshed the uncached var after the handler raised: {emitted_deltas}"
    )
    assert [type(ex) for ex in handled] == [RuntimeError], (
        f"the handler's exception did not reach the backend handler: {handled}"
    )


async def test_background_flush_failure_does_not_mask_handler_exception(
    wired_app: App,
    real_base_state_processor: BaseStateEventProcessor,
    token: str,
    caplog: pytest.LogCaptureFixture,
):
    """A failing compat flush must not replace a raised handler's exception.

    Regression: with the flush running after the handler raised, a flush
    failure (e.g. an uncached computed var throwing during delta
    resolution) replaced the handler's exception, so the backend exception
    handler received the flush error instead of the actionable application
    error. The flush failure is now logged and the handler's exception
    still propagates.

    Args:
        wired_app: The App wired to the processor's state manager.
        real_base_state_processor: The unmocked BaseStateEventProcessor.
        token: The client token.
        caplog: Fixture capturing log records.
    """
    handled: list[Exception] = []
    handler_ran: list[bool] = []

    class MaskingBgState(State):
        @rx.var(cache=False)
        def beat(self) -> int:
            if handler_ran:
                msg = "flush boom"
                raise ValueError(msg)
            return 13

        @event(background=True)
        async def bg_raises(self):
            handler_ran.append(True)
            msg = "boom"
            raise RuntimeError(msg)

    real_base_state_processor.backend_exception_handler = handled.append

    assert real_base_state_processor._root_context is not None
    state_manager = real_base_state_processor._root_context.state_manager
    async with state_manager.modify_state(
        BaseStateToken(ident=token, cls=State)
    ) as seed_root:
        seed_root.router_data = {"pathname": "/", "query": {}}

    try:
        async with real_base_state_processor as processor:
            await processor.enqueue(
                token, Event.from_event_type(MaskingBgState.bg_raises())[0]
            )
            with caplog.at_level(
                logging.ERROR, logger="reflex_base.event.processor.base_state_processor"
            ):
                await processor.join(5)
    finally:
        State._always_dirty_substates.discard(MaskingBgState.get_name())

    assert [type(ex) for ex in handled] == [RuntimeError], (
        f"the flush failure masked the handler's exception: {handled}"
    )
    assert any(
        record.exc_info and record.exc_info[0] is ValueError
        for record in caplog.records
    ), f"the flush failure was not logged: {caplog.records}"


async def test_chained_event_keeps_originating_router_data(
    wired_app: App,
    real_base_state_processor: BaseStateEventProcessor,
    token: str,
):
    """A yielded event resolves route args against the view that produced it.

    Regression: chained events were created with no ``router_data``, and the
    processor only refreshes ``state.router`` when an event carries some. A
    chained event therefore read whichever router the last client-sent event
    happened to leave on the root state. A loader that yields the real loader
    (a common on_load shape) could see another page's route, and a route arg
    would read as "" on a page whose URL clearly names one.

    Args:
        wired_app: The App wired to the processor's state manager.
        real_base_state_processor: The unmocked BaseStateEventProcessor.
        token: The client token.
    """
    item_view = {
        "pathname": "/item/[item_id]",
        "asPath": "/item/abc",
        "query": {"item_id": "abc"},
    }
    other_view = {"pathname": "/other", "asPath": "/other", "query": {}}

    # Ordered by a barrier, not sleeps: were `touch` to land second, `note`
    # would read the view it wanted anyway and the test would prove nothing.
    router_moved = asyncio.Event()

    class RouterState(State):
        seen: list[str] = []

        @event
        def note(self):
            item_id = self.router._page.params.get("item_id", "")
            self.seen = [*self.seen, f"{self.router.url.path}|{item_id}"]

        @event
        def touch(self):
            """A client-sent event on another page; it moves the shared router.

            The processor assigns `state.router` before the handler body runs,
            so by here the move has happened.
            """
            router_moved.set()

        @event(background=True)
        async def outer(self):
            # wait_for rather than asyncio.timeout: this package supports 3.10.
            await asyncio.wait_for(router_moved.wait(), timeout=5)
            yield RouterState.note

    def client_event(spec, router_data: dict[str, Any]) -> Event:
        return dataclasses.replace(
            Event.from_event_type(spec)[0], router_data=router_data
        )

    async with real_base_state_processor as processor:
        await processor.enqueue(token, client_event(RouterState.outer(), item_view))
        await processor.enqueue(token, client_event(RouterState.touch(), other_view))
        await processor.join(10)

    root_ctx = real_base_state_processor._root_context
    assert root_ctx is not None
    state = await root_ctx.state_manager.get_state(
        BaseStateToken(ident=token, cls=State)
    )
    assert (await state.get_state(RouterState)).seen == ["/item/abc|abc"]


async def test_ensure_locked_returns_a_root_only_while_the_lock_is_held(
    wired_app: App,
    real_base_state_processor: BaseStateEventProcessor,
    token: str,
):
    """ensure_locked passes a locked root through and refuses everything else.

    Foreground callers hand in the root they locked; a plain substate or an
    un-entered proxy holds no lock, so there is nothing safe to flush.

    Args:
        wired_app: The App wired to the processor's state manager.
        real_base_state_processor: The unmocked BaseStateEventProcessor.
        token: The client token.
    """
    from reflex_base.event.processor.base_state_processor import ensure_locked

    from reflex.istate.proxy import StateProxy

    root_ctx = real_base_state_processor._root_context
    assert root_ctx is not None
    EventContext.set(root_ctx.fork(token=token))
    root = await root_ctx.state_manager.get_state(
        BaseStateToken(ident=token, cls=State)
    )
    substate = await root.get_state(OnLoadInternalState)

    assert ensure_locked(substate, root) is root
    assert ensure_locked(substate, None) is None
    assert ensure_locked(StateProxy(substate), None) is None


async def test_failed_context_enter_does_not_mark_the_proxy_entered(
    wired_app: App,
    real_base_state_processor: BaseStateEventProcessor,
    token: str,
):
    """A proxy whose enter failed still gets the compatibility flush.

    The entered flag means "a context opened whose exit will flush". If
    ``__aenter__`` raises before that and the handler swallows it, the
    processor must still run the locked fallback flush, or preamble dirty
    vars like router_data would never reach a delta.

    Args:
        wired_app: The App wired to the processor's state manager.
        real_base_state_processor: The unmocked BaseStateEventProcessor.
        token: The client token.
    """
    from reflex.istate.proxy import StateProxy

    root_ctx = real_base_state_processor._root_context
    assert root_ctx is not None
    EventContext.set(root_ctx.fork(token=token))
    root = await root_ctx.state_manager.get_state(
        BaseStateToken(ident=token, cls=State)
    )
    substate = await root.get_state(OnLoadInternalState)

    proxy = StateProxy(substate)

    def raise_on_modify(*args, **kwargs):
        msg = "state manager unavailable"
        raise RuntimeError(msg)

    original = root_ctx.state_manager.modify_state_with_links
    object.__setattr__(
        root_ctx.state_manager, "modify_state_with_links", raise_on_modify
    )
    try:
        with pytest.raises(RuntimeError, match="state manager unavailable"):
            async with proxy:
                pass
    finally:
        object.__setattr__(root_ctx.state_manager, "modify_state_with_links", original)

    assert proxy._self_entered_context is False


def _client_event(spec: Any, router_data: dict[str, Any]) -> Event:
    """Build an event the way the socket layer delivers one: carrying router_data.

    Args:
        spec: The event spec to build the event from.
        router_data: The router data the client sent the event with.

    Returns:
        The event.
    """
    return dataclasses.replace(Event.from_event_type(spec)[0], router_data=router_data)


def _view(path: str, as_path: str | None = None, **query: str) -> dict[str, Any]:
    """The router_data the socket layer builds for a page view.

    ``pathname`` is the matched route (``/item/[item_id]``) and ``asPath`` the
    URL the client is actually on (``/item/abc``); see
    ``EventNamespace.on_event``.

    Args:
        path: The matched route.
        as_path: The client's URL, defaulting to the matched route.
        query: The route and query params for the view.

    Returns:
        A router_data dict.
    """
    return {
        RouteVar.PATH: path,
        RouteVar.ORIGIN: as_path if as_path is not None else path,
        RouteVar.QUERY: query,
    }


@contextlib.asynccontextmanager
async def _read_back(processor: BaseStateEventProcessor, token: str):
    """Read the token's final state through the lock.

    ``StateManagerRedis.get_state`` goes straight to redis, which under
    opportunistic locking has not yet seen the writes still held in the
    lease's cached copy.

    Args:
        processor: The processor whose state manager holds the token.
        token: The client token.

    Yields:
        The root state.
    """
    root_ctx = processor._root_context
    assert root_ctx is not None
    async with root_ctx.state_manager.modify_state(
        BaseStateToken(ident=token, cls=State)
    ) as root:
        yield root


async def _send(
    processor: BaseStateEventProcessor, token: str, ev: Event, timeout: float = 10
) -> None:
    """Enqueue an event and wait for it and everything it chains.

    ``processor.join()`` only drains the queue, which can empty between an
    event finishing and the events it chained being put on it, so the on_load
    chain these tests are about is not covered by it.

    Args:
        processor: The processor to enqueue against.
        token: The client token.
        ev: The event to enqueue.
        timeout: Seconds to wait for the chain to finish.
    """
    future = await processor.enqueue(token, ev)
    await asyncio.wait_for(future.wait_all(), timeout=timeout)


@pytest.mark.parametrize(
    "processor_state_manager", ["in_process", "disk", "redis"], indirect=True
)
async def test_rehydrate_runs_on_load_for_the_incoming_events_route(
    wired_app: App,
    real_base_state_processor: BaseStateEventProcessor,
    token: str,
):
    """The compatibility rehydrate loads the page the event came from.

    Once a token's state has expired, the next event arrives against a fresh
    tree with no ``router_data`` and the processor rehydrates it before running
    the handler. ``on_load`` is page dependent, so that rehydrate has to
    resolve the route from the event that triggered it: anything else runs
    another page's loader, or the 404 loader, against a client that is plainly
    somewhere else.

    Args:
        wired_app: The App wired to the processor's state manager.
        real_base_state_processor: The unmocked BaseStateEventProcessor.
        token: The client token.
    """

    class RouteLoadState(State):
        loaded: list[str] = []

        @event
        def load_a(self):
            self.loaded = [*self.loaded, "a"]

        @event
        def load_b(self):
            self.loaded = [*self.loaded, "b"]

        @event
        def load_404(self):
            self.loaded = [*self.loaded, "404"]

        @event
        def ping(self):
            pass

    wired_app.add_page(
        lambda: rx.text("a"), route="/page-a", on_load=RouteLoadState.load_a
    )
    wired_app.add_page(
        lambda: rx.text("b"), route="/page-b", on_load=RouteLoadState.load_b
    )
    wired_app.add_page(
        lambda: rx.text("404"), route="/404", on_load=RouteLoadState.load_404
    )

    async with real_base_state_processor as processor:
        await _send(
            processor, token, _client_event(RouteLoadState.ping(), _view("/page-b"))
        )

    async with _read_back(real_base_state_processor, token) as root:
        assert (await root.get_state(RouteLoadState)).loaded == ["b"], (
            "the rehydrate ran a loader for a page the event did not come from"
        )
        assert root.router.url.path == "/page-b"
        assert (await root.get_state(State)).is_hydrated is True


async def test_rehydrate_after_expiry_does_not_reload_the_previous_route(
    wired_app: App,
    real_base_state_processor: BaseStateEventProcessor,
    token: str,
):
    """A state that expired on one page rehydrates against the client's new page.

    The client navigates from ``/page-a`` to ``/page-b`` while the backend
    drops the token's state. The next event carries the ``/page-b`` view, so
    the rehydrate it triggers must not resurrect ``/page-a``'s loader from
    whatever the previous event left behind.

    Args:
        wired_app: The App wired to the processor's state manager.
        real_base_state_processor: The unmocked BaseStateEventProcessor.
        token: The client token.
    """

    class ExpiredLoadState(State):
        loaded: list[str] = []

        @event
        def load_a(self):
            self.loaded = [*self.loaded, "a"]

        @event
        def load_b(self):
            self.loaded = [*self.loaded, "b"]

        @event
        def ping(self):
            pass

    wired_app.add_page(
        lambda: rx.text("a"), route="/page-a", on_load=ExpiredLoadState.load_a
    )
    wired_app.add_page(
        lambda: rx.text("b"), route="/page-b", on_load=ExpiredLoadState.load_b
    )

    root_ctx = real_base_state_processor._root_context
    assert root_ctx is not None
    state_manager = root_ctx.state_manager

    async with real_base_state_processor as processor:
        # A first event settles the state on /page-a.
        await _send(
            processor, token, _client_event(ExpiredLoadState.ping(), _view("/page-a"))
        )
        # The token's state expires out from under the still-connected client.
        # Only the in-memory manager is driven here; expiry is a manager
        # concern, and what it leaves the processor with -- a fresh tree for a
        # known token -- is what the other managers are exercised on above.
        assert isinstance(state_manager, StateManagerMemory)
        state_manager.states.pop(token)
        # The client, now on /page-b, sends the next event.
        await _send(
            processor, token, _client_event(ExpiredLoadState.ping(), _view("/page-b"))
        )

    async with _read_back(real_base_state_processor, token) as root:
        assert (await root.get_state(ExpiredLoadState)).loaded == ["b"], (
            "the post-expiry rehydrate loaded the route the client had left"
        )
        assert root.router.url.path == "/page-b"


@pytest.mark.parametrize(
    "processor_state_manager", ["in_process", "disk", "redis"], indirect=True
)
async def test_rehydrate_resolves_dynamic_route_args_of_the_incoming_event(
    wired_app: App,
    real_base_state_processor: BaseStateEventProcessor,
    token: str,
):
    """A rehydrated dynamic page loads with the event's own route args.

    The loader for ``/item/[item_id]`` is useless without ``item_id``: the
    rehydrate has to seed ``router`` from the incoming event before chaining
    ``on_load``, or the loader reads an empty arg on a URL that plainly names
    one.

    Args:
        wired_app: The App wired to the processor's state manager.
        real_base_state_processor: The unmocked BaseStateEventProcessor.
        token: The client token.
    """

    class DynamicLoadState(State):
        seen: list[str] = []

        @event
        def load_item(self):
            item_id = self.item_id  # pyright: ignore[reportAttributeAccessIssue]
            self.seen = [*self.seen, f"{self.router.url.path}|{item_id}"]

        @event
        def ping(self):
            pass

    wired_app.add_page(
        lambda: rx.text("item"),
        route="/item/[item_id]",
        on_load=DynamicLoadState.load_item,
    )
    wired_app.add_page(
        lambda: rx.text("other"), route="/other", on_load=DynamicLoadState.load_item
    )

    async with real_base_state_processor as processor:
        await _send(
            processor,
            token,
            _client_event(
                DynamicLoadState.ping(),
                _view("/item/[item_id]", "/item/abc", item_id="abc"),
            ),
        )

    async with _read_back(real_base_state_processor, token) as root:
        assert (await root.get_state(DynamicLoadState)).seen == ["/item/abc|abc"]


async def test_event_without_router_data_hydrates_once_without_loaders(
    wired_app: App,
    real_base_state_processor: BaseStateEventProcessor,
    emitted_deltas: list[tuple[str, Mapping[str, Mapping[str, Any]]]],
    token: str,
):
    """A backend-initiated event hydrates an expired state, but only once.

    Regression: the rehydrate ran ``on_load_internal`` against the empty
    route, whose loaders (the 404 ones) chained events that carried no
    ``router_data`` either and rehydrated again, fanning out until the queue
    was shut down. Nothing sets ``router_data`` on this path, so the rehydrate
    also has to stop repeating itself.

    Args:
        wired_app: The App wired to the processor's state manager.
        real_base_state_processor: The unmocked BaseStateEventProcessor.
        emitted_deltas: List to capture emitted deltas.
        token: The client token.
    """

    class BackendPushState(State):
        loaded: list[str] = []

        @event
        def load_index(self):
            self.loaded = [*self.loaded, "index"]

        @event
        def load_404(self):
            self.loaded = [*self.loaded, "404"]

        @event
        def ping(self):
            pass

    wired_app.add_page(
        lambda: rx.text("i"), route="/", on_load=BackendPushState.load_index
    )
    wired_app.add_page(
        lambda: rx.text("404"), route="/404", on_load=BackendPushState.load_404
    )

    async with real_base_state_processor as processor:
        # join, not the event's future: pre-fix the fan-out outruns wait_all.
        for _ in range(2):
            await processor.enqueue(
                token, Event.from_event_type(BackendPushState.ping())[0]
            )
            await processor.join(1)

    async with _read_back(real_base_state_processor, token) as root:
        assert (await root.get_state(BackendPushState)).loaded == []
        assert (await root.get_state(State)).is_hydrated is True

    state_name = State.get_full_name()
    is_hydrated_key = CompileVars.IS_HYDRATED + FIELD_MARKER
    hydrate_deltas = [
        d
        for _, d in emitted_deltas
        if d.get(state_name, {}).get(is_hydrated_key) is False
    ]
    assert len(hydrate_deltas) == 1, "the second event hydrated the state again"


async def test_routed_event_after_a_routeless_rehydrate_loads_its_page(
    wired_app: App,
    real_base_state_processor: BaseStateEventProcessor,
    token: str,
):
    """Hydrating without a route does not consume the page's on_load.

    A backend-initiated event leaves the state hydrated but still routeless,
    so the first event that does carry a route still owes it its loaders.

    Args:
        wired_app: The App wired to the processor's state manager.
        real_base_state_processor: The unmocked BaseStateEventProcessor.
        token: The client token.
    """

    class MixedOriginState(State):
        loaded: list[str] = []

        @event
        def load_a(self):
            self.loaded = [*self.loaded, "a"]

        @event
        def load_b(self):
            self.loaded = [*self.loaded, "b"]

        @event
        def ping(self):
            pass

    wired_app.add_page(
        lambda: rx.text("a"), route="/page-a", on_load=MixedOriginState.load_a
    )
    wired_app.add_page(
        lambda: rx.text("b"), route="/page-b", on_load=MixedOriginState.load_b
    )

    async with real_base_state_processor as processor:
        await _send(processor, token, Event.from_event_type(MixedOriginState.ping())[0])
        await _send(
            processor, token, _client_event(MixedOriginState.ping(), _view("/page-b"))
        )

    async with _read_back(real_base_state_processor, token) as root:
        assert (await root.get_state(MixedOriginState)).loaded == ["b"]
