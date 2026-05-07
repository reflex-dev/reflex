"""Handle client side state with `useState`."""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable
from typing import Any

from reflex_base import constants
from reflex_base.event import EventChain, EventHandler, EventSpec, run_script
from reflex_base.utils.imports import ImportVar
from reflex_base.vars import VarData, get_unique_variable_name
from reflex_base.vars.base import LiteralVar, Var
from reflex_base.vars.function import ArgsFunctionOperationBuilder, FunctionVar

NoValue = object()


_refs_import = {
    f"$/{constants.Dirs.STATE_PATH}": [ImportVar(tag="refs")],
}


def _client_state_ref(var_name: str) -> Var:
    """Get the ref accessor Var for a ClientStateVar.

    Args:
        var_name: The name of the variable.

    Returns:
        A Var that accesses the ClientStateVar ref slot, carrying the
        ``refs`` import from ``$/utils/state``.
    """
    return Var(
        _js_expr=f"refs['_client_state_{var_name}']",
        _var_data=VarData(imports=_refs_import),
    )


def _client_state_ref_dict(var_name: str) -> Var:
    """Get the per-instance ref-dict accessor Var for a ClientStateVar.

    Args:
        var_name: The name of the variable.

    Returns:
        A Var that accesses the ClientStateVar's per-instance ref dict,
        carrying the ``refs`` import from ``$/utils/state``.
    """
    return Var(
        _js_expr=f"refs['_client_state_dict_{var_name}']",
        _var_data=VarData(imports=_refs_import),
    )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class ClientStateVar(Var):
    """A Var that exists on the client via useState."""

    # Track the names of the getters and setters
    _setter_name: str = dataclasses.field(default="")
    _getter_name: str = dataclasses.field(default="")
    _id_name: str = dataclasses.field(default="")

    # Whether to add the var and setter to the global `refs` object for use in any Component.
    _global_ref: bool = dataclasses.field(default=True)

    def __hash__(self) -> int:
        """Define a hash function for a var.

        Returns:
            The hash of the var.
        """
        return hash((
            self._js_expr,
            str(self._var_type),
            self._getter_name,
            self._setter_name,
        ))

    @classmethod
    def create(
        cls,
        var_name: str | None = None,
        default: Any = NoValue,
        global_ref: bool = True,
    ) -> ClientStateVar:
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

        Raises:
            ValueError: If the var_name is not a string.
        """
        if var_name is None:
            var_name = get_unique_variable_name()
        id_name = "id_" + get_unique_variable_name()
        if not isinstance(var_name, str):
            msg = "var_name must be a string."
            raise ValueError(msg)
        if default is NoValue:
            default_var = Var(_js_expr="")
        elif not isinstance(default, Var):
            default_var = LiteralVar.create(default)
        else:
            default_var = default
        setter_name = f"set{var_name.capitalize()}"
        hooks: dict[str, VarData | None] = {
            f"const {id_name} = useId()": None,
            f"const [{var_name}, {setter_name}] = useState({default_var!s})": None,
        }
        imports = {
            "react": [ImportVar(tag="useState"), ImportVar(tag="useId")],
        }
        if global_ref:
            arg_name = get_unique_variable_name()
            setter_ref = _client_state_ref(setter_name)
            var_ref = _client_state_ref(var_name)
            var_dict_ref = _client_state_ref_dict(var_name)
            setter_dict_ref = _client_state_ref_dict(setter_name)
            func = ArgsFunctionOperationBuilder.create(
                args_names=(arg_name,),
                return_expr=Var("Array.prototype.forEach.call")
                .to(FunctionVar)
                .call(
                    (
                        Var("Object.values")
                        .to(FunctionVar)
                        .call(setter_dict_ref)
                        .to(list)
                        .to(list)
                    )
                    + Var.create([Var(f"(value) => {{ {var_ref} = value; }}")]).to(
                        list
                    ),
                    ArgsFunctionOperationBuilder.create(
                        args_names=("setter",),
                        return_expr=Var("setter").to(FunctionVar).call(Var(arg_name)),
                    ),
                ),
            )

            hooks[f"{setter_ref!s} = {func!s}"] = setter_ref._get_all_var_data()
            hooks[f"{var_ref!s} ??= {var_name!s}"] = var_ref._get_all_var_data()
            hooks[f"{var_dict_ref!s} ??= {{}}"] = var_dict_ref._get_all_var_data()
            hooks[f"{setter_dict_ref!s} ??= {{}}"] = setter_dict_ref._get_all_var_data()
            hooks[f"{var_dict_ref!s}[{id_name}] = {var_ref!s}"] = VarData.merge(
                var_dict_ref._get_all_var_data(), var_ref._get_all_var_data()
            )
            hooks[f"{setter_dict_ref!s}[{id_name}] = {setter_name}"] = (
                setter_dict_ref._get_all_var_data()
            )
        return cls(
            _js_expr="null",
            _setter_name=setter_name,
            _getter_name=var_name,
            _id_name=id_name,
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
        js_expr = (
            f"{_client_state_ref_dict(self._getter_name)}[{self._id_name}]"
            if self._global_ref
            else self._getter_name
        )
        return Var(_js_expr=js_expr, _var_data=self._var_data).to(self._var_type)

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
            else Var(self._setter_name)
        ).to(FunctionVar)

        if value is not NoValue:
            # This is a hack to make it work like an EventSpec taking an arg
            value_var = LiteralVar.create(value)
            value_str = str(value_var)

            setter = ArgsFunctionOperationBuilder.create(
                # remove patterns of ["*"] from the value_str using regex
                args_names=(re.sub(r"(\?\.)?\[\".*\"\]", "", value_str),)
                if value_str.startswith("_")
                else (),
                return_expr=setter.call(value_var),
            )

        return setter.to(FunctionVar, EventChain)

    @property
    def set(self) -> Var:
        """Set the value of the client state variable.

        This property can only be attached to a frontend event trigger.

        To set a value from a backend event handler, see `push`.

        Returns:
            A special EventChain Var which will set the value when triggered.
        """
        return self.set_value()

    def retrieve(self, callback: EventHandler | Callable | None = None) -> EventSpec:
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
            msg = "ClientStateVar must be global to retrieve the value."
            raise ValueError(msg)
        return run_script(_client_state_ref(self._getter_name), callback=callback)

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
            msg = "ClientStateVar must be global to push the value."
            raise ValueError(msg)
        value = Var.create(value)
        return run_script(f"{_client_state_ref(self._setter_name)}({value})")
