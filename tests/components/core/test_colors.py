import pytest

import reflex as rx


class ColorState(rx.State):
    """Test color state."""

    color: str = "mint"
    shade: int = 4


@pytest.mark.parametrize(
    "color, expected",
    [
        (rx.color("mint"), "{`var(--mint-7)`}"),
        (rx.color("mint", 3), "{`var(--mint-3)`}"),
        (rx.color("mint", 3, True), "{`var(--mint-a3)`}"),
        (
            rx.color(ColorState.color, ColorState.shade),
            "{`var(--${state__color_state.color}-${state__color_state.shade})`}",
        ),
    ],
)
def test_color(color, expected):
    assert str(color) == expected


@pytest.mark.parametrize(
    "cond_var, expected",
    [
        (
            rx.cond(True, rx.color("mint"), rx.color("tomato", 5)),
            "{isTrue(true) ? `var(--mint-7)` : `var(--tomato-5)`}",
        ),
        (
            rx.cond(True, rx.color(ColorState.color), rx.color(ColorState.color, 5)),
            "{isTrue(true) ? `var(--${state__color_state.color}-7)` : `var(--${state__color_state.color}-5)`}",
        ),
        (
            rx.match(
                "condition",
                ("first", rx.color("mint")),
                ("second", rx.color("tomato", 5)),
                rx.color(ColorState.color, 2),
            ),
            "{(() => { switch (JSON.stringify(`condition`)) {case JSON.stringify(`first`):  return (`var(--mint-7)`);"
            "  break;case JSON.stringify(`second`):  return (`var(--tomato-5)`);  break;default:  "
            "return (`var(--${state__color_state.color}-2)`);  break;};})()}",
        ),
        (
            rx.match(
                "condition",
                ("first", rx.color(ColorState.color)),
                ("second", rx.color(ColorState.color, 5)),
                rx.color(ColorState.color, 2),
            ),
            "{(() => { switch (JSON.stringify(`condition`)) {case JSON.stringify(`first`):  "
            "return (`var(--${state__color_state.color}-7)`);  break;case JSON.stringify(`second`):  "
            "return (`var(--${state__color_state.color}-5)`);  break;default:  "
            "return (`var(--${state__color_state.color}-2)`);  break;};})()}",
        ),
    ],
)
def test_color_with_conditionals(cond_var, expected):
    assert str(cond_var) == expected
