import pytest
from reflex_base.vars.base import Var
from reflex_components_core.ui.components.button import (
    BUTTON_SIZES,
    BUTTON_VARIANTS,
    Button,
)

import reflex as rx


def test_button_defaults_to_primary_md() -> None:
    """The default button renders the primary variant at medium size."""
    rendered = str(Button.create("Go"))

    assert BUTTON_VARIANTS["primary"] in rendered
    assert BUTTON_SIZES["md"] in rendered
    assert '"data-slot":"button"' in rendered


def test_button_variant_and_size_are_static_literals() -> None:
    """Static variant and size resolve to one literal class string."""
    button = Button.create("Go", variant="outline", size="lg")

    assert isinstance(button.class_name, str)
    assert BUTTON_VARIANTS["outline"] in button.class_name
    assert BUTTON_SIZES["lg"] in button.class_name


def test_button_invalid_variant_raises() -> None:
    """Unknown variants raise a ValueError naming the options."""
    with pytest.raises(ValueError, match="Invalid variant"):
        Button.create("Go", variant="fancy")  # pyright: ignore[reportArgumentType]


def test_button_var_variant_keeps_all_literals() -> None:
    """A Var variant compiles to an expression with every class literal."""
    rendered = str(
        Button.create("Go", variant=Var("state.v").to(str))  # pyright: ignore[reportArgumentType]
    )

    for class_name in BUTTON_VARIANTS.values():
        assert class_name in rendered


def test_button_loading_static_disables_and_shows_spinner() -> None:
    """loading=True disables the button and prepends a spinner."""
    rendered = str(Button.create("Go", loading=True))

    assert "animate-spin" in rendered
    assert "disabled:true" in rendered


def test_button_loading_var_uses_cond() -> None:
    """A Var loading prop conditions both the spinner and disabled state."""
    loading = Var("state.loading").to(bool)
    rendered = str(Button.create("Go", loading=loading))

    assert "animate-spin" in rendered
    assert "state.loading" in rendered
    assert "disabled:" in rendered


def test_button_exposed_under_rx_ui() -> None:
    """The button factory is reachable as rx.ui.button."""
    assert rx.ui.button == Button.create
