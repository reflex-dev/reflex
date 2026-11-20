"""The script environment as a Var: the API browser code reaches Reflex through.

The frontend defines it in ``utils/script_env.js``. ``rx.call_script`` code
sees it as ``env``, a JavaScript module imports it as ``env``, and Python
builds expressions on it through ``rx.js.env``. A Var renders under the alias
``__reflexEnv``, which ``rx.call_script`` code also sees, so one expression
works compiled into a page and sent from the backend, and cannot collide with
the ``env`` a page imports from ``env.json``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from reflex_base.constants.base import Dirs
from reflex_base.event import EventCallback, EventHandler, EventSpec
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData
from reflex_base.vars.function import FunctionVar
from reflex_base.vars.object import ObjectVar

# The name a Var renders the environment under.
_ALIAS = "__reflexEnv"


class ScriptEnvVar(ObjectVar[Mapping[str, Any]]):
    """The script environment, for building browser code in Python."""

    def _function(self, name: str) -> FunctionVar:
        """Get one of the environment's functions.

        Args:
            name: The member name.

        Returns:
            The function.
        """
        return Var(
            _js_expr=f"{self._js_expr}.{name}",
            _var_data=self._get_all_var_data(),
        ).to(FunctionVar)

    @property
    def refs(self) -> ObjectVar[Mapping[str, Any]]:
        """Every registered component ref, by registry key (``ref_<id>``).

        Returns:
            The ref registry.
        """
        return Var(
            _js_expr=f"{self._js_expr}.refs",
            _var_data=self._get_all_var_data(),
        ).to(dict)

    def ref(self, id: str | Var[str]) -> ObjectVar[Mapping[str, Any]]:
        """Get the ref of a component by its id.

        Args:
            id: The component id.

        Returns:
            The ref, whose ``current`` is the mounted element, or undefined if
            no component with that id has mounted.
        """
        return self._function("ref").call(id).to(dict)

    def add_events(self, *events: EventSpec | EventHandler | EventCallback[()]) -> Var:
        """Dispatch events through the event loop, as event triggers do.

        Args:
            *events: The events, or handlers that take no arguments.

        Returns:
            The dispatch call.
        """
        return self._function("addEvents").call(
            LiteralVar.create([
                event if isinstance(event, EventSpec) else event() for event in events
            ])
        )

    def library(self, name: str | Var[str]) -> Var:
        """Get a library bundled for dynamic components.

        Args:
            name: The library's import name, e.g. ``"react"``.

        Returns:
            A promise of the library's module namespace.
        """
        return self._function("library").call(name)


env = ScriptEnvVar(
    _js_expr=_ALIAS,
    _var_type=Mapping[str, Any],
    _var_data=VarData(
        imports={f"$/{Dirs.SCRIPT_ENV_PATH}": [ImportVar(tag="env", alias=_ALIAS)]}
    ),
)
