"""ANSI color formatting for output in terminal."""

from __future__ import annotations

import io
import os
import sys
from functools import reduce
from typing import Iterable, Literal

from reflex.utils.decorator import once

_Attribute = Literal[
    "bold",
    "dark",
    "italic",
    "underline",
    "slow_blink",
    "rapid_blink",
    "reverse",
    "concealed",
    "strike",
]

_ATTRIBUTES: dict[_Attribute, int] = {
    "bold": 1,
    "dark": 2,
    "italic": 3,
    "underline": 4,
    "slow_blink": 5,
    "rapid_blink": 6,
    "reverse": 7,
    "concealed": 8,
    "strike": 9,
}

_Color = Literal[
    "black",
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "light_grey",
    "dark_grey",
    "light_red",
    "light_green",
    "light_yellow",
    "light_blue",
    "light_magenta",
    "light_cyan",
    "white",
    "error",
    "warning",
    "info",
    "success",
    "debug",
]


_COLORS: dict[_Color, int] = {
    "black": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "light_grey": 37,
    "dark_grey": 90,
    "light_red": 91,
    "light_green": 92,
    "light_yellow": 93,
    "light_blue": 94,
    "light_magenta": 95,
    "light_cyan": 96,
    "white": 97,
    "error": 31,
    "warning": 33,
    "info": 36,
    "success": 32,
    "debug": 90,
}

_BackgroundColor = Literal[
    "on_black",
    "on_red",
    "on_green",
    "on_yellow",
    "on_blue",
    "on_magenta",
    "on_cyan",
    "on_light_grey",
    "on_dark_grey",
    "on_light_red",
    "on_light_green",
    "on_light_yellow",
    "on_light_blue",
    "on_light_magenta",
    "on_light_cyan",
    "on_white",
]

BACKGROUND_COLORS: dict[_BackgroundColor, int] = {
    "on_black": 40,
    "on_red": 41,
    "on_green": 42,
    "on_yellow": 43,
    "on_blue": 44,
    "on_magenta": 45,
    "on_cyan": 46,
    "on_light_grey": 47,
    "on_dark_grey": 100,
    "on_light_red": 101,
    "on_light_green": 102,
    "on_light_yellow": 103,
    "on_light_blue": 104,
    "on_light_magenta": 105,
    "on_light_cyan": 106,
    "on_white": 107,
}


_ANSI_CODES = _ATTRIBUTES | BACKGROUND_COLORS | _COLORS


_RESET_MARKER = "\033[0m"


@once
def _can_colorize() -> bool:
    """Check if the output can be colorized.

    Copied from _colorize.can_colorize.

    https://raw.githubusercontent.com/python/cpython/refs/heads/main/Lib/_colorize.py

    Returns:
        If the output can be colorized
    """
    file = sys.stdout

    if not sys.flags.ignore_environment:
        if os.environ.get("PYTHON_COLORS") == "0":
            return False
        if os.environ.get("PYTHON_COLORS") == "1":
            return True
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if os.environ.get("TERM") == "dumb":
        return False

    if not hasattr(file, "fileno"):
        return False

    if sys.platform == "win32":
        try:
            import nt

            if not nt._supports_virtual_terminal():
                return False
        except (ImportError, AttributeError):
            return False

    try:
        return os.isatty(file.fileno())
    except io.UnsupportedOperation:
        return file.isatty()


def _format_str(text: str, ansi_escape_code: int | None) -> str:
    """Format text with ANSI escape code.

    Args:
        text: Text to format
        ansi_escape_code: ANSI escape code

    Returns:
        Formatted text
    """
    if ansi_escape_code is None:
        return text
    return f"\033[{ansi_escape_code}m{text}"


def colored(
    text: object,
    color: _Color | None = None,
    background_color: _BackgroundColor | None = None,
    attrs: Iterable[_Attribute] = (),
) -> str:
    """Colorize text for terminal output.

    Args:
        text: Text to colorize
        color: Text color
        background_color: Background color
        attrs: Text attributes

    Returns:
        Colorized text
    """
    result = str(text)

    if not _can_colorize():
        return result

    ansi_codes_to_apply = [
        _ANSI_CODES.get(x)
        for x in [
            color,
            background_color,
            *attrs,
        ]
        if x
    ]

    return (
        reduce(_format_str, ansi_codes_to_apply, result) + _RESET_MARKER
        if ansi_codes_to_apply
        else result
    )
