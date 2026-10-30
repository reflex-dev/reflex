"""Playwright coverage for linked shared state across browser pages."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Generator

import httpx
import pytest
from playwright.sync_api import Browser, Page, expect
from reflex_base.config import get_config

from reflex.testing import AppHarness


def LinkedStateApp():
    """Create shared-state scenarios used by the linked-state tests."""
    import reflex as rx

    class SharedState(rx.SharedState):
        _who: str = "world"
        n_changes: int = 0
        counter: int = 0
        event_seen_linked_to: str = ""

        @rx.event
        def set_counter(self, value: int):
            self.counter = value

        @rx.event
        def set_who(self, who: str):
            self._who = who
            self.n_changes += 1

        @rx.event
        async def link_to(self, token: str):
            await self._link_to(token)

        @rx.event
        async def link_to_and_increment(self):
            import uuid

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
            linked_state = await self._link_to(
                self.room or "default"  # pyright: ignore[reportAttributeAccessIssue]
            )
            assert linked_state._linked_to == (
                self.room or "default"  # pyright: ignore[reportAttributeAccessIssue]
            )

        @rx.event
        async def handle_submit(self, form_data: dict[str, str]):
            if "who" in form_data:
                self.set_who(form_data["who"])
            if "token" in form_data:
                await self.link_to(form_data["token"])

    class SharedNotes(rx.SharedState):
        note: str = ""

        @rx.event
        async def on_load_link_default(self):
            linked_state = await self._link_to(
                self.room or "default"  # pyright: ignore[reportAttributeAccessIssue]
            )
            initial_note = self.router.page.params.get("initial_note", "")
            if initial_note:
                linked_state.note = initial_note

    class PrivateState(rx.State):
        fetched_note: str = ""

        @rx.var
        async def greeting(self) -> str:
            shared = await self.get_state(SharedState)
            return f"Hello, {shared._who}!"

        @rx.var
        async def linked_to(self) -> str:
            shared = await self.get_state(SharedState)
            return shared._linked_to

        @rx.event
        async def fetch_shared_note(self):
            notes = await self.get_state(SharedNotes)
            self.fetched_note = notes.note

        @rx.event(background=True)
        async def bump_counter_bg(self):
            for _ in range(5):
                async with self:
                    shared = await self.get_state(SharedState)
                    shared.counter += 1
            async with self:
                shared = await self.get_state(SharedState)
            for _ in range(5):
                async with shared:
                    shared.counter += 1

        @rx.event
        async def bump_counter_yield(self):
            shared = await self.get_state(SharedState)
            for _ in range(5):
                shared.counter += 1
                yield

        @rx.event
        def reset_self(self):
            self.reset()

    class RaceState(rx.State):
        trigger: int = 0

        @rx.var
        async def race_val_0(self) -> str:
            return f"{self.trigger}-{(await self.get_state(SharedState)).counter}"

        @rx.var
        async def race_val_1(self) -> str:
            return f"{self.trigger}-{(await self.get_state(SharedState)).counter}"

        @rx.var
        async def race_val_2(self) -> str:
            return f"{self.trigger}-{(await self.get_state(SharedState)).counter}"

        @rx.var
        async def race_val_3(self) -> str:
            return f"{self.trigger}-{(await self.get_state(SharedState)).counter}"

        @rx.event
        def bump_trigger(self):
            self.trigger += 1

    def index():
        return rx.vstack(
            rx.text(SharedState.n_changes, id="n-changes"),
            rx.text(PrivateState.greeting, id="greeting"),
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
                "Link and increment",
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
            *(
                rx.text(getattr(RaceState, f"race_val_{i}"), id=f"race-val-{i}")
                for i in range(4)
            ),
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
        from reflex.istate.manager.token import BaseStateToken

        async with app.modify_state(
            BaseStateToken(ident=shared_token, cls=SharedState)
        ) as state:
            shared = await state.get_state(SharedState)
            shared.counter = value
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
def linked_state(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start the shared-state app.

    Yields:
        The running app harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("linked_state"), app_source=LinkedStateApp
    ) as harness:
        yield harness


@pytest.fixture
def tab_factory(
    linked_state: AppHarness, browser: Browser
) -> Generator[Callable[[], Page], None, None]:
    """Create pages that have isolated session storage but shared local storage.

    Yields:
        A page factory for the shared-state app.
    """
    assert linked_state.frontend_url is not None
    frontend_url = linked_state.frontend_url
    context = browser.new_context()

    def new_page() -> Page:
        page = context.new_page()
        page.goto(frontend_url)
        return page

    try:
        yield new_page
    finally:
        context.close()


def _linked_page(
    harness: AppHarness, tab_factory: Callable[[], Page], url: str
) -> Page:
    page = tab_factory()
    assert harness.frontend_url is not None
    page.goto(f"{harness.frontend_url}{url}")
    page.wait_for_function("Boolean(sessionStorage.getItem('token'))")
    return page


def _submit(page: Page, selector: str, value: str) -> None:
    field = page.locator(selector)
    field.fill(value)
    field.press("Enter")


def test_linked_state(linked_state: AppHarness, tab_factory: Callable[[], Page]):
    """Link two tabs, update shared state, then unlink and relink them."""
    tab1, tab2 = tab_factory(), tab_factory()
    for page in (tab1, tab2):
        page.wait_for_function("Boolean(sessionStorage.getItem('token'))")
        expect(page.locator("#n-changes")).to_have_text("0")
        expect(page.locator("#greeting")).to_have_text("Hello, world!")

    _submit(tab1, "#who-input", "Alice")
    expect(tab1.locator("#n-changes")).to_have_text("1")
    expect(tab1.locator("#greeting")).to_have_text("Hello, Alice!")
    _submit(tab2, "#who-input", "Bob")
    expect(tab2.locator("#n-changes")).to_have_text("1")
    expect(tab2.locator("#greeting")).to_have_text("Hello, Bob!")

    shared_token = f"shared-foo-{uuid.uuid4()}"
    for page in (tab1, tab2):
        _submit(page, "#token-input", shared_token)
        expect(page.locator("#linked-to")).to_have_text(shared_token)
        expect(page.locator("#n-changes")).to_have_text("0")
        expect(page.locator("#greeting")).to_have_text("Hello, world!")

    _submit(tab1, "#who-input", "Charlie")
    for page in (tab1, tab2):
        expect(page.locator("#n-changes")).to_have_text("1")
        expect(page.locator("#greeting")).to_have_text("Hello, Charlie!")

    counter1, counter2 = (
        tab1.locator("#counter-button"),
        tab2.locator("#counter-button"),
    )
    for expected in ("0", "1", "2", "3"):
        expect(counter1).to_have_text(expected)
        expect(counter2).to_have_text(expected)
        if expected != "3":
            (tab2 if expected in {"0", "2"} else tab1).locator(
                "#counter-button"
            ).click()
            next_value = str(int(expected) + 1)
            expect(counter1).to_have_text(next_value)
            expect(counter2).to_have_text(next_value)

    tab2.locator("#unlink-button").click()
    expect(tab2.locator("#greeting")).to_have_text("Hello, Bob!")
    expect(counter2).to_have_text("0")
    _submit(tab2, "#token-input", shared_token)
    expect(tab2.locator("#greeting")).to_have_text("Hello, Charlie!")
    expect(counter2).to_have_text("3")

    tab1.locator("#unlink-button").click()
    expect(tab1.locator("#greeting")).to_have_text("Hello, Alice!")
    _submit(tab2, "#who-input", "Diana")
    expect(tab2.locator("#greeting")).to_have_text("Hello, Diana!")
    expect(tab1.locator("#greeting")).to_have_text("Hello, Alice!")
    _submit(tab1, "#token-input", shared_token)
    expect(tab1.locator("#greeting")).to_have_text("Hello, Diana!")
    expect(counter1).to_have_text("3")

    assert linked_state.frontend_url is not None
    tab3 = _linked_page(linked_state, tab_factory, f"room/{shared_token}")
    expect(tab3.locator("#n-changes")).to_have_text("2")
    expect(tab3.locator("#greeting")).to_have_text("Hello, Diana!")
    expect(tab3.locator("#counter-button")).to_have_text("3")
    expect(tab3.locator("#linked-to")).to_have_text(shared_token)

    for page in (tab1, tab2, tab3):
        page.locator("#bg-button").click()
    for page in (tab1, tab2, tab3):
        expect(page.locator("#counter-button")).to_have_text("33", timeout=30_000)
    for page in (tab1, tab2, tab3):
        page.locator("#yield-button").click()
    for page in (tab1, tab2, tab3):
        expect(page.locator("#counter-button")).to_have_text("48", timeout=30_000)

    new_token = f"shared-bar-{uuid.uuid4()}"
    _submit(tab1, "#token-input", new_token)
    expect(tab1.locator("#n-changes")).to_have_text("0")
    expect(tab1.locator("#greeting")).to_have_text("Hello, world!")
    for expected in ("0", "1", "2", "3"):
        expect(counter1).to_have_text(expected)
        if expected != "3":
            counter1.click()
    expect(tab2.locator("#greeting")).to_have_text("Hello, Diana!")
    expect(tab2.locator("#counter-button")).to_have_text("48")
    expect(tab3.locator("#greeting")).to_have_text("Hello, Diana!")
    expect(tab3.locator("#counter-button")).to_have_text("48")
    tab1.locator("#link-increment-button").click()
    expect(counter1).to_have_text("1")


def _open_linked_page(
    harness: AppHarness, tab_factory: Callable[[], Page], token: str
) -> Page:
    page = _linked_page(harness, tab_factory, f"room/{token}")
    expect(page.locator("#counter-button")).to_have_text("0")
    expect(page.locator("#linked-to")).to_have_text(token)
    expect(page.locator("#shared-note")).to_have_text("")
    return page


def test_modify_shared_state_by_shared_token(
    linked_state: AppHarness, tab_factory: Callable[[], Page]
):
    """An API update by shared token reaches all linked pages."""
    shared_token = f"api-test-{uuid.uuid4()}"
    page1 = _open_linked_page(linked_state, tab_factory, shared_token)
    page2 = _open_linked_page(linked_state, tab_factory, shared_token)
    response = httpx.get(f"{get_config().api_url}/api/set-counter/{shared_token}/42")
    assert response.status_code == 200
    for page in (page1, page2):
        expect(page.locator("#counter-button")).to_have_text("42")
        expect(page.locator("#shared-note")).to_have_text("counter set to 42")
    page1.locator("#counter-button").click()
    expect(page1.locator("#counter-button")).to_have_text("43")
    expect(page2.locator("#counter-button")).to_have_text("43")


def test_get_state_returns_linked_state(
    linked_state: AppHarness, tab_factory: Callable[[], Page]
):
    """get_state from a private handler reads the linked SharedNotes instance."""
    shared_token = f"get-state-test-{uuid.uuid4()}"
    initial_note = f"note-{uuid.uuid4()}"
    page = _linked_page(
        linked_state, tab_factory, f"room/{shared_token}?initial_note={initial_note}"
    )
    expect(page.locator("#linked-to")).to_have_text(shared_token)
    expect(page.locator("#shared-note")).to_have_text(initial_note)
    page.locator("#fetch-note-button").click()
    expect(page.locator("#fetched-note")).to_have_text(initial_note)


def test_unrelated_reset_does_not_break_shared_event_link_context(
    linked_state: AppHarness, tab_factory: Callable[[], Page]
):
    """Resetting private state leaves subsequent shared events linked."""
    page = tab_factory()
    page.wait_for_function("Boolean(sessionStorage.getItem('token'))")
    shared_token = f"reset-repro-{uuid.uuid4()}"
    _submit(page, "#token-input", shared_token)
    expect(page.locator("#linked-to")).to_have_text(shared_token)
    page.locator("#record-link-status-button").click()
    expect(page.locator("#event-seen-linked-to")).to_have_text(shared_token)
    page.locator("#clear-link-status-button").click()
    expect(page.locator("#event-seen-linked-to")).to_have_text("")
    page.locator("#reset-private-state-button").click()
    page.locator("#record-link-status-button").click()
    expect(page.locator("#event-seen-linked-to")).to_have_text(shared_token)


def test_concurrent_async_vars_do_not_deadlock_linked_token(
    linked_state: AppHarness, tab_factory: Callable[[], Page]
):
    """Concurrent async vars resolve one linked token without lock contention."""
    from reflex.istate.manager.redis import StateManagerRedis

    assert linked_state.app_instance is not None
    manager = linked_state.app_instance.state_manager
    if not isinstance(manager, StateManagerRedis):
        pytest.skip("Only applicable with Redis state manager")
    max_acceptable_s = manager.lock_expiration / 2000
    page = tab_factory()
    page.wait_for_function("Boolean(sessionStorage.getItem('token'))")
    shared_token = f"race-repro-{uuid.uuid4()}"
    _submit(page, "#token-input", shared_token)
    expect(page.locator("#linked-to")).to_have_text(shared_token)
    race_values = [page.locator(f"#race-val-{index}") for index in range(4)]
    initial = []
    for value in race_values:
        expect(value).not_to_have_text("")
        initial.append(value.inner_text())
    page.locator("#bump-trigger-button").click()
    started = time.monotonic()
    for value, before in zip(race_values, initial, strict=True):
        expect(value).not_to_have_text(before, timeout=int(max_acceptable_s * 1000))
    elapsed = time.monotonic() - started
    assert elapsed < max_acceptable_s, (
        f"Async vars took {elapsed:.2f}s; expected under {max_acceptable_s:.2f}s "
        f"(lock_expiration={manager.lock_expiration / 1000:.2f}s)."
    )
