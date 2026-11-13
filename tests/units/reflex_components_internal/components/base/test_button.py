"""Tests for the internal button component."""

import pytest
from reflex_base.utils.exceptions import BackendVarFormatError
from reflex_components_internal.components.base.button import Button

from reflex.state import BaseState


class ButtonState(BaseState):
    """A state with a backend var."""

    _secret: str = "x"


@pytest.mark.parametrize("validate", [Button.validate_variant, Button.validate_size])
def test_validate_backend_var_raises_format_error(validate):
    """A backend var passed as a variant or size raises the backend var format error.

    Args:
        validate: The validator under test.
    """
    with pytest.raises(
        BackendVarFormatError, match=r"Backend var 'ButtonState\._secret' exists only"
    ):
        validate(ButtonState._secret)
