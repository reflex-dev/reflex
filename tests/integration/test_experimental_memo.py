"""Integration tests for rx._x.memo."""

import re
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def ExperimentalMemoApp():
    """Reflex app that exercises experimental memo functions and components."""
    import reflex as rx

    class FooComponent(rx.Fragment):
        def add_custom_code(self) -> list[str]:
            return [
                "const foo = 'bar'",
            ]

    @rx._x.memo
    def foo_component(label: rx.Var[str]) -> rx.Component:
        return FooComponent.create(label, rx.Var("foo"))

    @rx._x.memo
    def format_price(amount: rx.Var[int], currency: rx.Var[str]) -> rx.Var[str]:
        return currency.to(str) + ": $" + amount.to(str)

    @rx._x.memo
    def summary_card(
        children: rx.Var[rx.Component],
        rest: rx.RestProp,
        *,
        title: rx.Var[str],
        value: rx.Var[str],
    ) -> rx.Component:
        return rx.box(
            rx.heading(title, id="summary-title"),
            rx.text(value, id="summary-value"),
            children,
            rest,
        )

    class ExperimentalMemoState(rx.State):
        amount: int = 125
        currency: str = "USD"
        title: str = "Current Price"

        @rx.event
        def increment_amount(self):
            self.amount += 5

    def index() -> rx.Component:
        formatted_price = format_price(
            amount=ExperimentalMemoState.amount,
            currency=ExperimentalMemoState.currency,
        )
        return rx.vstack(
            rx.vstack(
                foo_component(label="foo"),
                foo_component(label="bar"),
                id="experimental-memo-custom-code",
            ),
            rx.text(formatted_price, id="formatted-price"),
            rx.button(
                "Increment",
                id="increment-price",
                on_click=ExperimentalMemoState.increment_amount,
            ),
            summary_card(
                rx.text("Children are passed positionally.", id="summary-child"),
                title=ExperimentalMemoState.title,
                value=formatted_price,
                id="summary-card",
                class_name="forwarded-summary-card",
            ),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def experimental_memo_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start ExperimentalMemoApp app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture.

    Yields:
        Running AppHarness instance.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("experimental_memo_app"),
        app_source=ExperimentalMemoApp,
    ) as harness:
        yield harness


def test_experimental_memo_app(experimental_memo_app: AppHarness, page: Page):
    """Render experimental memos and assert on their frontend behavior.

    Args:
        experimental_memo_app: Harness for ExperimentalMemoApp.
        page: Playwright Page fixture.
    """
    assert experimental_memo_app.app_instance is not None, "app is not running"
    assert experimental_memo_app.frontend_url is not None
    page.goto(experimental_memo_app.frontend_url)

    memo_custom_code_stack = page.locator("#experimental-memo-custom-code")
    expect(memo_custom_code_stack).to_have_text("foobarbarbar")

    formatted_price = page.locator("#formatted-price")
    expect(formatted_price).to_have_text("USD: $125")

    summary_card = page.locator("#summary-card")
    expect(summary_card).to_have_class(
        re.compile(r"(^|\s)forwarded-summary-card(\s|$)")
    )
    expect(page.locator("#summary-title")).to_have_text("Current Price")
    expect(page.locator("#summary-child")).to_have_text(
        "Children are passed positionally."
    )

    summary_value = page.locator("#summary-value")
    expect(summary_value).to_have_text("USD: $125")

    page.locator("#increment-price").click()
    expect(formatted_price).to_have_text("USD: $130")
    expect(summary_value).to_have_text("USD: $130")
