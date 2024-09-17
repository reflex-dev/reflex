"""Handle styling."""

from __future__ import annotations

from typing import Any, Literal, Tuple, Type

from reflex import constants
from reflex.components.core.breakpoints import Breakpoints, breakpoints_values
from reflex.event import EventChain, EventHandler
from reflex.utils import format
from reflex.utils.exceptions import ReflexError
from reflex.utils.imports import ImportVar
from reflex.vars import VarData
from reflex.vars.base import CallableVar, LiteralVar, Var
from reflex.vars.function import FunctionVar

SYSTEM_COLOR_MODE: str = "system"
LIGHT_COLOR_MODE: str = "light"
DARK_COLOR_MODE: str = "dark"
LiteralColorMode = Literal["system", "light", "dark"]

# Reference the global ColorModeContext
color_mode_imports = {
    f"/{constants.Dirs.CONTEXTS_PATH}": [ImportVar(tag="ColorModeContext")],
    "react": [ImportVar(tag="useContext")],
}


def _color_mode_var(_js_expr: str, _var_type: Type = str) -> Var:
    """Create a Var that destructs the _js_expr from ColorModeContext.

    Args:
        _js_expr: The name of the variable to get from ColorModeContext.
        _var_type: The type of the Var.

    Returns:
        The Var that resolves to the color mode.
    """
    return Var(
        _js_expr=_js_expr,
        _var_type=_var_type,
        _var_data=VarData(
            imports=color_mode_imports,
            hooks={f"const {{ {_js_expr} }} = useContext(ColorModeContext)": None},
        ),
    ).guess_type()


@CallableVar
def set_color_mode(
    new_color_mode: LiteralColorMode | Var[LiteralColorMode] | None = None,
) -> Var[EventChain]:
    """Create an EventChain Var that sets the color mode to a specific value.

    Note: `set_color_mode` is not a real event and cannot be triggered from a
    backend event handler.

    Args:
        new_color_mode: The color mode to set.

    Returns:
        The EventChain Var that can be passed to an event trigger.
    """
    base_setter = _color_mode_var(
        _js_expr=constants.ColorMode.SET,
        _var_type=EventChain,
    )
    if new_color_mode is None:
        return base_setter

    if not isinstance(new_color_mode, Var):
        new_color_mode = LiteralVar.create(new_color_mode)

    return Var(
        f"() => {str(base_setter)}({str(new_color_mode)})",
        _var_data=VarData.merge(
            base_setter._get_all_var_data(), new_color_mode._get_all_var_data()
        ),
    ).to(FunctionVar, EventChain)  # type: ignore


# Var resolves to the current color mode for the app ("light", "dark" or "system")
color_mode = _color_mode_var(_js_expr=constants.ColorMode.NAME)
# Var resolves to the resolved color mode for the app ("light" or "dark")
resolved_color_mode = _color_mode_var(_js_expr=constants.ColorMode.RESOLVED_NAME)
# Var resolves to a function invocation that toggles the color mode
toggle_color_mode = _color_mode_var(
    _js_expr=constants.ColorMode.TOGGLE,
    _var_type=EventChain,
)

STYLE_PROP_SHORTHAND_MAPPING = {
    "paddingX": ("paddingInlineStart", "paddingInlineEnd"),
    "paddingY": ("paddingTop", "paddingBottom"),
    "marginX": ("marginInlineStart", "marginInlineEnd"),
    "marginY": ("marginTop", "marginBottom"),
    "bg": ("background",),
    "bgColor": ("backgroundColor",),
    # Radix components derive their font from this CSS var, not inherited from body or class.
    "fontFamily": ("fontFamily", "--default-font-family"),
}


def media_query(breakpoint_expr: str):
    """Create a media query selector.

    Args:
        breakpoint_expr: The CSS expression representing the breakpoint.

    Returns:
        The media query selector used as a key in emotion css dict.
    """
    return f"@media screen and (min-width: {breakpoint_expr})"


def convert_item(
    style_item: int | str | Var,
) -> tuple[str | Var, VarData | None]:
    """Format a single value in a style dictionary.

    Args:
        style_item: The style item to format.

    Returns:
        The formatted style item and any associated VarData.

    Raises:
        ReflexError: If an EventHandler is used as a style value
    """
    if isinstance(style_item, EventHandler):
        raise ReflexError(
            "EventHandlers cannot be used as style values. "
            "Please use a Var or a literal value."
        )

    if isinstance(style_item, Var):
        return style_item, style_item._get_all_var_data()

    # if isinstance(style_item, str) and REFLEX_VAR_OPENING_TAG not in style_item:
    #     return style_item, None

    # Otherwise, convert to Var to collapse VarData encoded in f-string.
    new_var = LiteralVar.create(style_item)
    var_data = new_var._get_all_var_data() if new_var is not None else None
    return new_var, var_data


def convert_list(
    responsive_list: list[str | dict | Var],
) -> tuple[list[str | dict[str, Var | list | dict]], VarData | None]:
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


def convert(
    style_dict: dict[str, Var | dict | list | str],
) -> tuple[dict[str, str | list | dict], VarData | None]:
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
        if isinstance(value, Var):
            return_val = value
            new_var_data = value._get_all_var_data()
            update_out_dict(return_val, keys)
        elif isinstance(value, dict):
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

    if isinstance(style_dict, Breakpoints):
        out = Breakpoints(out).factorize()

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

    def __init__(self, style_dict: dict | None = None, **kwargs):
        """Initialize the style.

        Args:
            style_dict: The style dictionary.
            kwargs: Other key value pairs to apply to the dict update.
        """
        if style_dict:
            style_dict.update(kwargs)
        else:
            style_dict = kwargs
        style_dict, self._var_data = convert(style_dict or {})
        super().__init__(style_dict)

    def update(self, style_dict: dict | None, **kwargs):
        """Update the style.

        Args:
            style_dict: The style dictionary.
            kwargs: Other key value pairs to apply to the dict update.
        """
        if not isinstance(style_dict, Style):
            converted_dict = type(self)(style_dict)
        else:
            converted_dict = style_dict
        if kwargs:
            if converted_dict is None:
                converted_dict = type(self)(kwargs)
            else:
                converted_dict.update(kwargs)
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
        _var = LiteralVar.create(value)
        if _var is not None:
            # Carry the imports/hooks when setting a Var as a value.
            self._var_data = VarData.merge(self._var_data, _var._get_all_var_data())
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
        if isinstance(value, (Breakpoints, list)):
            if isinstance(value, Breakpoints):
                mbps = {
                    media_query(bp): (
                        bp_value if isinstance(bp_value, dict) else {key: bp_value}
                    )
                    for bp, bp_value in value.items()
                }
            else:
                # Apply media queries from responsive value list.
                mbps = {
                    media_query([0, *breakpoints_values][bp]): (
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
    raw_dict: dict[str, Any],
) -> dict[str, Any] | None:
    """Convert a dict to a style dict and then format as emotion.

    Args:
        raw_dict: The dict to convert.

    Returns:
        The emotion dict.

    """
    return format_as_emotion(Style(raw_dict))


STACK_CHILDREN_FULL_WIDTH = {
    "& :where(.rx-Stack)": {
        "width": "100%",
    },
    "& :where(.rx-Stack) > :where( "
    "div:not(.rt-Box, .rx-Upload, .rx-Html),"
    "input, select, textarea, table"
    ")": {
        "width": "100%",
        "flex_shrink": "1",
    },
}
