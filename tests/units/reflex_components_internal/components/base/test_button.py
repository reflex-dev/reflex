"""Tests for the internal button component."""

import pytest
from reflex_components_internal.components.base.button import Button

from reflex.state import BaseState


class ButtonState(BaseState):
    """A state with a backend var."""

    _secret: str = "x"


@pytest.mark.parametrize(
    ("validate", "match"),
    [
        (Button.validate_variant, r"Invalid variant: Field\(default='x'"),
        (Button.validate_size, r"Invalid size: Field\(default='x'"),
    ],
)
def test_validate_backend_var_reports_repr(validate, match: str):
    """A backend var passed as a variant or size reports its repr.

    Args:
        validate: The validator under test.
        match: The expected error message pattern.
    """
    with pytest.raises(ValueError, match=match):
        validate(ButtonState._secret)
