"""Handle styling."""

from __future__ import annotations

from typing import Any, Tuple

from reflex import constants
from reflex.event import EventChain
from reflex.utils import format
from reflex.utils.imports import ImportVar
from reflex.vars import BaseVar, Var, VarData

VarData.update_forward_refs()  # Ensure all type definitions are resolved

LIGHT_COLOR_MODE: str = "light"
DARK_COLOR_MODE: str = "dark"

# Reference the global ColorModeContext
color_mode_var_data = VarData(  # type: ignore
    imports={
        f"/{constants.Dirs.CONTEXTS_PATH}": {ImportVar(tag="ColorModeContext")},
        "react": {ImportVar(tag="useContext")},
    },
    hooks={
        f"const [ {constants.ColorMode.NAME}, {constants.ColorMode.TOGGLE} ] = useContext(ColorModeContext)": None,
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

breakpoints = ["0", "30em", "48em", "62em", "80em", "96em"]

STYLE_PROP_SHORTHAND_MAPPING = {
    "paddingX": ("paddingInlineStart", "paddingInlineEnd"),
    "paddingY": ("paddingTop", "paddingBottom"),
    "marginX": ("marginInlineStart", "marginInlineEnd"),
    "marginY": ("marginTop", "marginBottom"),
    "bg": ("background",),
    "bgColor": ("backgroundColor",),
}


def media_query(breakpoint_index: int):
    """Create a media query selector.

    Args:
        breakpoint_index: The index of the breakpoint to use.

    Returns:
        The media query selector used as a key in emotion css dict.
    """
    return f"@media screen and (min-width: {breakpoints[breakpoint_index]})"


def convert_item(style_item: str | Var) -> tuple[str, VarData | None]:
    """Format a single value in a style dictionary.

    Args:
        style_item: The style item to format.

    Returns:
        The formatted style item and any associated VarData.
    """
    if isinstance(style_item, Var):
        # If the value is a Var, extract the var_data and cast as str.
        return str(style_item), style_item._var_data

    # Otherwise, convert to Var to collapse VarData encoded in f-string.
    new_var = Var.create(style_item)
    if new_var is not None and new_var._var_data:
        # The wrapped backtick is used to identify the Var for interpolation.
        return f"`{str(new_var)}`", new_var._var_data

    return style_item, None


def convert_list(
    responsive_list: list[str | dict | Var],
) -> tuple[list[str | dict], VarData | None]:
    """Format a responsive value list.

    Args:
        responsive_list: The raw responsive value list (one value per breakpoint).

    Returns:
        The recursively converted responsive value list and any associated VarData.
    """
    converted_value = []
    item_var_datas = []
    for responsive_item in responsive_list:
        if isinstance(responsive_item, dict):
            # Recursively format nested style dictionaries.
            item, item_var_data = convert(responsive_item)
        else:
            item, item_var_data = convert_item(responsive_item)
        converted_value.append(item)
        item_var_datas.append(item_var_data)
    return converted_value, VarData.merge(*item_var_datas)


def convert(style_dict):
    """Format a style dictionary.

    Args:
        style_dict: The style dictionary to format.

    Returns:
        The formatted style dictionary.
    """
    var_data = None  # Track import/hook data from any Vars in the style dict.
    out = {}

    def update_out_dict(return_value, keys_to_update):
        for k in keys_to_update:
            out[k] = return_value

    for key, value in style_dict.items():
        keys = format_style_key(key)
        if isinstance(value, dict):
            # Recursively format nested style dictionaries.
            return_val, new_var_data = convert(value)
            update_out_dict(return_val, keys)
        elif isinstance(value, list):
            # Responsive value is a list of dict or value
            return_val, new_var_data = convert_list(value)
            update_out_dict(return_val, keys)
        else:
            return_val, new_var_data = convert_item(value)
            update_out_dict(return_val, keys)
        # Combine all the collected VarData instances.
        var_data = VarData.merge(var_data, new_var_data)
    return out, var_data


def format_style_key(key: str) -> Tuple[str, ...]:
    """Convert style keys to camel case and convert shorthand
    styles names to their corresponding css names.

    Args:
        key: The style key to convert.

    Returns:
        Tuple of css style names corresponding to the key provided.
    """
    key = format.to_camel_case(key, allow_hyphens=True)
    return STYLE_PROP_SHORTHAND_MAPPING.get(key, (key,))


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


def _format_emotion_style_pseudo_selector(key: str) -> str:
    """Format a pseudo selector for emotion CSS-in-JS.

    Args:
        key: Underscore-prefixed or colon-prefixed pseudo selector key (_hover).

    Returns:
        A self-referential pseudo selector key (&:hover).
    """
    prefix = None
    if key.startswith("_"):
        # Handle pseudo selectors in chakra style format.
        prefix = "&:"
        key = key[1:]
    if key.startswith(":"):
        # Handle pseudo selectors and elements in native format.
        prefix = "&"
    if prefix is not None:
        return prefix + format.to_kebab_case(key)
    return key


def format_as_emotion(style_dict: dict[str, Any]) -> Style | None:
    """Convert the style to an emotion-compatible CSS-in-JS dict.

    Args:
        style_dict: The style dict to convert.

    Returns:
        The emotion style dict.
    """
    _var_data = style_dict._var_data if isinstance(style_dict, Style) else None

    emotion_style = Style()

    for orig_key, value in style_dict.items():
        key = _format_emotion_style_pseudo_selector(orig_key)
        if isinstance(value, list):
            # Apply media queries from responsive value list.
            mbps = {
                media_query(bp): (
                    bp_value if isinstance(bp_value, dict) else {key: bp_value}
                )
                for bp, bp_value in enumerate(value)
            }
            if key.startswith("&:"):
                emotion_style[key] = mbps
            else:
                for mq, style_sub_dict in mbps.items():
                    emotion_style.setdefault(mq, {}).update(style_sub_dict)
        elif isinstance(value, dict):
            # Recursively format nested style dictionaries.
            emotion_style[key] = format_as_emotion(value)
        else:
            emotion_style[key] = value
    if emotion_style:
        if _var_data is not None:
            emotion_style._var_data = VarData.merge(emotion_style._var_data, _var_data)
        return emotion_style


def convert_dict_to_style_and_format_emotion(
    raw_dict: dict[str, Any]
) -> dict[str, Any] | None:
    """Convert a dict to a style dict and then format as emotion.

    Args:
        raw_dict: The dict to convert.

    Returns:
        The emotion dict.

    """
    return format_as_emotion(Style(raw_dict))
