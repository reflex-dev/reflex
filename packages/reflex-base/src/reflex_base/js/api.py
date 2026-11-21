"""Build calls on ``reflex``, the API browser code reaches Reflex through.

The frontend defines ``reflex`` in ``utils/reflex.js``. Each function here
returns a Var that renders as a call on it, such as ``reflex.ref("search")``.
A page that uses one imports ``reflex``, and code ``rx.run_script`` sends from
the backend has ``reflex`` in scope, so the same Var works in both.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from reflex_base.constants.base import Dirs
from reflex_base.event import (
    EventCallback,
    EventHandler,
    EventSpec,
    call_event_handler,
    no_args_event_spec,
)
from reflex_base.utils.exceptions import EventFnArgMismatchError
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData
from reflex_base.vars.function import FunctionVar
from reflex_base.vars.object import ObjectVar

__all__ = ["add_events", "library", "ref"]

_REFLEX_VAR_DATA = VarData(
    imports={f"$/{Dirs.REFLEX_API_PATH}": [ImportVar(tag="reflex")]}
)


def _call(member: str, *args: Any) -> Var:
    """Call a member of ``reflex``.

    Args:
        member: The member's name.
        *args: The arguments to call it with.

    Returns:
        The call.
    """
    return (
        Var(_js_expr=f"reflex.{member}", _var_data=_REFLEX_VAR_DATA)
        .to(FunctionVar)
        .call(*args)
    )


def _event_spec(event: EventSpec | EventHandler | EventCallback[()]) -> EventSpec:
    """Build the event ``add_events`` dispatches for a handler or an event.

    Args:
        event: The event, or a handler that takes no arguments.

    Returns:
        The event.

    Raises:
        EventFnArgMismatchError: If the handler needs arguments it was not given.
    """
    try:
        return call_event_handler(
            cast("EventSpec | EventHandler", event), no_args_event_spec
        )
    except EventFnArgMismatchError as err:
        handler = event.handler if isinstance(event, EventSpec) else event
        name = handler.fn.__qualname__
        msg = (
            f"rx.js.add_events cannot dispatch {name}: the handler needs "
            "arguments, and add_events has none to pass it. Pass them where you "
            f"add it, as in rx.js.add_events({name}(...))."
        )
        raise EventFnArgMismatchError(msg) from err


def ref(id: str | Var[str]) -> ObjectVar[Mapping[str, Mapping[str, Any]]]:
    """Get the ref of a component by its id.

    Args:
        id: The component's id.

    Returns:
        The ref, whose ``current`` is the mounted element, or undefined if no
        component with that id has mounted.
    """
    return _call("ref", id).to(ObjectVar, Mapping[str, Mapping[str, Any]])


def add_events(*events: EventSpec | EventHandler | EventCallback[()]) -> Var:
    """Dispatch events through the event loop, as event triggers do.

    Args:
        *events: The events, or handlers that take no arguments.

    Returns:
        The dispatch call.
    """
    return _call(
        "addEvents", LiteralVar.create([_event_spec(event) for event in events])
    )


def library(name: str | Var[str]) -> Var:
    """Get an npm library bundled for dynamic components.

    Args:
        name: The library's import name, e.g. ``"react"``.

    Returns:
        A promise of the library's module namespace.
    """
    return _call("library", name)
