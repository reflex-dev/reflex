"""Test linked state."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Generator

import httpx
import pytest
from reflex_base.config import get_config
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement

from reflex.testing import AppHarness, WebDriver

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


@pytest.fixture
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
) -> Generator[Callable[[], WebDriver], None, None]:
    """Get an instance of the browser open to the linked_state app.

    Args:
        linked_state: harness for LinkedStateApp

    Yields:
        WebDriver instance.

    """
    assert linked_state.app_instance is not None, "app is not running"

    drivers = []

    def driver() -> WebDriver:
        d = linked_state.frontend()
        drivers.append(d)
        return d

    try:
        yield driver
    finally:
        for d in drivers:
            d.quit()


def test_linked_state(
    linked_state: AppHarness,
    tab_factory: Callable[[], WebDriver],
):
    """Test that multiple tabs can link to and share state.

    Args:
        linked_state: harness for LinkedStateApp.
        tab_factory: factory to create WebDriver instances.

    """
    assert linked_state.app_instance is not None

    tab1 = tab_factory()
    tab2 = tab_factory()
    ss = utils.SessionStorage(tab1)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"
    n_changes_1 = tab1.find_element(By.ID, "n-changes")
    greeting_1 = tab1.find_element(By.ID, "greeting")
    ss = utils.SessionStorage(tab2)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"
    n_changes_2 = tab2.find_element(By.ID, "n-changes")
    greeting_2 = tab2.find_element(By.ID, "greeting")

    # Initial state
    assert n_changes_1.text == "0"
    assert greeting_1.text == "Hello, world!"
    assert n_changes_2.text == "0"
    assert greeting_2.text == "Hello, world!"

    # Change state in tab 1
    tab1.find_element(By.ID, "who-input").send_keys("Alice", Keys.ENTER)
    assert linked_state.poll_for_content(n_changes_1, exp_not_equal="0") == "1"
    assert (
        linked_state.poll_for_content(greeting_1, exp_not_equal="Hello, world!")
        == "Hello, Alice!"
    )

    # Change state in tab 2
    tab2.find_element(By.ID, "who-input").send_keys("Bob", Keys.ENTER)
    assert linked_state.poll_for_content(n_changes_2, exp_not_equal="0") == "1"
    assert (
        linked_state.poll_for_content(greeting_2, exp_not_equal="Hello, world!")
        == "Hello, Bob!"
    )

    # Link both tabs to the same token, "shared-foo"
    shared_token = f"shared-foo-{uuid.uuid4()}"
    for tab in (tab1, tab2):
        tab.find_element(By.ID, "token-input").send_keys(shared_token, Keys.ENTER)
    assert linked_state.poll_for_content(n_changes_1, exp_not_equal="1") == "0"
    assert (
        linked_state.poll_for_content(greeting_1, exp_not_equal="Hello, Alice!")
        == "Hello, world!"
    )
    assert linked_state.poll_for_content(n_changes_2, exp_not_equal="1") == "0"
    assert (
        linked_state.poll_for_content(greeting_2, exp_not_equal="Hello, Bob!")
        == "Hello, world!"
    )

    # Set a new value in tab 1, should reflect in tab 2
    tab1.find_element(By.ID, "who-input").send_keys("Charlie", Keys.ENTER)
    assert linked_state.poll_for_content(n_changes_1, exp_not_equal="0") == "1"
    assert (
        linked_state.poll_for_content(greeting_1, exp_not_equal="Hello, world!")
        == "Hello, Charlie!"
    )
    assert linked_state.poll_for_content(n_changes_2, exp_not_equal="0") == "1"
    assert (
        linked_state.poll_for_content(greeting_2, exp_not_equal="Hello, world!")
        == "Hello, Charlie!"
    )

    # Bump the counter in tab 2, should reflect in tab 1
    counter_button_1 = tab1.find_element(By.ID, "counter-button")
    counter_button_2 = tab2.find_element(By.ID, "counter-button")
    assert counter_button_1.text == "0"
    assert counter_button_2.text == "0"
    counter_button_2.click()
    assert linked_state.poll_for_content(counter_button_1, exp_not_equal="0") == "1"
    assert linked_state.poll_for_content(counter_button_2, exp_not_equal="0") == "1"
    counter_button_1.click()
    assert linked_state.poll_for_content(counter_button_1, exp_not_equal="1") == "2"
    assert linked_state.poll_for_content(counter_button_2, exp_not_equal="1") == "2"
    counter_button_2.click()
    assert linked_state.poll_for_content(counter_button_1, exp_not_equal="2") == "3"
    assert linked_state.poll_for_content(counter_button_2, exp_not_equal="2") == "3"

    # Unlink tab 2, should revert to previous private values
    tab2.find_element(By.ID, "unlink-button").click()
    assert n_changes_2.text == "1"
    assert (
        linked_state.poll_for_content(greeting_2, exp_not_equal="Hello, Charlie!")
        == "Hello, Bob!"
    )
    assert linked_state.poll_for_content(counter_button_2, exp_not_equal="3") == "0"

    # Relink tab 2, should go back to shared values
    tab2.find_element(By.ID, "token-input").send_keys(shared_token, Keys.ENTER)
    assert n_changes_2.text == "1"
    assert (
        linked_state.poll_for_content(greeting_2, exp_not_equal="Hello, Bob!")
        == "Hello, Charlie!"
    )
    assert linked_state.poll_for_content(counter_button_2, exp_not_equal="0") == "3"

    # Unlink tab 1, change the shared value in tab 2, and relink tab 1
    tab1.find_element(By.ID, "unlink-button").click()
    assert n_changes_1.text == "1"
    assert (
        linked_state.poll_for_content(greeting_1, exp_not_equal="Hello, Charlie!")
        == "Hello, Alice!"
    )
    tab2.find_element(By.ID, "who-input").send_keys("Diana", Keys.ENTER)
    assert linked_state.poll_for_content(n_changes_2, exp_not_equal="1") == "2"
    assert (
        linked_state.poll_for_content(greeting_2, exp_not_equal="Hello, Charlie!")
        == "Hello, Diana!"
    )
    assert counter_button_2.text == "3"
    assert n_changes_1.text == "1"
    assert greeting_1.text == "Hello, Alice!"
    tab1.find_element(By.ID, "token-input").send_keys(shared_token, Keys.ENTER)
    assert linked_state.poll_for_content(n_changes_1, exp_not_equal="1") == "2"
    assert (
        linked_state.poll_for_content(greeting_1, exp_not_equal="Hello, Alice!")
        == "Hello, Diana!"
    )
    assert linked_state.poll_for_content(counter_button_1, exp_not_equal="0") == "3"

    # Open a third tab linked to the shared token on_load
    tab3 = tab_factory()
    tab3.get(f"{linked_state.frontend_url}room/{shared_token}")
    ss = utils.SessionStorage(tab3)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"
    n_changes_3 = AppHarness._poll_for(lambda: tab3.find_element(By.ID, "n-changes"))
    assert n_changes_3
    greeting_3 = tab3.find_element(By.ID, "greeting")
    counter_button_3 = tab3.find_element(By.ID, "counter-button")
    assert linked_state.poll_for_content(n_changes_3, exp_not_equal="0") == "2"
    assert (
        linked_state.poll_for_content(greeting_3, exp_not_equal="Hello, world!")
        == "Hello, Diana!"
    )
    assert linked_state.poll_for_content(counter_button_3, exp_not_equal="0") == "3"
    assert tab3.find_element(By.ID, "linked-to").text == shared_token

    # Trigger a background task in all shared states, assert on final value
    tab1.find_element(By.ID, "bg-button").click()
    tab2.find_element(By.ID, "bg-button").click()
    tab3.find_element(By.ID, "bg-button").click()
    assert AppHarness._poll_for(lambda: counter_button_1.text == "33")
    assert AppHarness._poll_for(lambda: counter_button_2.text == "33")
    assert AppHarness._poll_for(lambda: counter_button_3.text == "33")

    # Trigger a yield-based task in all shared states, assert on final value
    tab1.find_element(By.ID, "yield-button").click()
    tab2.find_element(By.ID, "yield-button").click()
    tab3.find_element(By.ID, "yield-button").click()
    assert AppHarness._poll_for(lambda: counter_button_1.text == "48")
    assert AppHarness._poll_for(lambda: counter_button_2.text == "48")
    assert AppHarness._poll_for(lambda: counter_button_3.text == "48")

    # Link to a new token when we're already linked
    new_shared_token = f"shared-bar-{uuid.uuid4()}"
    tab1.find_element(By.ID, "token-input").send_keys(new_shared_token, Keys.ENTER)
    assert linked_state.poll_for_content(n_changes_1, exp_not_equal="2") == "0"
    assert (
        linked_state.poll_for_content(greeting_1, exp_not_equal="Hello, Diana!")
        == "Hello, world!"
    )
    assert linked_state.poll_for_content(counter_button_1, exp_not_equal="48") == "0"
    counter_button_1.click()
    assert linked_state.poll_for_content(counter_button_1, exp_not_equal="0") == "1"
    counter_button_1.click()
    assert linked_state.poll_for_content(counter_button_1, exp_not_equal="1") == "2"
    counter_button_1.click()
    assert linked_state.poll_for_content(counter_button_1, exp_not_equal="2") == "3"
    # Ensure other tabs are unaffected
    assert n_changes_2.text == "2"
    assert greeting_2.text == "Hello, Diana!"
    assert counter_button_2.text == "48"
    assert n_changes_3.text == "2"
    assert greeting_3.text == "Hello, Diana!"
    assert counter_button_3.text == "48"

    # Link to a new state and increment the counter in the same event
    tab1.find_element(By.ID, "link-increment-button").click()
    assert linked_state.poll_for_content(counter_button_1, exp_not_equal="3") == "1"


def _open_linked_tab(
    harness: AppHarness,
    tab_factory: Callable[[], WebDriver],
    shared_token: str,
) -> tuple[WebElement, WebElement]:
    """Open a new tab linked to a shared token and return key elements.

    Args:
        harness: The running AppHarness.
        tab_factory: Factory to create WebDriver instances.
        shared_token: The shared token to link to via on_load.

    Returns:
        Tuple of (counter_button, note_element).
    """
    tab = tab_factory()
    tab.get(f"{harness.frontend_url}room/{shared_token}")
    ss = utils.SessionStorage(tab)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"
    counter_button = AppHarness._poll_for(
        lambda: tab.find_element(By.ID, "counter-button")
    )
    assert counter_button
    assert harness.poll_for_content(counter_button) == "0"
    # Wait for SharedState.on_load_link_default to complete (linked-to shows the token).
    linked_to = tab.find_element(By.ID, "linked-to")
    assert harness.poll_for_content(linked_to) == shared_token
    note = tab.find_element(By.ID, "shared-note")
    assert note.text == ""
    return counter_button, note


def test_modify_shared_state_by_shared_token(
    linked_state: AppHarness,
    tab_factory: Callable[[], WebDriver],
):
    """Test that modifying shared state by shared token propagates to all linked clients.

    This exercises the use case of modifying shared state from an API route
    where only the shared token is known (no private client token).

    Args:
        linked_state: harness for LinkedStateApp.
        tab_factory: factory to create WebDriver instances.
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
    assert linked_state.poll_for_content(counter_button_1, exp_not_equal="0") == "42"
    assert linked_state.poll_for_content(counter_button_2, exp_not_equal="0") == "42"
    assert (
        linked_state.poll_for_content(note_1, exp_not_equal="") == "counter set to 42"
    )
    assert (
        linked_state.poll_for_content(note_2, exp_not_equal="") == "counter set to 42"
    )

    # After the API-driven update, normal event handlers should still work
    counter_button_1.click()
    assert linked_state.poll_for_content(counter_button_1, exp_not_equal="42") == "43"
    assert linked_state.poll_for_content(counter_button_2, exp_not_equal="42") == "43"


def test_get_state_returns_linked_state(
    linked_state: AppHarness,
    tab_factory: Callable[[], WebDriver],
):
    """Test that get_state from an unrelated handler returns the linked instance.

    When SharedNotes is linked to a shared token, calling
    ``await self.get_state(SharedNotes)`` from PrivateState (an unrelated
    state handler) should return the linked SharedNotes — not the private
    copy.  With the Redis state manager, SharedNotes may not be pre-loaded
    in the tree, so ``get_state`` falls through to the redis fetch path.

    Args:
        linked_state: harness for LinkedStateApp.
        tab_factory: factory to create WebDriver instances.
    """
    assert linked_state.app_instance is not None

    shared_token = f"get-state-test-{uuid.uuid4()}"
    initial_note = f"note-{uuid.uuid4()}"

    # Open a tab linked to the shared token via on_load, setting the note
    # immediately during linking via query param.
    tab = tab_factory()
    tab.get(
        f"{linked_state.frontend_url}room/{shared_token}?initial_note={initial_note}"
    )
    ss = utils.SessionStorage(tab)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"
    linked_to = AppHarness._poll_for(lambda: tab.find_element(By.ID, "linked-to"))
    assert linked_to
    # Wait for on_load to link SharedState (confirms event processing started).
    assert linked_state.poll_for_content(linked_to) == shared_token

    # Verify the linked note appears on the page (direct SharedNotes binding).
    note = tab.find_element(By.ID, "shared-note")
    assert linked_state.poll_for_content(note, exp_not_equal="") == initial_note

    # Now trigger PrivateState.fetch_shared_note — this calls get_state(SharedNotes)
    # from an unrelated state handler.  The returned instance must be the
    # *linked* SharedNotes (with the note set from the query param), not
    # the private copy (which would have an empty note).
    tab.find_element(By.ID, "fetch-note-button").click()
    fetched = tab.find_element(By.ID, "fetched-note")
    assert linked_state.poll_for_content(fetched, exp_not_equal="") == initial_note
