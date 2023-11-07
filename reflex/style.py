"""Handle styling."""

from __future__ import annotations

from typing import Any

from reflex import constants
from reflex.event import EventChain
from reflex.utils import format, imports
from reflex.vars import BaseVar, ImportVar, Var

color_mode_imports = {
    f"/{constants.Dirs.CONTEXTS_PATH}": {ImportVar(tag="ColorModeContext")},
}
color_mode_hooks = {
    f"const [ {{{constants.ColorMode.NAME}}}, {{{constants.ColorMode.TOGGLE}}} ] = useContext(ColorModeContext)",
}
color_mode = BaseVar(
    _var_name=constants.ColorMode.NAME,
    _var_type="str",
    _var_imports=color_mode_imports,
    _var_hooks=color_mode_hooks,
)
toggle_color_mode = BaseVar(
    _var_name=constants.ColorMode.TOGGLE,
    _var_type=EventChain,
    _var_imports=color_mode_imports,
    _var_hooks=color_mode_hooks,
)


def convert(style_dict):
    """Format a style dictionary.

    Args:
        style_dict: The style dictionary to format.

    Returns:
        The formatted style dictionary.
    """
    var_data = Var.create("")
    out = {}
    for key, value in style_dict.items():
        key = format.to_camel_case(key)
        if isinstance(value, dict):
            out[key], new_var_data = convert(value)
        else:
            new_var_data = Var.create(value, _var_is_string=True)
            out[key] = str(new_var_data)
        var_data = var_data._replace(
            add_imports=new_var_data._var_imports, add_hooks=new_var_data._var_hooks
        )
    return out, var_data


class Style(dict):
    """A style dictionary."""

    def __init__(self, style_dict: dict | None = None):
        """Initialize the style.

        Args:
            style_dict: The style dictionary.
        """
        style_dict, var_data = convert(style_dict or {})
        self._var_imports = var_data._var_imports
        self._var_hooks = var_data._var_hooks
        super().__init__(style_dict)

    def update(self, style_dict: dict | None = None):
        """Update the style.

        Args:
            style_dict: The style dictionary.
        """
        converted_dict = type(self)(style_dict)
        self._var_imports = imports.merge_imports(
            self._var_imports, converted_dict._var_imports
        )
        self._var_hooks.update(converted_dict._var_hooks)
        super().update(converted_dict)

    def __setitem__(self, key: str, value: Any):
        """Set an item in the style.

        Args:
            key: The key to set.
            value: The value to set.
        """
        _var = Var.create(value)
        self._var_imports = imports.merge_imports(self._var_imports, _var._var_imports)
        self._var_hooks.update(_var._var_hooks)
        super().__setitem__(key, value)
