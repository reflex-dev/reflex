"""Handle styling."""

from __future__ import annotations

from typing import Any

from reflex import constants
from reflex.event import EventChain
from reflex.utils import format
from reflex.vars import BaseVar, Var, _decode_var_state

color_mode = BaseVar(_var_name=constants.ColorMode.NAME, _var_type="str")
toggle_color_mode = BaseVar(_var_name=constants.ColorMode.TOGGLE, _var_type=EventChain)


def convert(style_dict) -> tuple[dict, str]:
    """Format a style dictionary.

    Args:
        style_dict: The style dictionary to format.

    Returns:
        A tuple of the formatted style dictionary and any state Var depends on.
    """
    var_state = ""
    out = {}
    for key, value in style_dict.items():
        key = format.to_camel_case(key)
        if isinstance(value, dict):
            out[key], maybe_var_state = convert(value)
            var_state = var_state or maybe_var_state
        elif isinstance(value, Var):
            out[key] = str(value)
            var_state = var_state or value._var_state
        else:
            maybe_var_state, out[key] = _decode_var_state(value)
            var_state = var_state or maybe_var_state
    return out, var_state


class Style(dict):
    """A style dictionary."""

    def __init__(self, style_dict: dict | None = None):
        """Initialize the style.

        Args:
            style_dict: The style dictionary.
        """
        self._var_state = ""
        converted_dict, self._var_state = convert(style_dict or {})
        super().__init__(converted_dict)

    def update(self, style_dict: dict | None = None):
        """Update the style.

        Args:
            style_dict: The style dictionary.
        """
        converted_dict = type(self)(style_dict)
        self._var_state = self._var_state or converted_dict._var_state
        super().update(converted_dict)

    def __setitem__(self, key: str, value: Any):
        """Set an item in the style.

        Args:
            key: The key to set.
            value: The value to set.
        """
        if not self._var_state and isinstance(value, Var):
            self._var_state = value._var_state
        super().__setitem__(key, value)
