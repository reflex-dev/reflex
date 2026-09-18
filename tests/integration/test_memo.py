"""Integration tests for the ``rx._x.memo`` deprecation shim."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def MemoApp():
    """Reflex app that exercises memo functions and components via ``rx._x.memo``."""
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

    class MemoState(rx.State):
        amount: int = 125
        currency: str = "USD"
        title: str = "Current Price"

        @rx.event
        def increment_amount(self):
            self.amount += 5

    def index() -> rx.Component:
        formatted_price = format_price(
            amount=MemoState.amount,
            currency=MemoState.currency,
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
                on_click=MemoState.increment_amount,
            ),
            summary_card(
                rx.text("Children are passed positionally.", id="summary-child"),
                title=MemoState.title,
                value=formatted_price,
                id="summary-card",
                class_name="forwarded-summary-card",
                font_weight="bold",
                style={"padding": "10px"},
            ),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def memo_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start MemoApp app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest temporary directory factory.

    Yields:
        Running AppHarness instance.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("memo_app"),
        app_source=MemoApp,
    ) as harness:
        yield harness


def test_memo_app(memo_app: AppHarness, page: Page):
    """Render deprecated experimental memos and verify forwarded props.

    Args:
        memo_app: Harness for MemoApp.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)
    expect(page.locator("#experimental-memo-custom-code")).to_have_text("foobarbarbar")
    expect(page.locator("#formatted-price")).to_have_text("USD: $125")
    summary_card = page.locator("#summary-card")
    assert "forwarded-summary-card" in (summary_card.get_attribute("class") or "")
    expect(summary_card).to_have_css("font-weight", "700")
    expect(summary_card).to_have_css("padding", "10px")
    expect(page.locator("#summary-title")).to_have_text("Current Price")
    expect(page.locator("#summary-child")).to_have_text(
        "Children are passed positionally."
    )
    expect(page.locator("#summary-value")).to_have_text("USD: $125")
    page.locator("#increment-price").click()
    expect(page.locator("#formatted-price")).to_have_text("USD: $130")
    expect(page.locator("#summary-value")).to_have_text("USD: $130")
