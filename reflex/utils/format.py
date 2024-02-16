"""Formatting operations."""

from __future__ import annotations

import inspect
import json
import os
import re
import sys
from typing import TYPE_CHECKING, Any, List, Union

from reflex import constants
from reflex.utils import exceptions, serializers, types
from reflex.utils.serializers import serialize
from reflex.vars import BaseVar, Var

if TYPE_CHECKING:
    from reflex.components.component import ComponentStyle
    from reflex.event import EventChain, EventHandler, EventSpec

WRAP_MAP = {
    "{": "}",
    "(": ")",
    "[": "]",
    "<": ">",
    '"': '"',
    "'": "'",
    "`": "`",
}


def get_close_char(open: str, close: str | None = None) -> str:
    """Check if the given character is a valid brace.

    Args:
        open: The open character.
        close: The close character if provided.

    Returns:
        The close character.

    Raises:
        ValueError: If the open character is not a valid brace.
    """
    if close is not None:
        return close
    if open not in WRAP_MAP:
        raise ValueError(f"Invalid wrap open: {open}, must be one of {WRAP_MAP.keys()}")
    return WRAP_MAP[open]


def is_wrapped(text: str, open: str, close: str | None = None) -> bool:
    """Check if the given text is wrapped in the given open and close characters.

    "(a) + (b)" --> False
    "((abc))"   --> True
    "(abc)"     --> True

    Args:
        text: The text to check.
        open: The open character.
        close: The close character.

    Returns:
        Whether the text is wrapped.
    """
    close = get_close_char(open, close)
    if not (text.startswith(open) and text.endswith(close)):
        return False

    depth = 0
    for ch in text[:-1]:
        if ch == open:
            depth += 1
        if ch == close:
            depth -= 1
        if depth == 0:  # it shouldn't close before the end
            return False
    return True


def wrap(
    text: str,
    open: str,
    close: str | None = None,
    check_first: bool = True,
    num: int = 1,
) -> str:
    """Wrap the given text in the given open and close characters.

    Args:
        text: The text to wrap.
        open: The open character.
        close: The close character.
        check_first: Whether to check if the text is already wrapped.
        num: The number of times to wrap the text.

    Returns:
        The wrapped text.
    """
    close = get_close_char(open, close)

    # If desired, check if the text is already wrapped in braces.
    if check_first and is_wrapped(text=text, open=open, close=close):
        return text

    # Wrap the text in braces.
    return f"{open * num}{text}{close * num}"


def indent(text: str, indent_level: int = 2) -> str:
    """Indent the given text by the given indent level.

    Args:
        text: The text to indent.
        indent_level: The indent level.

    Returns:
        The indented text.
    """
    lines = text.splitlines()
    if len(lines) < 2:
        return text
    return os.linesep.join(f"{' ' * indent_level}{line}" for line in lines) + os.linesep


def to_snake_case(text: str) -> str:
    """Convert a string to snake case.

    The words in the text are converted to lowercase and
    separated by underscores.

    Args:
        text: The string to convert.

    Returns:
        The snake case string.
    """
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", text)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower().replace("-", "_")


def to_camel_case(text: str, allow_hyphens: bool = False) -> str:
    """Convert a string to camel case.

    The first word in the text is converted to lowercase and
    the rest of the words are converted to title case, removing underscores.

    Args:
        text: The string to convert.
        allow_hyphens: Whether to allow hyphens in the string.

    Returns:
        The camel case string.
    """
    char = "_" if allow_hyphens else "-_"
    words = re.split(f"[{char}]", text.lstrip(char))
    leading_underscores_or_hyphens = "".join(re.findall(rf"^[{char}]+", text))
    # Capitalize the first letter of each word except the first one
    converted_word = words[0] + "".join(x.capitalize() for x in words[1:])
    return leading_underscores_or_hyphens + converted_word


def to_title_case(text: str) -> str:
    """Convert a string from snake case to title case.

    Args:
        text: The string to convert.

    Returns:
        The title case string.
    """
    return "".join(word.capitalize() for word in text.split("_"))


def to_kebab_case(text: str) -> str:
    """Convert a string to kebab case.

    The words in the text are converted to lowercase and
    separated by hyphens.

    Args:
        text: The string to convert.

    Returns:
        The title case string.
    """
    return to_snake_case(text).replace("_", "-")


def _escape_js_string(string: str) -> str:
    """Escape the string for use as a JS string literal.

    Args:
        string: The string to escape.

    Returns:
        The escaped string.
    """
    # Escape backticks.
    string = string.replace(r"\`", "`")
    string = string.replace("`", r"\`")
    return string


def _wrap_js_string(string: str) -> str:
    """Wrap string so it looks like {`string`}.

    Args:
        string: The string to wrap.

    Returns:
        The wrapped string.
    """
    string = wrap(string, "`")
    string = wrap(string, "{")
    return string


def format_string(string: str) -> str:
    """Format the given string as a JS string literal..

    Args:
        string: The string to format.

    Returns:
        The formatted string.
    """
    return _wrap_js_string(_escape_js_string(string))


def format_f_string_prop(prop: BaseVar) -> str:
    """Format the string in a given prop as an f-string.

    Args:
        prop: The prop to format.

    Returns:
        The formatted string.
    """
    s = prop._var_full_name
    var_data = prop._var_data
    interps = var_data.interpolations if var_data else []
    parts: List[str] = []

    if interps:
        for i, (start, end) in enumerate(interps):
            prev_end = interps[i - 1][1] if i > 0 else 0
            parts.append(_escape_js_string(s[prev_end:start]))
            parts.append(s[start:end])
        parts.append(_escape_js_string(s[interps[-1][1] :]))
    else:
        parts.append(_escape_js_string(s))

    return _wrap_js_string("".join(parts))


def format_var(var: Var) -> str:
    """Format the given Var as a javascript value.

    Args:
        var: The Var to format.

    Returns:
        The formatted Var.
    """
    if not var._var_is_local or var._var_is_string:
        return str(var)
    if types._issubclass(var._var_type, str):
        return format_string(var._var_full_name)
    if is_wrapped(var._var_full_name, "{"):
        return var._var_full_name
    return json_dumps(var._var_full_name)


def format_route(route: str, format_case=True) -> str:
    """Format the given route.

    Args:
        route: The route to format.
        format_case: whether to format case to kebab case.

    Returns:
        The formatted route.
    """
    route = route.strip("/")
    # Strip the route and format casing.
    if format_case:
        route = to_kebab_case(route)

    # If the route is empty, return the index route.
    if route == "":
        return constants.PageNames.INDEX_ROUTE

    return route


def format_cond(
    cond: str | Var,
    true_value: str | Var,
    false_value: str | Var = '""',
    is_prop=False,
) -> str:
    """Format a conditional expression.

    Args:
        cond: The cond.
        true_value: The value to return if the cond is true.
        false_value: The value to return if the cond is false.
        is_prop: Whether the cond is a prop

    Returns:
        The formatted conditional expression.
    """
    # Use Python truthiness.
    cond = f"isTrue({cond})"

    def create_var(cond_part):
        return Var.create_safe(cond_part, _var_is_string=type(cond_part) is str)

    # Format prop conds.
    if is_prop:
        true_value = create_var(true_value)
        prop1 = true_value._replace(
            _var_is_local=True,
        )

        false_value = create_var(false_value)
        prop2 = false_value._replace(_var_is_local=True)
        # unwrap '{}' to avoid f-string semantics for Var
        return f"{cond} ? {prop1._var_name_unwrapped} : {prop2._var_name_unwrapped}"

    # Format component conds.
    return wrap(f"{cond} ? {true_value} : {false_value}", "{")


def format_match(cond: str | Var, match_cases: List[BaseVar], default: Var) -> str:
    """Format a match expression whose return type is a Var.

    Args:
        cond: The condition.
        match_cases: The list of cases to match.
        default: The default case.

    Returns:
        The formatted match expression

    """
    switch_code = f"(() => {{ switch (JSON.stringify({cond})) {{"

    for case in match_cases:
        conditions = case[:-1]
        return_value = case[-1]

        case_conditions = " ".join(
            [
                f"case JSON.stringify({condition._var_name_unwrapped}):"
                for condition in conditions
            ]
        )
        case_code = (
            f"{case_conditions}  return ({return_value._var_name_unwrapped});  break;"
        )
        switch_code += case_code

    switch_code += f"default:  return ({default._var_name_unwrapped});  break;"
    switch_code += "};})()"

    return switch_code


def format_prop(
    prop: Union[Var, EventChain, ComponentStyle, str],
) -> Union[int, float, str]:
    """Format a prop.

    Args:
        prop: The prop to format.

    Returns:
        The formatted prop to display within a tag.

    Raises:
        exceptions.InvalidStylePropError: If the style prop value is not a valid type.
        TypeError: If the prop is not valid.
    """
    # import here to avoid circular import.
    from reflex.event import EventChain

    try:
        # Handle var props.
        if isinstance(prop, Var):
            if not prop._var_is_local or prop._var_is_string:
                return str(prop)
            if isinstance(prop, BaseVar) and types._issubclass(prop._var_type, str):
                if prop._var_data and prop._var_data.interpolations:
                    return format_f_string_prop(prop)
                return format_string(prop._var_full_name)
            prop = prop._var_full_name

        # Handle event props.
        elif isinstance(prop, EventChain):
            sig = inspect.signature(prop.args_spec)  # type: ignore
            if sig.parameters:
                arg_def = ",".join(f"_{p}" for p in sig.parameters)
                arg_def = f"({arg_def})"
            else:
                # add a default argument for addEvents if none were specified in prop.args_spec
                # used to trigger the preventDefault() on the event.
                arg_def = "(_e)"

            chain = ",".join([format_event(event) for event in prop.events])
            event = f"addEvents([{chain}], {arg_def}, {json_dumps(prop.event_actions)})"
            prop = f"{arg_def} => {event}"

        # Handle other types.
        elif isinstance(prop, str):
            if is_wrapped(prop, "{"):
                return prop
            return json_dumps(prop)

        # For dictionaries, convert any properties to strings.
        elif isinstance(prop, dict):
            prop = serializers.serialize_dict(prop)  # type: ignore

        else:
            # Dump the prop as JSON.
            prop = json_dumps(prop)
    except exceptions.InvalidStylePropError:
        raise
    except TypeError as e:
        raise TypeError(f"Could not format prop: {prop} of type {type(prop)}") from e

    # Wrap the variable in braces.
    assert isinstance(prop, str), "The prop must be a string."
    return wrap(prop, "{", check_first=False)


def format_props(*single_props, **key_value_props) -> list[str]:
    """Format the tag's props.

    Args:
        single_props: Props that are not key-value pairs.
        key_value_props: Props that are key-value pairs.

    Returns:
        The formatted props list.
    """
    # Format all the props.
    return [
        f"{name}={format_prop(prop)}"
        for name, prop in sorted(key_value_props.items())
        if prop is not None
    ] + [str(prop) for prop in single_props]


def get_event_handler_parts(handler: EventHandler) -> tuple[str, str]:
    """Get the state and function name of an event handler.

    Args:
        handler: The event handler to get the parts of.

    Returns:
        The state and function name.
    """
    # Get the class that defines the event handler.
    parts = handler.fn.__qualname__.split(".")

    # If there's no enclosing class, just return the function name.
    if len(parts) == 1:
        return ("", parts[-1])

    # Get the state and the function name.
    state_name, name = parts[-2:]

    # Construct the full event handler name.
    try:
        # Try to get the state from the module.
        state = vars(sys.modules[handler.fn.__module__])[state_name]
    except Exception:
        # If the state isn't in the module, just return the function name.
        return ("", to_snake_case(handler.fn.__qualname__))

    return (state.get_full_name(), name)


def format_event_handler(handler: EventHandler) -> str:
    """Format an event handler.

    Args:
        handler: The event handler to format.

    Returns:
        The formatted function.
    """
    state, name = get_event_handler_parts(handler)
    if state == "":
        return name
    return f"{state}.{name}"


def format_event(event_spec: EventSpec) -> str:
    """Format an event.

    Args:
        event_spec: The event to format.

    Returns:
        The compiled event.
    """
    args = ",".join(
        [
            ":".join(
                (
                    name._var_name,
                    wrap(json.dumps(val._var_name).strip('"').replace("`", "\\`"), "`")
                    if val._var_is_string
                    else val._var_full_name,
                )
            )
            for name, val in event_spec.args
        ]
    )
    event_args = [
        wrap(format_event_handler(event_spec.handler), '"'),
    ]
    event_args.append(wrap(args, "{"))

    if event_spec.client_handler_name:
        event_args.append(wrap(event_spec.client_handler_name, '"'))
    return f"Event({', '.join(event_args)})"


def format_event_chain(
    event_chain: EventChain | Var[EventChain],
    event_arg: Var | None = None,
) -> str:
    """Format an event chain as a javascript invocation.

    Args:
        event_chain: The event chain to queue on the frontend.
        event_arg: The browser-native event (only used to preventDefault).

    Returns:
        Compiled javascript code to queue the given event chain on the frontend.

    Raises:
        ValueError: When the given event chain is not a valid event chain.
    """
    if isinstance(event_chain, Var):
        from reflex.event import EventChain

        if event_chain._var_type is not EventChain:
            raise ValueError(f"Invalid event chain: {event_chain}")
        return "".join(
            [
                "(() => {",
                format_var(event_chain),
                f"; preventDefault({format_var(event_arg)})" if event_arg else "",
                "})()",
            ]
        )

    chain = ",".join([format_event(event) for event in event_chain.events])
    return "".join(
        [
            f"addEvents([{chain}]",
            f", {format_var(event_arg)}" if event_arg else "",
            ")",
        ]
    )


def format_query_params(router_data: dict[str, Any]) -> dict[str, str]:
    """Convert back query params name to python-friendly case.

    Args:
        router_data: the router_data dict containing the query params

    Returns:
        The reformatted query params
    """
    params = router_data[constants.RouteVar.QUERY]
    return {k.replace("-", "_"): v for k, v in params.items()}


def format_state(value: Any) -> Any:
    """Recursively format values in the given state.

    Args:
        value: The state to format.

    Returns:
        The formatted state.

    Raises:
        TypeError: If the given value is not a valid state.
    """
    # Handle dicts.
    if isinstance(value, dict):
        return {k: format_state(v) for k, v in value.items()}

    # Handle lists, sets, typles.
    if isinstance(value, types.StateIterBases):
        return [format_state(v) for v in value]

    # Return state vars as is.
    if isinstance(value, types.StateBases):
        return value

    # Serialize the value.
    serialized = serialize(value)
    if serialized is not None:
        return serialized

    raise TypeError(f"No JSON serializer found for var {value} of type {type(value)}.")


def format_state_name(state_name: str) -> str:
    """Format a state name, replacing dots with double underscore.

    This allows individual substates to be accessed independently as javascript vars
    without using dot notation.

    Args:
        state_name: The state name to format.

    Returns:
        The formatted state name.
    """
    return state_name.replace(".", "__")


def format_ref(ref: str) -> str:
    """Format a ref.

    Args:
        ref: The ref to format.

    Returns:
        The formatted ref.
    """
    # Replace all non-word characters with underscores.
    clean_ref = re.sub(r"[^\w]+", "_", ref)
    return f"ref_{clean_ref}"


def format_array_ref(refs: str, idx: Var | None) -> str:
    """Format a ref accessed by array.

    Args:
        refs : The ref array to access.
        idx : The index of the ref in the array.

    Returns:
        The formatted ref.
    """
    clean_ref = re.sub(r"[^\w]+", "_", refs)
    if idx is not None:
        idx._var_is_local = True
        return f"refs_{clean_ref}[{idx}]"
    return f"refs_{clean_ref}"


def format_breadcrumbs(route: str) -> list[tuple[str, str]]:
    """Take a route and return a list of tuple for use in breadcrumb.

    Args:
        route: The route to transform.

    Returns:
        list[tuple[str, str]]: the list of tuples for the breadcrumb.
    """
    route_parts = route.lstrip("/").split("/")

    # create and return breadcrumbs
    return [
        (part, "/".join(["", *route_parts[: i + 1]]))
        for i, part in enumerate(route_parts)
    ]


def format_library_name(library_fullname: str):
    """Format the name of a library.

    Args:
        library_fullname: The fullname of the library.

    Returns:
        The name without the @version if it was part of the name
    """
    lib, at, version = library_fullname.rpartition("@")
    if not lib:
        lib = at + version

    return lib


def json_dumps(obj: Any) -> str:
    """Takes an object and returns a jsonified string.

    Args:
        obj: The object to be serialized.

    Returns:
        A string
    """
    return json.dumps(obj, ensure_ascii=False, default=serialize)


def unwrap_vars(value: str) -> str:
    """Unwrap var values from a JSON string.

    For example, "{var}" will be unwrapped to "var".

    Args:
        value: The JSON string to unwrap.

    Returns:
        The unwrapped JSON string.
    """

    def unescape_double_quotes_in_var(m: re.Match) -> str:
        prefix = m.group(1) or ""
        # Since the outer quotes are removed, the inner escaped quotes must be unescaped.
        return prefix + re.sub('\\\\"', '"', m.group(2))

    # This substitution is necessary to unwrap var values.
    return (
        re.sub(
            pattern=r"""
            (?<!\\)      # must NOT start with a backslash
            "            # match opening double quote of JSON value
            (<reflex.Var>.*?</reflex.Var>)?  # Optional encoded VarData (non-greedy)
            {(.*?)}      # extract the value between curly braces (non-greedy)
            "            # match must end with an unescaped double quote
        """,
            repl=unescape_double_quotes_in_var,
            string=value,
            flags=re.VERBOSE,
        )
        .replace('"`', "`")
        .replace('`"', "`")
    )


def collect_form_dict_names(form_dict: dict[str, Any]) -> dict[str, Any]:
    """Collapse keys with consecutive suffixes into a single list value.

    Separators dash and underscore are removed, unless this would overwrite an existing key.

    Args:
        form_dict: The dict to collapse.

    Returns:
        The collapsed dict.
    """
    ending_digit_regex = re.compile(r"^(.*?)[_-]?(\d+)$")
    collapsed = {}
    for k in sorted(form_dict):
        m = ending_digit_regex.match(k)
        if m:
            collapsed.setdefault(m.group(1), []).append(form_dict[k])
    # collapsing never overwrites valid data from the form_dict
    collapsed.update(form_dict)
    return collapsed


def format_data_editor_column(col: str | dict):
    """Format a given column into the proper format.

    Args:
        col: The column.

    Raises:
        ValueError: invalid type provided for column.

    Returns:
        The formatted column.
    """
    if isinstance(col, str):
        return {"title": col, "id": col.lower(), "type": "str"}

    if isinstance(col, (dict,)):
        if "id" not in col:
            col["id"] = col["title"].lower()
        if "type" not in col:
            col["type"] = "str"
        if "overlayIcon" not in col:
            col["overlayIcon"] = None
        return col

    if isinstance(col, BaseVar):
        return col

    raise ValueError(
        f"unexpected type ({(type(col).__name__)}: {col}) for column header in data_editor"
    )


def format_data_editor_cell(cell: Any):
    """Format a given data into a renderable cell for data_editor.

    Args:
        cell: The data to format.

    Returns:
        The formatted cell.
    """
    return {"kind": Var.create(value="GridCellKind.Text"), "data": cell}
