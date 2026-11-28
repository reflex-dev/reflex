"""How a component reaches the functions of a behaviour script."""

from __future__ import annotations

import functools
from typing import Any

from reflex_base.components.tags import CommonTag
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData

from reflex_components_ui.constants import WEB_DIR


@functools.cache
def script(module: str, name: str) -> Var:
    """Name a function of a behaviour script.

    Args:
        module: The name of the script, without its extension.
        name: The name the script exports the function under.

    Returns:
        The function, with its import: a page that does not render it does
        not load the script.
    """
    return Var(
        name,
        _var_data=VarData(
            imports={f"$/{WEB_DIR}/behaviors/{module}.js": [ImportVar(tag=name)]}
        ),
    )


def handlers(tag: CommonTag, events: dict[str, str]) -> tuple[CommonTag, Var | None]:
    """Take the event handlers a script calls off a rendered element.

    Args:
        tag: The rendered element.
        events: The name the script knows each event by, by the prop the
            event is rendered as.

    Returns:
        The tag without those props, and the handlers that were among them
        as one object, or None when there was none.
    """
    rendered = dict(tag.props)
    found = {
        name: LiteralVar.create(rendered.pop(event))
        for event, name in events.items()
        if event in rendered
    }
    if not found:
        return tag, None
    return tag.set(props=rendered), Var(
        "({ "
        + ", ".join([f"{name}: {handler!s}" for name, handler in found.items()])
        + " })",
        _var_data=VarData.merge(
            *(handler._get_all_var_data() for handler in found.values())
        ),
    )


def listen(
    tag: CommonTag, function: Var, *events: str, arguments: Any = ()
) -> CommonTag:
    """Have a function of a script hear events of a rendered element.

    Args:
        tag: The rendered element.
        function: The function of the script.
        *events: The props the events are rendered as, such as ``onClick``.
        arguments: What the function is called with after the event.

    Returns:
        The tag. A handler the element already has for an event is called
        after the script.
    """
    arguments = [LiteralVar.create(argument) for argument in arguments]
    data = [argument._get_all_var_data() for argument in arguments]
    if arguments:
        passed = ", ".join(str(argument) for argument in arguments)
        function = Var(
            f"((event) => {function!s}(event, {passed}))",
            _var_data=VarData.merge(function._get_all_var_data(), *data),
        )
    props = {}
    for event in events:
        own = tag.props.get(event)
        if own is None:
            props[event] = function
            continue
        own = LiteralVar.create(own)
        props[event] = Var(
            f"((event) => {{ ({function!s})(event); ({own!s})(event); }})",
            _var_data=VarData.merge(
                function._get_all_var_data(), own._get_all_var_data()
            ),
        )
    return tag.add_props(**props)
