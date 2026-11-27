"""Tests for reflex_components_ui.tokens."""

import copy
from collections.abc import Callable
from typing import Any, get_args

import pytest
from reflex_components_ui import tokens
from reflex_components_ui._radix_tokens import VAR_GROUPS
from reflex_components_ui.style.lower import Lowered, lower
from reflex_components_ui.tokens import TokenError

import reflex as rx

SCALES = get_args(tokens.LiteralColorScale)

SCALE_NAMES = (
    "amber, blue, bronze, brown, crimson, cyan, gold, grass, green, indigo, "
    "iris, jade, lime, mauve, mint, olive, orange, pink, plum, purple, red, "
    "ruby, sage, sand, sky, slate, teal, tomato, violet, yellow"
)


def _all(group: Any) -> list[str]:
    """List every token of a group, and of the groups inside it.

    Args:
        group: A token, or a group of tokens.

    Returns:
        The tokens.
    """
    if isinstance(group, str):
        return [group]
    found = list(group._steps)
    for name, value in vars(group).items():
        if name[0] != "_":
            found.extend(_all(value))
    return found


def _every_token() -> list[str]:
    """List every token an app can name.

    Returns:
        The tokens of the module, then the ones of each color scale.
    """
    found = []
    for name, value in vars(tokens).items():
        if name[0] != "_" and isinstance(value, (str, tokens._Tokens)):
            found.extend(_all(value))
    for name in SCALES:
        found.extend(_all(tokens.scale(name)))
    return found


def test_tokens_are_the_custom_properties_of_radix_themes():
    """An app can name every custom property the modules define, and no other."""
    defined = [f"var({name})" for _, names in VAR_GROUPS.values() for name in names]
    assert len(defined) == 1070
    found = _every_token()
    assert sorted(found) == sorted(defined)


def test_color_scales_are_the_generated_ones():
    """The accent and the gray of the theme aside, a scale is a color module."""
    assert sorted(SCALES) == sorted(
        name
        for name, (module, names) in VAR_GROUPS.items()
        if module.startswith("colors/") and len(names) == 28
    )


def test_a_token_is_a_plain_string():
    """The examples of the documentation, and the type every style takes."""
    assert tokens.space[4] == "var(--space-4)"
    assert tokens.radius[3] == "var(--radius-3)"
    assert tokens.radius.full == "var(--radius-full)"
    assert tokens.shadow[3] == "var(--shadow-3)"
    assert tokens.accent[9] == "var(--accent-9)"
    assert tokens.accent.a[3] == "var(--accent-a3)"
    assert tokens.accent.contrast == "var(--accent-contrast)"
    assert tokens.gray[11] == "var(--gray-11)"
    assert tokens.focus.a[5] == "var(--focus-a5)"
    assert tokens.font_size[2] == "var(--font-size-2)"
    assert tokens.line_height[2] == "var(--line-height-2)"
    assert tokens.letter_spacing[2] == "var(--letter-spacing-2)"
    assert tokens.font_weight.bold == "var(--font-weight-bold)"
    assert tokens.heading.line_height[9] == "var(--heading-line-height-9)"
    assert tokens.default.font_family == "var(--default-font-family)"
    assert tokens.code.padding_top == "var(--code-padding-top)"
    assert tokens.color.panel_solid == "var(--color-panel-solid)"
    assert tokens.cursor.slider_thumb_active == "var(--cursor-slider-thumb-active)"
    assert tokens.panel.backdrop_filter == "var(--backdrop-filter-panel)"
    assert tokens.black.a[12] == "var(--black-a12)"
    assert tokens.scaling == "var(--scaling)"
    assert tokens.scale("ruby")[9] == f"{rx.color('ruby', 9)}"
    assert tokens.scale("ruby").a[3] == f"{rx.color('ruby', 3, True)}"
    assert tokens.scale("ruby").track == "var(--ruby-track)"
    assert tokens.scale("ruby") is tokens.scale("ruby")
    assert {type(token) for token in _every_token()} == {str}
    assert f"calc({tokens.space[4]} * 2)" == "calc(var(--space-4) * 2)"


def test_every_token_lowers_to_itself_and_imports_its_module():
    """A style names the module that defines each token it uses."""
    count = 0
    for module, names in VAR_GROUPS.values():
        for name in names:
            token = f"var({name})"
            assert lower("rx.ui.box", {"--probe": token}) == Lowered(
                {"--probe": token}, (f"$/reflex-ui/{module}",)
            ), name
            count += 1
    assert count == len(_every_token())


@pytest.mark.parametrize(
    ("get", "message"),
    [
        (
            lambda: tokens.space[10],  # pyright: ignore [reportArgumentType]
            "rx.ui.tokens.space has no step 10. Its steps are 1 to 9.",
        ),
        (
            lambda: tokens.space[0],  # pyright: ignore [reportArgumentType]
            "rx.ui.tokens.space has no step 0. Its steps are 1 to 9.",
        ),
        (
            lambda: tokens.space[-1],  # pyright: ignore [reportArgumentType]
            "rx.ui.tokens.space has no step -1. Its steps are 1 to 9.",
        ),
        (
            lambda: tokens.space["4"],  # pyright: ignore [reportArgumentType]
            "rx.ui.tokens.space has no step '4'. Its steps are 1 to 9.",
        ),
        (
            lambda: tokens.space[True],
            "rx.ui.tokens.space has no step True. Its steps are 1 to 9.",
        ),
        (
            lambda: tokens.radius[7],  # pyright: ignore [reportArgumentType]
            "rx.ui.tokens.radius has no step 7. Its steps are 1 to 6.",
        ),
        (
            lambda: tokens.accent.a[13],  # pyright: ignore [reportArgumentType]
            "rx.ui.tokens.accent.a has no step 13. Its steps are 1 to 12.",
        ),
        (
            lambda: tokens.scale("ruby").a[0],  # pyright: ignore [reportArgumentType]
            'rx.ui.tokens.scale("ruby").a has no step 0. Its steps are 1 to 12.',
        ),
        (
            lambda: tokens.font_weight[1],
            "rx.ui.tokens.font_weight has no steps. Its tokens are bold, light, "
            "medium, regular.",
        ),
        (
            lambda: tokens.black[3],
            "rx.ui.tokens.black has no steps. Its tokens are a.",
        ),
        (
            lambda: tokens.accent.contrst,  # pyright: ignore [reportAttributeAccessIssue]
            'rx.ui.tokens.accent has no token "contrst". Did you mean '
            '"contrast"? Its tokens are a, contrast, indicator, surface, track, '
            "and the steps [1] to [12].",
        ),
        (
            lambda: tokens.space.four,  # pyright: ignore [reportAttributeAccessIssue]
            'rx.ui.tokens.space has no token "four". Its tokens are the steps '
            "[1] to [9].",
        ),
        (
            lambda: tokens.font_weight.semibold,  # pyright: ignore [reportAttributeAccessIssue]
            'rx.ui.tokens.font_weight has no token "semibold". Did you mean "bold"? Its tokens are '
            "bold, light, medium, regular.",
        ),
        (
            lambda: tokens.focus.contrast,  # pyright: ignore [reportAttributeAccessIssue]
            'rx.ui.tokens.focus has no token "contrast". Its tokens are a, and '
            "the steps [1] to [12].",
        ),
        (
            lambda: tokens.scale("rubby"),  # pyright: ignore [reportArgumentType]
            'rx.ui.tokens.scale: unknown color scale "rubby". Did you mean '
            f'"ruby"? The scales are {SCALE_NAMES}.',
        ),
        (
            lambda: tokens.scale("gray"),  # pyright: ignore [reportArgumentType]
            'rx.ui.tokens.scale: "gray" is not a color scale of its own, but '
            "the gray of the theme: use rx.ui.tokens.gray.",
        ),
        (
            lambda: tokens.scale(9),  # pyright: ignore [reportArgumentType]
            f"rx.ui.tokens.scale: unknown color scale 9. The scales are {SCALE_NAMES}.",
        ),
    ],
)
def test_a_token_that_does_not_exist_says_what_does(
    get: Callable[[], str], message: str
):
    """The same mistakes a type checker reports, where the app runs.

    Args:
        get: Asks for the token.
        message: The whole error message.
    """
    with pytest.raises(TokenError) as error:
        get()
    assert str(error.value) == message


def test_token_error_is_what_python_expects_of_a_missing_name():
    """``hasattr`` and ``getattr`` with a default work, and so does copying."""
    assert not hasattr(tokens.accent, "contrst")
    assert getattr(tokens.accent, "contrst", None) is None
    assert issubclass(TokenError, (AttributeError, LookupError))
    assert copy.deepcopy(tokens.accent).a[3] == "var(--accent-a3)"


def test_tokens_are_a_name_of_the_ui_namespace():
    assert rx.ui.tokens is tokens
    assert "tokens" in dir(rx.ui)
