"""Build calls on ``reflex``, the API browser code reaches Reflex through.

The frontend defines ``reflex`` in ``utils/reflex.js``. Each function here
returns a Var that renders as a call on it, such as ``reflex.ref("search")``.
A page that uses one imports ``reflex``, and code ``rx.run_script`` sends from
the backend has ``reflex`` in scope, so the same Var works in both.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from reflex_base.constants.base import Dirs
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData
from reflex_base.vars.function import FunctionVar
from reflex_base.vars.object import ObjectVar

__all__ = ["ref"]

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


def ref(id: str | Var[str]) -> ObjectVar[Mapping[str, Mapping[str, Any]]]:
    """Get the ref of a component by its id.

    Args:
        id: The component's id.

    Returns:
        The ref, whose ``current`` is the mounted element, or undefined if no
        component with that id has mounted or the component's id is a Var,
        which registers no ref.
    """
    return _call("ref", id).to(ObjectVar, Mapping[str, Mapping[str, Any]])
