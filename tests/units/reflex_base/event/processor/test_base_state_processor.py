"""Tests for BaseStateEventProcessor, specifically the _rehydrate path."""

import asyncio
import dataclasses
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
