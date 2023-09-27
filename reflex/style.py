"""Handle styling."""

from __future__ import annotations

from reflex import constants
from reflex.event import EventChain
from reflex.utils import format
from reflex.vars import BaseVar, Var

color_mode = BaseVar(name=constants.ColorMode.NAME, type_="str")
toggle_color_mode = BaseVar(name=constants.ColorMode.TOGGLE, type_=EventChain)


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
