import pytest
from reflex_base.vars.base import Var

import reflex as rx


def _make_tabs(**props):
    return rx.ui.tabs(
        rx.ui.tabs.list(
            rx.ui.tabs.trigger("Account", value="account"),
            rx.ui.tabs.trigger("Password", value="password"),
        ),
        rx.ui.tabs.content("account panel", value="account"),
        rx.ui.tabs.content("password panel", value="password"),
        **props,
    )


def test_tabs_have_aria_roles_and_keyboard_nav() -> None:
    """The tab list and triggers carry WAI-ARIA roles and roving focus."""
    rendered = str(_make_tabs())

    assert 'role:"tablist"' in rendered
    assert rendered.count('role:"tab"') >= 2
    assert rendered.count('role:"tabpanel"') == 2
    assert "onKeyDown" in rendered
    assert "ArrowRight" in rendered


def test_uncontrolled_tabs_use_client_state() -> None:
    """Without a value prop, selection is kept in client-side state."""
    rendered = str(_make_tabs())

    assert "refs" in rendered
    assert "data-state" in rendered
    assert "inactive" in rendered


def test_uncontrolled_tabs_default_to_first_trigger() -> None:
    """The first trigger's value seeds the client state default."""
    tabs = _make_tabs()
    hooks = " ".join(map(str, tabs._get_all_hooks()))

    assert '"account"' in hooks


def test_controlled_tabs_wire_on_change() -> None:
    """A controlled tabs root wires value equality and on_change events."""

    class TabState(rx.State):
        tab: str = "account"

        @rx.event
        def change_tab(self, value: str):
            self.tab = value

    rendered = str(_make_tabs(value=TabState.tab, on_change=TabState.change_tab))

    assert "change_tab" in rendered
    assert "refs" not in rendered
    assert "data-state" in rendered


def test_tabs_content_hidden_when_inactive() -> None:
    """Content panels hide via the data-state attribute."""
    rendered = str(_make_tabs())

    assert "data-[state=inactive]:hidden" in rendered


def test_tabs_trigger_requires_value() -> None:
    """A trigger without a value raises at create time."""
    with pytest.raises(ValueError, match="trigger requires a value"):
        rx.ui.tabs(rx.ui.tabs.list(rx.ui.tabs.trigger("Broken")))


def test_tabs_var_trigger_values_supported() -> None:
    """Var trigger values participate in selection comparisons."""
    item = Var("item").to(str)
    rendered = str(
        rx.ui.tabs(
            rx.ui.tabs.list(rx.ui.tabs.trigger("A", value=item)),
            rx.ui.tabs.content("panel", value=item),
            default_value="a",
        )
    )

    assert "data-state" in rendered


def test_nested_tabs_are_wired_independently() -> None:
    """A nested tabs root keeps its own selection state."""
    inner = _make_tabs()
    outer = rx.ui.tabs(
        rx.ui.tabs.list(rx.ui.tabs.trigger("Outer", value="outer")),
        rx.ui.tabs.content(inner, value="outer"),
    )

    rendered = str(outer)
    assert rendered.count("tabs_") >= 2
