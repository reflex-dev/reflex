"""Test linked state."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Generator

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect
from reflex_base.config import get_config

from reflex.testing import AppHarness

from . import utils


def LinkedStateApp():
    """Test that linked state works as expected."""
    import uuid
    from typing import Any

    import reflex as rx

    class SharedState(rx.SharedState):
        _who: str = "world"
        n_changes: int = 0
        counter: int = 0
        event_seen_linked_to: str = ""

        @rx.event
        def set_counter(self, value: int) -> None:
            self.counter = value

        @rx.event
        def set_who(self, who: str) -> None:
            self._who = who
            self.n_changes += 1

        @rx.event
        async def link_to(self, token: str):
            await self._link_to(token)

        @rx.event
        async def link_to_and_increment(self):
            linked_state = await self._link_to(f"arbitrary-token-{uuid.uuid4()}")
            linked_state.counter += 1

        @rx.event
        async def unlink(self):
            return await self._unlink()

        @rx.event
        def record_event_link_status(self):
            self.event_seen_linked_to = self._linked_to

        @rx.event
        def clear_event_link_status(self):
            self.event_seen_linked_to = ""

        @rx.event
        async def on_load_link_default(self):
            linked_state = await self._link_to(self.room or "default")  # pyright: ignore[reportAttributeAccessIssue]
            if self.room:  # pyright: ignore[reportAttributeAccessIssue]
                assert linked_state._linked_to == self.room  # pyright: ignore[reportAttributeAccessIssue]
            else:
                assert linked_state._linked_to == "default"

        @rx.event
        async def handle_submit(self, form_data: dict[str, Any]):
            if "who" in form_data:
                self.set_who(form_data["who"])
            if "token" in form_data:
                await self.link_to(form_data["token"])

    class SharedNotes(rx.SharedState):
        """A second SharedState to test multi-SharedState propagation."""

        note: str = ""

        @rx.event
        async def on_load_link_default(self):
            linked_state = await self._link_to(self.room or "default")  # pyright: ignore[reportAttributeAccessIssue]
            initial_note = self.router.page.params.get("initial_note", "")
            if initial_note:
                linked_state.note = initial_note

    class PrivateState(rx.State):
        fetched_note: str = ""

        @rx.var
        async def greeting(self) -> str:
            ss = await self.get_state(SharedState)
            return f"Hello, {ss._who}!"

        @rx.var
        async def linked_to(self) -> str:
            ss = await self.get_state(SharedState)
            return ss._linked_to

        @rx.event
        async def fetch_shared_note(self):
            """Fetch SharedNotes via get_state from an unrelated state handler."""
            sn = await self.get_state(SharedNotes)
            self.fetched_note = sn.note

        @rx.event(background=True)
        async def bump_counter_bg(self):
            for _ in range(5):
                async with self:
                    ss = await self.get_state(SharedState)
                    ss.counter += 1
            async with self:
                ss = await self.get_state(SharedState)
            for _ in range(5):
                async with ss:
                    ss.counter += 1

        @rx.event
        async def bump_counter_yield(self):
            ss = await self.get_state(SharedState)
            for _ in range(5):
                ss.counter += 1
                yield

        @rx.event
        def reset_self(self):
            self.reset()

    class RaceState(rx.State):
        """State with multiple async vars that race for the linked token lock."""

        trigger: int = 0

        @rx.var
        async def race_val_0(self) -> str:
            n = self.trigger
            ss = await self.get_state(SharedState)
            return f"{n}-{ss.counter}"

        @rx.var
        async def race_val_1(self) -> str:
            n = self.trigger
            ss = await self.get_state(SharedState)
            return f"{n}-{ss.counter}"

        @rx.var
        async def race_val_2(self) -> str:
            n = self.trigger
            ss = await self.get_state(SharedState)
            return f"{n}-{ss.counter}"

        @rx.var
        async def race_val_3(self) -> str:
            n = self.trigger
            ss = await self.get_state(SharedState)
            return f"{n}-{ss.counter}"

        @rx.event
        def bump_trigger(self):
            self.trigger += 1

    def index() -> rx.Component:
        return rx.vstack(
            rx.text(
                SharedState.n_changes,
                id="n-changes",
            ),
            rx.text(
                PrivateState.greeting,
                id="greeting",
            ),
            rx.form(
                rx.input(name="who", id="who-input"),
                rx.button("Set Who"),
                on_submit=SharedState.handle_submit,
                reset_on_submit=True,
            ),
            rx.text(PrivateState.linked_to, id="linked-to"),
            rx.text(SharedState.event_seen_linked_to, id="event-seen-linked-to"),
            rx.button("Unlink", id="unlink-button", on_click=SharedState.unlink),
            rx.form(
                rx.input(name="token", id="token-input"),
                rx.button("Link To Token"),
                on_submit=SharedState.handle_submit,
                reset_on_submit=True,
            ),
            rx.button(
                SharedState.counter,
                id="counter-button",
                on_click=SharedState.set_counter(SharedState.counter + 1),
                on_context_menu=SharedState.set_counter(
                    SharedState.counter - 1
                ).prevent_default,
            ),
            rx.button(
                "Bump Counter in Background",
                on_click=PrivateState.bump_counter_bg,
                id="bg-button",
            ),
            rx.button(
                "Bump Counter with Yield",
                on_click=PrivateState.bump_counter_yield,
                id="yield-button",
            ),
            rx.button(
                "Record Event Link Status",
                on_click=SharedState.record_event_link_status,
                id="record-link-status-button",
            ),
            rx.button(
                "Clear Event Link Status",
                on_click=SharedState.clear_event_link_status,
                id="clear-link-status-button",
            ),
            rx.button(
                "Reset Private State",
                on_click=PrivateState.reset_self,
                id="reset-private-state-button",
            ),
            rx.button(
                "Link to arbitrary token and Increment n_changes",
                on_click=SharedState.link_to_and_increment,
                id="link-increment-button",
            ),
            rx.text(SharedNotes.note, id="shared-note"),
            rx.button(
                "Fetch Note via get_state",
                on_click=PrivateState.fetch_shared_note,
                id="fetch-note-button",
            ),
            rx.text(PrivateState.fetched_note, id="fetched-note"),
            rx.text(RaceState.race_val_0, id="race-val-0"),
            rx.text(RaceState.race_val_1, id="race-val-1"),
            rx.text(RaceState.race_val_2, id="race-val-2"),
            rx.text(RaceState.race_val_3, id="race-val-3"),
            rx.button(
                "Bump Trigger",
                on_click=RaceState.bump_trigger,
                id="bump-trigger-button",
            ),
        )

    from fastapi import FastAPI

    api = FastAPI()

    @api.get("/api/set-counter/{shared_token}/{value}")
    async def set_counter_api(shared_token: str, value: int):
        """Modify shared state by its shared token from an API route."""
        from reflex.istate.manager.token import BaseStateToken

        async with app.modify_state(
            BaseStateToken(ident=shared_token, cls=SharedState),
        ) as state:
            ss = await state.get_state(SharedState)
            ss.counter = value
            notes = await state.get_state(SharedNotes)
            notes.note = f"counter set to {value}"

    app = rx.App(api_transformer=api)
    app.add_page(
        index,
        route="/room/[room]",
        on_load=[SharedState.on_load_link_default, SharedNotes.on_load_link_default],
    )
    app.add_page(index)


@pytest.fixture(scope="module")
def linked_state(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start LinkedStateApp at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance

    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("linked_state"),
        app_source=LinkedStateApp,
    ) as harness:
        yield harness


@pytest.fixture
def tab_factory(
    linked_state: AppHarness,
    page: Page,
) -> Generator[Callable[[], Page], None, None]:
    """Factory that opens new Playwright pages against the linked_state app.

    The first call returns the default function-scoped `page` fixture so that
    Playwright still manages its lifecycle; later calls open additional pages
    in the same browser context and will be closed on teardown.

    Args:
        linked_state: harness for LinkedStateApp
        page: The default Playwright page fixture.

    Yields:
        A zero-argument callable returning a Page navigated to the app.
    """
    assert linked_state.app_instance is not None, "app is not running"
    assert linked_state.frontend_url is not None
    frontend_url = linked_state.frontend_url

    pages: list[Page] = []
    extra_pages: list[Page] = []

    def factory() -> Page:
        if not pages:
            page.goto(frontend_url)
            pages.append(page)
            return page
        new_page = page.context.new_page()
        new_page.goto(frontend_url)
        pages.append(new_page)
        extra_pages.append(new_page)
        return new_page

    try:
        yield factory
    finally:
        for p in extra_pages:
            p.close()


def _wait_for_token(tab: Page) -> None:
    """Block until the session-storage token is present in the given tab."""
    ss = utils.SessionStorage(tab)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"


def test_linked_state(
    linked_state: AppHarness,
    tab_factory: Callable[[], Page],
):
    """Test that multiple tabs can link to and share state.

    Args:
        linked_state: harness for LinkedStateApp.
        tab_factory: factory to create Playwright pages.
    """
    assert linked_state.app_instance is not None

    tab1 = tab_factory()
    tab2 = tab_factory()
    _wait_for_token(tab1)
    n_changes_1 = tab1.locator("#n-changes")
    greeting_1 = tab1.locator("#greeting")
    _wait_for_token(tab2)
    n_changes_2 = tab2.locator("#n-changes")
    greeting_2 = tab2.locator("#greeting")

    # Initial state
    expect(n_changes_1).to_have_text("0")
    expect(greeting_1).to_have_text("Hello, world!")
    expect(n_changes_2).to_have_text("0")
    expect(greeting_2).to_have_text("Hello, world!")

    # Change state in tab 1
    tab1.locator("#who-input").fill("Alice")
    tab1.locator("#who-input").press("Enter")
    expect(n_changes_1).to_have_text("1")
    expect(greeting_1).to_have_text("Hello, Alice!")

    # Change state in tab 2
    tab2.locator("#who-input").fill("Bob")
    tab2.locator("#who-input").press("Enter")
    expect(n_changes_2).to_have_text("1")
    expect(greeting_2).to_have_text("Hello, Bob!")

    # Link both tabs to the same token, "shared-foo"
    shared_token = f"shared-foo-{uuid.uuid4()}"
    for tab in (tab1, tab2):
        tab.locator("#token-input").fill(shared_token)
        tab.locator("#token-input").press("Enter")
    expect(n_changes_1).to_have_text("0")
    expect(greeting_1).to_have_text("Hello, world!")
    expect(n_changes_2).to_have_text("0")
    expect(greeting_2).to_have_text("Hello, world!")

    # Set a new value in tab 1, should reflect in tab 2
    tab1.locator("#who-input").fill("Charlie")
    tab1.locator("#who-input").press("Enter")
    expect(n_changes_1).to_have_text("1")
    expect(greeting_1).to_have_text("Hello, Charlie!")
    expect(n_changes_2).to_have_text("1")
    expect(greeting_2).to_have_text("Hello, Charlie!")

    # Bump the counter in tab 2, should reflect in tab 1
    counter_button_1 = tab1.locator("#counter-button")
    counter_button_2 = tab2.locator("#counter-button")
    expect(counter_button_1).to_have_text("0")
    expect(counter_button_2).to_have_text("0")
    counter_button_2.click()
    expect(counter_button_1).to_have_text("1")
    expect(counter_button_2).to_have_text("1")
    counter_button_1.click()
    expect(counter_button_1).to_have_text("2")
    expect(counter_button_2).to_have_text("2")
    counter_button_2.click()
    expect(counter_button_1).to_have_text("3")
    expect(counter_button_2).to_have_text("3")

    # Unlink tab 2, should revert to previous private values
    tab2.locator("#unlink-button").click()
    expect(n_changes_2).to_have_text("1")
    expect(greeting_2).to_have_text("Hello, Bob!")
    expect(counter_button_2).to_have_text("0")

    # Relink tab 2, should go back to shared values
    tab2.locator("#token-input").fill(shared_token)
    tab2.locator("#token-input").press("Enter")
    expect(n_changes_2).to_have_text("1")
    expect(greeting_2).to_have_text("Hello, Charlie!")
    expect(counter_button_2).to_have_text("3")

    # Unlink tab 1, change the shared value in tab 2, and relink tab 1
    tab1.locator("#unlink-button").click()
    expect(n_changes_1).to_have_text("1")
    expect(greeting_1).to_have_text("Hello, Alice!")
    tab2.locator("#who-input").fill("Diana")
    tab2.locator("#who-input").press("Enter")
    expect(n_changes_2).to_have_text("2")
    expect(greeting_2).to_have_text("Hello, Diana!")
    expect(counter_button_2).to_have_text("3")
    expect(n_changes_1).to_have_text("1")
    expect(greeting_1).to_have_text("Hello, Alice!")
    tab1.locator("#token-input").fill(shared_token)
    tab1.locator("#token-input").press("Enter")
    expect(n_changes_1).to_have_text("2")
    expect(greeting_1).to_have_text("Hello, Diana!")
    expect(counter_button_1).to_have_text("3")

    # Open a third tab linked to the shared token on_load
    tab3 = tab_factory()
    tab3.goto(f"{linked_state.frontend_url}room/{shared_token}")  # pyright: ignore[reportOptionalMemberAccess]
    _wait_for_token(tab3)
    n_changes_3 = tab3.locator("#n-changes")
    greeting_3 = tab3.locator("#greeting")
    counter_button_3 = tab3.locator("#counter-button")
    expect(n_changes_3).to_have_text("2")
    expect(greeting_3).to_have_text("Hello, Diana!")
    expect(counter_button_3).to_have_text("3")
    expect(tab3.locator("#linked-to")).to_have_text(shared_token)

    # Trigger a background task in all shared states, assert on final value
    tab1.locator("#bg-button").click()
    tab2.locator("#bg-button").click()
    tab3.locator("#bg-button").click()
    expect(counter_button_1).to_have_text("33")
    expect(counter_button_2).to_have_text("33")
    expect(counter_button_3).to_have_text("33")

    # Trigger a yield-based task in all shared states, assert on final value
    tab1.locator("#yield-button").click()
    tab2.locator("#yield-button").click()
    tab3.locator("#yield-button").click()
    expect(counter_button_1).to_have_text("48")
    expect(counter_button_2).to_have_text("48")
    expect(counter_button_3).to_have_text("48")

    # Link to a new token when we're already linked
    new_shared_token = f"shared-bar-{uuid.uuid4()}"
    tab1.locator("#token-input").fill(new_shared_token)
    tab1.locator("#token-input").press("Enter")
    expect(n_changes_1).to_have_text("0")
    expect(greeting_1).to_have_text("Hello, world!")
    expect(counter_button_1).to_have_text("0")
    counter_button_1.click()
    expect(counter_button_1).to_have_text("1")
    counter_button_1.click()
    expect(counter_button_1).to_have_text("2")
    counter_button_1.click()
    expect(counter_button_1).to_have_text("3")
    # Ensure other tabs are unaffected
    expect(n_changes_2).to_have_text("2")
    expect(greeting_2).to_have_text("Hello, Diana!")
    expect(counter_button_2).to_have_text("48")
    expect(n_changes_3).to_have_text("2")
    expect(greeting_3).to_have_text("Hello, Diana!")
    expect(counter_button_3).to_have_text("48")

    # Link to a new state and increment the counter in the same event
    tab1.locator("#link-increment-button").click()
    expect(counter_button_1).to_have_text("1")


def _open_linked_tab(
    harness: AppHarness,
    tab_factory: Callable[[], Page],
    shared_token: str,
) -> tuple[Locator, Locator]:
    """Open a new tab linked to a shared token and return key locators.

    Args:
        harness: The running AppHarness.
        tab_factory: Factory to create Playwright pages.
        shared_token: The shared token to link to via on_load.

    Returns:
        Tuple of (counter_button, note_element).
    """
    tab = tab_factory()
    tab.goto(f"{harness.frontend_url}room/{shared_token}")  # pyright: ignore[reportOptionalMemberAccess]
    _wait_for_token(tab)
    counter_button = tab.locator("#counter-button")
    expect(counter_button).to_have_text("0")
    # Wait for SharedState.on_load_link_default to complete (linked-to shows the token).
    expect(tab.locator("#linked-to")).to_have_text(shared_token)
    note = tab.locator("#shared-note")
    expect(note).to_have_text("")
    return counter_button, note


def test_modify_shared_state_by_shared_token(
    linked_state: AppHarness,
    tab_factory: Callable[[], Page],
):
    """Test that modifying shared state by shared token propagates to all linked clients.

    This exercises the use case of modifying shared state from an API route
    where only the shared token is known (no private client token).

    Args:
        linked_state: harness for LinkedStateApp.
        tab_factory: factory to create Playwright pages.
    """
    assert linked_state.app_instance is not None

    shared_token = f"api-test-{uuid.uuid4()}"

    # Open two tabs linked to the same shared token via on_load
    counter_button_1, note_1 = _open_linked_tab(linked_state, tab_factory, shared_token)
    counter_button_2, note_2 = _open_linked_tab(linked_state, tab_factory, shared_token)

    # Modify both shared states by shared token via API route
    api_url = f"{get_config().api_url}/api/set-counter/{shared_token}/42"
    response = httpx.get(api_url)
    assert response.status_code == 200

    # Both tabs should see updates to both SharedState and SharedNotes
    expect(counter_button_1).to_have_text("42")
    expect(counter_button_2).to_have_text("42")
    expect(note_1).to_have_text("counter set to 42")
    expect(note_2).to_have_text("counter set to 42")

    # After the API-driven update, normal event handlers should still work
    counter_button_1.click()
    expect(counter_button_1).to_have_text("43")
    expect(counter_button_2).to_have_text("43")


def test_get_state_returns_linked_state(
    linked_state: AppHarness,
    tab_factory: Callable[[], Page],
):
    """Test that get_state from an unrelated handler returns the linked instance.

    When SharedNotes is linked to a shared token, calling
    ``await self.get_state(SharedNotes)`` from PrivateState (an unrelated
    state handler) should return the linked SharedNotes — not the private
    copy.  With the Redis state manager, SharedNotes may not be pre-loaded
    in the tree, so ``get_state`` falls through to the redis fetch path.

    Args:
        linked_state: harness for LinkedStateApp.
        tab_factory: factory to create Playwright pages.
    """
    assert linked_state.app_instance is not None

    shared_token = f"get-state-test-{uuid.uuid4()}"
    initial_note = f"note-{uuid.uuid4()}"

    # Open a tab linked to the shared token via on_load, setting the note
    # immediately during linking via query param.
    tab = tab_factory()
    tab.goto(
        f"{linked_state.frontend_url}room/{shared_token}?initial_note={initial_note}"  # pyright: ignore[reportOptionalMemberAccess]
    )
    _wait_for_token(tab)
    linked_to = tab.locator("#linked-to")
    # Wait for on_load to link SharedState (confirms event processing started).
    expect(linked_to).to_have_text(shared_token)

    # Verify the linked note appears on the page (direct SharedNotes binding).
    note = tab.locator("#shared-note")
    expect(note).to_have_text(initial_note)

    # Now trigger PrivateState.fetch_shared_note — this calls get_state(SharedNotes)
    # from an unrelated state handler.  The returned instance must be the
    # *linked* SharedNotes (with the note set from the query param), not
    # the private copy (which would have an empty note).
    tab.locator("#fetch-note-button").click()
    fetched = tab.locator("#fetched-note")
    expect(fetched).to_have_text(initial_note)


def test_unrelated_reset_does_not_break_shared_event_link_context(
    linked_state: AppHarness,
    tab_factory: Callable[[], Page],
):
    """Ensure private-state reset does not break SharedState event linkage context.

    Repro sequence from reported issue:
    1. Link SharedState to a shared token.
    2. Confirm a SharedState event sees linked token in ``self._linked_to``.
    3. Call ``self.reset()`` on an unrelated non-shared state.
    4. Confirm subsequent SharedState events still see linked token.

    Args:
        linked_state: harness for LinkedStateApp.
        tab_factory: factory to create Playwright pages.
    """
    assert linked_state.app_instance is not None

    tab = tab_factory()
    _wait_for_token(tab)

    shared_token = f"reset-repro-{uuid.uuid4()}"
    tab.locator("#token-input").fill(shared_token)
    tab.locator("#token-input").press("Enter")

    expect(tab.locator("#linked-to")).to_have_text(shared_token)

    event_seen = tab.locator("#event-seen-linked-to")
    tab.locator("#record-link-status-button").click()
    expect(event_seen).to_have_text(shared_token)

    # Clear the field first so we can distinguish a fresh record from the stale value,
    # then trigger reset + record and wait for the DOM to reflect the new result.
    tab.locator("#clear-link-status-button").click()
    expect(event_seen).to_have_text("")
    tab.locator("#reset-private-state-button").click()
    tab.locator("#record-link-status-button").click()
    expect(event_seen).to_have_text(shared_token)


def test_concurrent_async_vars_do_not_deadlock_linked_token(
    linked_state: AppHarness,
    tab_factory: Callable[[], Page],
):
    """Ensure concurrent async vars accessing a linked SharedState do not deadlock.

    When multiple async rx.var functions simultaneously call ``await
    self.get_state(SharedState)`` and SharedState is not yet cached, each
    resolves the linked state independently, meaning multiple concurrent calls
    to ``state_manager.modify_state`` for the same linked token.  Without a lock
    protecting this operation these races hit the Redis lock timeout
    (~lock_expiration delay per blocked var).

    Only meaningful with the Redis state manager; skipped otherwise.

    Args:
        linked_state: harness for LinkedStateApp.
        tab_factory: factory to create Playwright pages.
    """
    import time

    from reflex.istate.manager.redis import StateManagerRedis

    assert linked_state.app_instance is not None
    sm = linked_state.app_instance.state_manager
    if not isinstance(sm, StateManagerRedis):
        pytest.skip("Only applicable with Redis state manager")

    lock_expiration_s = sm.lock_expiration / 1000
    # All 4 vars must update well within the lock expiration window.
    # If any var hits a lock timeout it will delay by ~lock_expiration_s,
    # which would exceed this threshold and fail the assertion.
    max_acceptable_s = lock_expiration_s / 2

    tab = tab_factory()
    _wait_for_token(tab)

    shared_token = f"race-repro-{uuid.uuid4()}"
    tab.locator("#token-input").fill(shared_token)
    tab.locator("#token-input").press("Enter")
    expect(tab.locator("#linked-to")).to_have_text(shared_token)

    race_elements = [tab.locator(f"#race-val-{i}") for i in range(4)]

    # Wait for all 4 vars to settle to their initial value after linking.
    initial_texts = []
    for el in race_elements:
        expect(el).not_to_have_text("")
        initial_texts.append(el.text_content() or "")

    # Trigger the race: bump_trigger causes all 4 async vars to recompute
    # concurrently, each independently calling get_state(SharedState) which
    # resolves via modify_state on the linked token.
    tab.locator("#bump-trigger-button").click()

    t0 = time.monotonic()
    for el, initial in zip(race_elements, initial_texts, strict=True):
        expect(el).not_to_have_text(initial)
    elapsed = time.monotonic() - t0

    assert elapsed < max_acceptable_s, (
        f"Async vars took {elapsed:.2f}s to update — expected < {max_acceptable_s:.2f}s "
        f"(lock_expiration={lock_expiration_s:.2f}s). "
        "Likely caused by concurrent async vars racing for the linked token lock."
    )
