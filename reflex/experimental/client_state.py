"""Handle client side state with `useState`."""

from __future__ import annotations

import dataclasses
import sys
from typing import Any, Callable, Union

from reflex import constants
from reflex.event import EventChain, EventHandler, EventSpec, call_script
from reflex.utils.imports import ImportVar
from reflex.vars import (
    VarData,
    get_unique_variable_name,
)
from reflex.vars.base import LiteralVar, Var
from reflex.vars.function import FunctionVar

NoValue = object()


_refs_import = {
    f"/{constants.Dirs.STATE_PATH}": [ImportVar(tag="refs")],
}


def _client_state_ref(var_name: str) -> str:
    """Get the ref path for a ClientStateVar.

    Args:
        var_name: The name of the variable.

    Returns:
        An accessor for ClientStateVar ref as a string.
    """
    return f"refs['_client_state_{var_name}']"


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ClientStateVar(Var):
    """A Var that exists on the client via useState."""

    # Track the names of the getters and setters
    _setter_name: str = dataclasses.field(default="")
    _getter_name: str = dataclasses.field(default="")

    # Whether to add the var and setter to the global `refs` object for use in any Component.
    _global_ref: bool = dataclasses.field(default=True)

    def __hash__(self) -> int:
        """Define a hash function for a var.

        Returns:
            The hash of the var.
        """
        return hash(
            (self._js_expr, str(self._var_type), self._getter_name, self._setter_name)
        )

    @classmethod
    def create(
        cls,
        var_name: str | None = None,
        default: Any = NoValue,
        global_ref: bool = True,
    ) -> "ClientStateVar":
        """Create a local_state Var that can be accessed and updated on the client.

        The `ClientStateVar` should be included in the highest parent component
        that contains the components which will access and manipulate the client
        state. It has no visual rendering, including it ensures that the
        `useState` hook is called in the correct scope.

        To render the var in a component, use the `value` property.

        To update the var in a component, use the `set` property or `set_value` method.

        To access the var in an event handler, use the `retrieve` method with
        `callback` set to the event handler which should receive the value.

        To update the var in an event handler, use the `push` method with the
        value to update.

        Args:
            var_name: The name of the variable.
            default: The default value of the variable.
            global_ref: Whether the state should be accessible in any Component and on the backend.

        Returns:
            ClientStateVar
        """
        if var_name is None:
            var_name = get_unique_variable_name()
        assert isinstance(var_name, str), "var_name must be a string."
        if default is NoValue:
            default_var = Var(_js_expr="")
        elif not isinstance(default, Var):
            default_var = LiteralVar.create(default)
        else:
            default_var = default
        setter_name = f"set{var_name.capitalize()}"
        hooks = {
            f"const [{var_name}, {setter_name}] = useState({str(default_var)})": None,
        }
        imports = {
            "react": [ImportVar(tag="useState")],
        }
        if global_ref:
            hooks[f"{_client_state_ref(var_name)} = {var_name}"] = None
            hooks[f"{_client_state_ref(setter_name)} = {setter_name}"] = None
            imports.update(_refs_import)
        return cls(
            _js_expr="",
            _setter_name=setter_name,
            _getter_name=var_name,
            _global_ref=global_ref,
            _var_type=default_var._var_type,
            _var_data=VarData.merge(
                default_var._var_data,
                VarData(
                    hooks=hooks,
                    imports=imports,
                ),
            ),
        )

    @property
    def value(self) -> Var:
        """Get a placeholder for the Var.

        This property can only be rendered on the frontend.

        To access the value in a backend event handler, see `retrieve`.

        Returns:
            an accessor for the client state variable.
        """
        return (
            Var(
                _js_expr=(
                    _client_state_ref(self._getter_name)
                    if self._global_ref
                    else self._getter_name
                )
            )
            .to(self._var_type)
            ._replace(
                merge_var_data=VarData(  # type: ignore
                    imports=_refs_import if self._global_ref else {}
                )
            )
        )

    def set_value(self, value: Any = NoValue) -> Var:
        """Set the value of the client state variable.

        This property can only be attached to a frontend event trigger.

        To set a value from a backend event handler, see `push`.

        Args:
            value: The value to set.

        Returns:
            A special EventChain Var which will set the value when triggered.
        """
        setter = (
            _client_state_ref(self._setter_name)
            if self._global_ref
            else self._setter_name
        )
        if value is not NoValue:
            import re

            # This is a hack to make it work like an EventSpec taking an arg
            value_str = str(LiteralVar.create(value))

            # remove patterns of ["*"] from the value_str using regex
            arg = re.sub(r"\[\".*\"\]", "", value_str)

            setter = f"({arg}) => {setter}({str(value)})"
        return Var(
            _js_expr=setter,
            _var_data=VarData(imports=_refs_import if self._global_ref else {}),
        ).to(FunctionVar, EventChain)

    @property
    def set(self) -> Var:
        """Set the value of the client state variable.

        This property can only be attached to a frontend event trigger.

        To set a value from a backend event handler, see `push`.

        Returns:
            A special EventChain Var which will set the value when triggered.
        """
        return self.set_value()

    def retrieve(
        self, callback: Union[EventHandler, Callable, None] = None
    ) -> EventSpec:
        """Pass the value of the client state variable to a backend EventHandler.

        The event handler must `yield` or `return` the EventSpec to trigger the event.

        Args:
            callback: The callback to pass the value to.

        Returns:
            An EventSpec which will retrieve the value when triggered.

        Raises:
            ValueError: If the ClientStateVar is not global.
        """
        if not self._global_ref:
            raise ValueError("ClientStateVar must be global to retrieve the value.")
        return call_script(_client_state_ref(self._getter_name), callback=callback)

    def push(self, value: Any) -> EventSpec:
        """Push a value to the client state variable from the backend.

        The event handler must `yield` or `return` the EventSpec to trigger the event.

        Args:
            value: The value to update.

        Returns:
            An EventSpec which will push the value when triggered.

        Raises:
            ValueError: If the ClientStateVar is not global.
        """
        if not self._global_ref:
            raise ValueError("ClientStateVar must be global to push the value.")
        return call_script(f"{_client_state_ref(self._setter_name)}({value})")
