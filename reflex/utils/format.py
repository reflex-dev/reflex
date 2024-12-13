"""Formatting operations."""

from __future__ import annotations

import inspect
import json
import os
import re
from typing import TYPE_CHECKING, Any, List, Optional, Union

from reflex import constants
from reflex.constants.state import FRONTEND_EVENT_STATE
from reflex.utils import exceptions
from reflex.utils.console import deprecate

if TYPE_CHECKING:
    from reflex.components.component import ComponentStyle
    from reflex.event import ArgsSpec, EventChain, EventHandler, EventSpec, EventType

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


def to_title_case(text: str, sep: str = "") -> str:
    """Convert a string from snake case to title case.

    Args:
        text: The string to convert.
        sep: The separator to use to join the words.

    Returns:
        The title case string.
    """
    return sep.join(word.title() for word in text.split("_"))


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


def make_default_page_title(app_name: str, route: str) -> str:
    """Make a default page title from a route.

    Args:
        app_name: The name of the app owning the page.
        route: The route to make the title from.

    Returns:
        The default page title.
    """
    route_parts = [
        part
        for part in route.split("/")
        if part and not (part.startswith("[") and part.endswith("]"))
    ]

    title = constants.DefaultPage.TITLE.format(
        app_name, route_parts[-1] if route_parts else constants.PageNames.INDEX_ROUTE
    )
    return to_title_case(title)


def _escape_js_string(string: str) -> str:
    """Escape the string for use as a JS string literal.

    Args:
        string: The string to escape.

    Returns:
        The escaped string.
    """

    # TODO: we may need to re-vist this logic after new Var API is implemented.
    def escape_outside_segments(segment):
        """Escape backticks in segments outside of `${}`.

        Args:
            segment: The part of the string to escape.

        Returns:
            The escaped or unescaped segment.
        """
        if segment.startswith("${") and segment.endswith("}"):
            # Return the `${}` segment unchanged
            return segment
        else:
            # Escape backticks in the segment
            segment = segment.replace(r"\`", "`")
            segment = segment.replace("`", r"\`")
            return segment

    # Split the string into parts, keeping the `${}` segments
    parts = re.split(r"(\$\{.*?\})", string)
    escaped_parts = [escape_outside_segments(part) for part in parts]
    escaped_string = "".join(escaped_parts)
    return escaped_string


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


def format_var(var: Var) -> str:
    """Format the given Var as a javascript value.

    Args:
        var: The Var to format.

    Returns:
        The formatted Var.
    """
    return str(var)


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


def format_match(
    cond: str | Var,
    match_cases: List[List[Var]],
    default: Var,
) -> str:
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
            [f"case JSON.stringify({condition!s}):" for condition in conditions]
        )
        case_code = f"{case_conditions}  return ({return_value!s});  break;"
        switch_code += case_code

    switch_code += f"default:  return ({default!s});  break;"
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
        ValueError: If the prop is not a string.
    """
    # import here to avoid circular import.
    from reflex.event import EventChain
    from reflex.utils import serializers
    from reflex.vars import Var

    try:
        # Handle var props.
        if isinstance(prop, Var):
            return str(prop)

        # Handle event props.
        if isinstance(prop, EventChain):
            return str(Var.create(prop))

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
    if not isinstance(prop, str):
        raise ValueError(f"Invalid prop: {prop}. Expected a string.")
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
    from reflex.vars.base import LiteralVar, Var

    return [
        (
            f"{name}={{{format_prop(prop if isinstance(prop, Var) else LiteralVar.create(prop))}}}"
        )
        for name, prop in sorted(key_value_props.items())
        if prop is not None
    ] + [(f"{LiteralVar.create(prop)!s}") for prop in single_props]


def get_event_handler_parts(handler: EventHandler) -> tuple[str, str]:
    """Get the state and function name of an event handler.

    Args:
        handler: The event handler to get the parts of.

    Returns:
        The state and function name.
    """
    # Get the class that defines the event handler.
    parts = handler.fn.__qualname__.split(".")

    # Get the state full name
    state_full_name = handler.state_full_name

    # If there's no enclosing class, just return the function name.
    if not state_full_name:
        return ("", parts[-1])

    # Get the function name
    name = parts[-1]

    from reflex.state import State

    if state_full_name == FRONTEND_EVENT_STATE and name not in State.__dict__:
        return ("", to_snake_case(handler.fn.__qualname__))

    return (state_full_name, name)


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
                    name._js_expr,
                    (
                        wrap(
                            json.dumps(val._js_expr).strip('"').replace("`", "\\`"),
                            "`",
                        )
                        if val._var_is_string
                        else str(val)
                    ),
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


if TYPE_CHECKING:
    from reflex.vars import Var


def format_event_chain(
    event_chain: EventChain | Var[EventChain],
    event_arg: Var | None = None,
) -> str:
    """DEPRECATED: format an event chain as a javascript invocation.

    Use str(rx.Var.create(event_chain)) instead.

    Args:
        event_chain: The event chain to format.
        event_arg: this argument is ignored.

    Returns:
        Compiled javascript code to queue the given event chain on the frontend.
    """
    deprecate(
        feature_name="format_event_chain",
        reason="Use str(rx.Var.create(event_chain)) instead",
        deprecation_version="0.6.0",
        removal_version="0.7.0",
    )

    from reflex.vars import Var
    from reflex.vars.function import ArgsFunctionOperation

    result = Var.create(event_chain)
    if isinstance(result, ArgsFunctionOperation):
        result = result._return_expr
    return str(result)


def format_queue_events(
    events: EventType | None = None,
    args_spec: Optional[ArgsSpec] = None,
) -> Var[EventChain]:
    """Format a list of event handler / event spec as a javascript callback.

    The resulting code can be passed to interfaces that expect a callback
    function and when triggered it will directly call queueEvents.

    It is intended to be executed in the rx.call_script context, where some
    existing API needs a callback to trigger a backend event handler.

    Args:
        events: The events to queue.
        args_spec: The argument spec for the callback.

    Returns:
        The compiled javascript callback to queue the given events on the frontend.

    Raises:
        ValueError: If a lambda function is given which returns a Var.
    """
    from reflex.event import (
        EventChain,
        EventHandler,
        EventSpec,
        call_event_fn,
        call_event_handler,
    )
    from reflex.vars import FunctionVar, Var

    if not events:
        return Var("(() => null)").to(FunctionVar, EventChain)  # type: ignore

    # If no spec is provided, the function will take no arguments.
    def _default_args_spec():
        return []

    # Construct the arguments that the function accepts.
    sig = inspect.signature(args_spec or _default_args_spec)  # type: ignore
    if sig.parameters:
        arg_def = ",".join(f"_{p}" for p in sig.parameters)
        arg_def = f"({arg_def})"
    else:
        arg_def = "()"

    payloads = []
    if not isinstance(events, list):
        events = [events]

    # Process each event/spec/lambda (similar to Component._create_event_chain).
    for spec in events:
        specs: list[EventSpec] = []
        if isinstance(spec, (EventHandler, EventSpec)):
            specs = [call_event_handler(spec, args_spec or _default_args_spec)]
        elif isinstance(spec, type(lambda: None)):
            specs = call_event_fn(spec, args_spec or _default_args_spec)  # type: ignore
            if isinstance(specs, Var):
                raise ValueError(
                    f"Invalid event spec: {specs}. Expected a list of EventSpecs."
                )
        payloads.extend(format_event(s) for s in specs)

    # Return the final code snippet, expecting queueEvents, processEvent, and socket to be in scope.
    # Typically this snippet will _only_ run from within an rx.call_script eval context.
    return Var(
        f"{arg_def} => {{queueEvents([{','.join(payloads)}], {constants.CompileVars.SOCKET}); "
        f"processEvent({constants.CompileVars.SOCKET})}}",
    ).to(FunctionVar, EventChain)  # type: ignore


def format_query_params(router_data: dict[str, Any]) -> dict[str, str]:
    """Convert back query params name to python-friendly case.

    Args:
        router_data: the router_data dict containing the query params

    Returns:
        The reformatted query params
    """
    params = router_data[constants.RouteVar.QUERY]
    return {k.replace("-", "_"): v for k, v in params.items()}


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


def format_library_name(library_fullname: str):
    """Format the name of a library.

    Args:
        library_fullname: The fullname of the library.

    Returns:
        The name without the @version if it was part of the name
    """
    if library_fullname.startswith("https://"):
        return library_fullname
    lib, at, version = library_fullname.rpartition("@")
    if not lib:
        lib = at + version

    return lib


def json_dumps(obj: Any, **kwargs) -> str:
    """Takes an object and returns a jsonified string.

    Args:
        obj: The object to be serialized.
        kwargs: Additional keyword arguments to pass to json.dumps.

    Returns:
        A string
    """
    from reflex.utils import serializers

    kwargs.setdefault("ensure_ascii", False)
    kwargs.setdefault("default", serializers.serialize)

    return json.dumps(obj, **kwargs)


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
        return f"refs_{clean_ref}[{idx!s}]"
    return f"refs_{clean_ref}"


def format_data_editor_column(col: str | dict):
    """Format a given column into the proper format.

    Args:
        col: The column.

    Raises:
        ValueError: invalid type provided for column.

    Returns:
        The formatted column.
    """
    from reflex.vars import Var

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

    if isinstance(col, Var):
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
    from reflex.vars.base import Var

    return {
        "kind": Var(_js_expr="GridCellKind.Text"),
        "data": cell,
    }
