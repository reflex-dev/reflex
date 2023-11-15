"""Handle styling."""

from __future__ import annotations

from nextpy import constants
from nextpy.core.event import EventChain
from nextpy.utils import format
from nextpy.core.vars import BaseVar, Var

color_mode = BaseVar(_var_name=constants.ColorMode.NAME, _var_type="str")
toggle_color_mode = BaseVar(_var_name=constants.ColorMode.TOGGLE, _var_type=EventChain)


def convert(style_dict):
    """Format a style dictionary.

    Args:
        style_dict: The style dictionary to format.

    Returns:
        The formatted style dictionary.
    """
    out = {}
    for key, value in style_dict.items():
        key = format.to_camel_case(key)
        if isinstance(value, dict):
            out[key] = convert(value)
        elif isinstance(value, Var):
            out[key] = str(value)
        else:
            out[key] = value
    return out


class Style(dict):
    """A style dictionary."""

    def __init__(self, style_dict: dict | None = None):
        """Initialize the style.

        Args:
            style_dict: The style dictionary.
        """
        style_dict = style_dict or {}
        super().__init__(convert(style_dict))
