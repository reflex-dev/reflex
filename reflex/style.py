"""Handle styling."""

from __future__ import annotations

from typing import Any

from reflex import constants
from reflex.event import EventChain
from reflex.utils import format
from reflex.utils.imports import ImportVar
from reflex.vars import BaseVar, Var, VarData

VarData.update_forward_refs()  # Ensure all type definitions are resolved

# Reference the global ColorModeContext
color_mode_var_data = VarData(  # type: ignore
    imports={
        f"/{constants.Dirs.CONTEXTS_PATH}": {ImportVar(tag="ColorModeContext")},
        "react": {ImportVar(tag="useContext")},
    },
    hooks={
        f"const [ {constants.ColorMode.NAME}, {constants.ColorMode.TOGGLE} ] = useContext(ColorModeContext)",
    },
)
# Var resolves to the current color mode for the app ("light" or "dark")
color_mode = BaseVar(
    _var_name=constants.ColorMode.NAME,
    _var_type="str",
    _var_data=color_mode_var_data,
)
# Var resolves to a function invocation that toggles the color mode
toggle_color_mode = BaseVar(
    _var_name=constants.ColorMode.TOGGLE,
    _var_type=EventChain,
    _var_data=color_mode_var_data,
)


def convert(style_dict):
    """Format a style dictionary.

    Args:
        style_dict: The style dictionary to format.

    Returns:
        The formatted style dictionary.
    """
    var_data = None  # Track import/hook data from any Vars in the style dict.
    out = {}
    for key, value in style_dict.items():
        key = format.to_camel_case(key)
        new_var_data = None
        if isinstance(value, dict):
            # Recursively format nested style dictionaries.
            out[key], new_var_data = convert(value)
        elif isinstance(value, Var):
            # If the value is a Var, extract the var_data and cast as str.
            new_var_data = value._var_data
            out[key] = str(value)
        else:
            # Otherwise, convert to Var to collapse VarData encoded in f-string.
            new_var = Var.create(value)
            if new_var is not None:
                new_var_data = new_var._var_data
            out[key] = value
        # Combine all the collected VarData instances.
        var_data = VarData.merge(var_data, new_var_data)
    return out, var_data


class Style(dict):
    """A style dictionary."""

    def __init__(self, style_dict: dict | None = None):
        """Initialize the style.

        Args:
            style_dict: The style dictionary.
        """
        style_dict, self._var_data = convert(style_dict or {})
        super().__init__(style_dict)

    def update(self, style_dict: dict | None, **kwargs):
        """Update the style.

        Args:
            style_dict: The style dictionary.
            kwargs: Other key value pairs to apply to the dict update.
        """
        if kwargs:
            style_dict = {**(style_dict or {}), **kwargs}
        if not isinstance(style_dict, Style):
            converted_dict = type(self)(style_dict)
        else:
            converted_dict = style_dict
        # Combine our VarData with that of any Vars in the style_dict that was passed.
        self._var_data = VarData.merge(self._var_data, converted_dict._var_data)
        super().update(converted_dict)

    def __setitem__(self, key: str, value: Any):
        """Set an item in the style.

        Args:
            key: The key to set.
            value: The value to set.
        """
        # Create a Var to collapse VarData encoded in f-string.
        _var = Var.create(value)
        if _var is not None:
            # Carry the imports/hooks when setting a Var as a value.
            self._var_data = VarData.merge(self._var_data, _var._var_data)
        super().__setitem__(key, value)
