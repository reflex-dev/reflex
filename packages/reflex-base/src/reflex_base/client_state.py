"""Handle client side state with `useClientState`."""

from __future__ import annotations

import dataclasses
import inspect
import itertools
import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from reflex_base.components.client_state_context import get_client_state_app_wraps
from reflex_base.constants import Dirs
from reflex_base.constants.state import (
    CAMEL_CASE_CLIENT_STATE_MARKER,
    CAMEL_CASE_MEMO_MARKER,
    FIELD_MARKER,
)
from reflex_base.event import (
    EventChain,
    EventHandler,
    EventSpec,
    run_script,
    server_side,
)
from reflex_base.utils import console, format
from reflex_base.utils.exceptions import VarTypeError
from reflex_base.utils.imports import ImportVar
from reflex_base.vars import VarData
from reflex_base.vars.base import LiteralVar, Var
from reflex_base.vars.function import ArgsFunctionOperationBuilder, FunctionVar

if TYPE_CHECKING:
    from typing_extensions import deprecated

NoValue = object()

_CLIENT_STATE_IMPORT = {
    f"$/{Dirs.CLIENT_STATE_PATH}": [ImportVar(tag="useClientState")],
}
_CLIENT_STATE_ESCAPE_IMPORT = {
    f"$/{Dirs.CLIENT_STATE_PATH}": [
        ImportVar(tag="getClientState"),
        ImportVar(tag="setClientState"),
    ],
}

# Generated names come from a dedicated counter rather than
# `get_unique_variable_name`, which draws from a process-wide generator shared
# with every other consumer -- so an unrelated `ArrayVar.map` would shift every
# subsequent client state name. This keeps a name dependent only on how many
# client state vars were created before it.
_name_counter = itertools.count()

# Separate from _name_counter so tracing a lambda updater never shifts the
# generated var-name sequence.
_placeholder_counter = itertools.count()

_VALID_NAME = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")

# The store's entry point on the global `refs` object. This is the only binding
# reachable from the scope `run_script` code is evaluated in, and doubles as the
# devtools handle for inspecting client state. Must match CLIENT_STATE_REF in
# `$/utils/client_state`.
_client_state_store_ref = Var(
    _js_expr='refs["__client_state"]',
    _var_data=VarData(
        imports={f"$/{Dirs.STATE_PATH}": [ImportVar(tag="refs")]},
    ),
)

# Reflex marks every identifier it puts in scope; an unmarked `_`-leading name is
# an event-arg placeholder from `parse_args_spec`.
_IN_SCOPE_MARKERS = (
    CAMEL_CASE_CLIENT_STATE_MARKER,
    CAMEL_CASE_MEMO_MARKER,
    FIELD_MARKER,
)
_LEADING_EVENT_ARG = re.compile(r"^_[A-Za-z0-9_$]*")


def _recovered_event_arg(value_str: str) -> str | None:
    """Get the event-arg parameter an emitted setter wrapper must declare.

    A value bound into a setter may reference the event args of the trigger it is
    attached to, in which case the wrapper has to declare them or they are
    unbound when it fires.

    Args:
        value_str: The rendered value expression.

    Returns:
        The parameter name to declare, or None if the value references no event arg.
    """
    match = _LEADING_EVENT_ARG.match(value_str)
    if match is None:
        return None
    name = match.group()
    if name.endswith(_IN_SCOPE_MARKERS):
        return None
    return name


def _client_state_set(var_name: str, value: Any):
    """Signature holder for the ``_client_state_set`` event.

    Args:
        var_name: The client state var name.
        value: The value to set.
    """


def _client_state_get(var_name: str):
    """Signature holder for the ``_client_state_get`` event.

    Args:
        var_name: The client state var name.
    """


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class ClientStateSetter(FunctionVar[Any]):
    """The setter for a ClientStateVar.

    Attach it to an event trigger directly to forward the trigger's argument, or
    call it to bind a specific value or a functional updater.
    """

    # The type of the value being set, used to type lambda updater placeholders.
    _value_type: Any = dataclasses.field(default=Any)

    def __call__(self, value: Any = NoValue) -> Var:  # pyright: ignore [reportIncompatibleMethodOverride]
        """Bind a value to this setter.

        Args:
            value: The value to set. A ``Var`` or literal is set directly; a
                callable is traced at compile time and receives the current
                value, so ``cs.set(lambda v: v + 1)`` becomes an updater.

        Returns:
            A Var which sets the value when triggered.
        """
        if value is NoValue:
            return self

        # Check Var before callable: FunctionVars are themselves callable, and a
        # Var is always passed through (the store treats a function value as an
        # updater at runtime).
        if isinstance(value, Var):
            value_var = value
        elif callable(value):
            value_var = self._trace_updater(value)
        else:
            value_var = LiteralVar.create(value)

        value_str = str(value_var)
        event_arg = _recovered_event_arg(value_str)
        return ArgsFunctionOperationBuilder.create(
            args_names=(event_arg,) if event_arg is not None else (),
            return_expr=self.to(FunctionVar).call(value_var),
        ).to(FunctionVar, EventChain)

    def _trace_updater(self, fn: Callable) -> Var:
        """Trace a Python callable into a functional-updater Var.

        Args:
            fn: The callable, taking at most one argument (the current value).

        Returns:
            The traced updater, or the plain value for a zero-argument callable.

        Raises:
            VarTypeError: If fn takes more than one argument.
        """
        num_args = len(inspect.signature(fn).parameters)
        if num_args > 1:
            msg = "The function passed to ClientStateVar.set should take at most one argument."
            raise VarTypeError(msg)
        if num_args == 0:
            return Var.create(fn())
        placeholder = Var(
            _js_expr=f"prev{next(_placeholder_counter)}{CAMEL_CASE_CLIENT_STATE_MARKER}",
            _var_type=self._value_type,
        ).guess_type()
        return ArgsFunctionOperationBuilder.create(
            args_names=(placeholder._js_expr,),
            return_expr=Var.create(fn(placeholder)),
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class ClientStateVar(Var):
    """A Var that exists on the client via useClientState."""

    # Track the names of the getters and setters
    _setter_name: str = dataclasses.field(default="")
    _getter_name: str = dataclasses.field(default="")
    # The bare name keying this var in the client state store.
    _state_name: str = dataclasses.field(default="")

    # Whether the state is shared by name (and reachable from the backend).
    _global_ref: bool = dataclasses.field(default=True)

    # VarData without the hook, for accessors that work in any JS scope.
    _escape_var_data: VarData | None = dataclasses.field(default=None)

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
            self._state_name,
            self._global_ref,
        ))

    @classmethod
    def create(
        cls,
        var_name: str | None = None,
        default: Any = NoValue,
        global_ref: bool = True,
    ) -> ClientStateVar:
        """Create a local_state Var that can be accessed and updated on the client.

        With ``global_ref`` set (the default) the state is keyed by name in a
        store shared across the app, so it can be read and written from any
        component and from the backend. Without it the state is anonymous: it is
        private to the component the hook is emitted in, and `push`, `retrieve`,
        `global_value` and `global_set` cannot address it.

        To render the var in a component, use the `value` property.

        To update the var in a component, use the `set` property: attach it to a
        trigger to forward the trigger's argument, or call it with a value or a
        function of the current value.

        To access the var in an event handler, use the `retrieve` method with
        `callback` set to the event handler which should receive the value.

        To update the var in an event handler, use the `push` method with the
        value to update.

        To read or write the var from JS outside a React component, use the
        `global_value` and `global_set` properties.

        Args:
            var_name: The name of the variable.
            default: The default value of the variable.
            global_ref: Whether the state should be accessible in any Component and on the backend.

        Returns:
            ClientStateVar

        Raises:
            ValueError: If var_name is not a valid identifier string.
        """
        if var_name is None:
            var_name = f"cs{next(_name_counter)}"
        if isinstance(var_name, Var):
            msg = (
                "var_name must be a string, not a Var. The name keys the client "
                "state store and is embedded in the events that `push`, "
                "`retrieve` and `global_set` send, so it has to be known at "
                "compile time."
            )
            raise ValueError(msg)
        if not isinstance(var_name, str):
            msg = "var_name must be a string."
            raise ValueError(msg)
        if not _VALID_NAME.match(var_name):
            msg = (
                f"var_name {var_name!r} is not a valid javascript identifier; it "
                "is emitted as one in the compiled app."
            )
            raise ValueError(msg)
        if default is NoValue:
            # Explicit `undefined` rather than an empty expression: the name is
            # passed as a second argument, so an empty first argument would emit
            # `useClientState(, "name")` -- a syntax error.
            default_var = Var(_js_expr="undefined")
        elif not isinstance(default, Var):
            default_var = LiteralVar.create(default)
        else:
            default_var = default
        # The marker keeps a user-chosen name from colliding with a JS reserved
        # word; the store key stays the bare name.
        getter_name = f"{var_name}{CAMEL_CASE_CLIENT_STATE_MARKER}"
        setter_name = f"set{var_name[0].upper()}{var_name[1:]}"
        name_arg = f", {LiteralVar.create(var_name)!s}" if global_ref else ""
        hooks: dict[str, VarData | None] = {
            f"const [{getter_name}, {setter_name}] = useClientState({default_var!s}{name_arg})": None,
        }
        app_wraps = get_client_state_app_wraps()
        return cls(
            _js_expr="null",
            _setter_name=setter_name,
            _getter_name=getter_name,
            _state_name=var_name,
            _global_ref=global_ref,
            _var_type=default_var._var_type,
            _var_data=VarData.merge(
                default_var._var_data,
                VarData(
                    hooks=hooks,
                    imports=_CLIENT_STATE_IMPORT,
                    app_wraps=app_wraps,
                ),
            ),
            _escape_var_data=VarData(
                imports=_CLIENT_STATE_ESCAPE_IMPORT,
                app_wraps=app_wraps,
            ),
        )

    @property
    def value(self) -> Var:
        """Get a placeholder for the Var.

        This property can only be rendered on the frontend.

        To access the value in a backend event handler, see `retrieve`. To read
        it from JS outside a React component, see `global_value`.

        Returns:
            an accessor for the client state variable.
        """
        return Var(_js_expr=self._getter_name, _var_data=self._var_data).to(
            self._var_type
        )

    @property
    def set(self) -> ClientStateSetter:
        """Set the value of the client state variable.

        Attach this to a frontend event trigger to forward the trigger's
        argument, or call it with a value (``cs.set(True)``) or a function of the
        current value (``cs.set(lambda v: v + 1)``).

        To set a value from a backend event handler, see `push`. To set it from
        JS outside a React component, see `global_set`.

        Returns:
            A special EventChain Var which will set the value when triggered.
        """
        return ClientStateSetter(
            _js_expr=self._setter_name,
            _var_type=EventChain,
            _var_data=self._var_data,
            _value_type=self._var_type,
        )

    if TYPE_CHECKING:

        @deprecated("Use `set` instead.")
        def set_value(self, value: Any = NoValue) -> Var:
            """Set the value of the client state variable.

            Args:
                value: The value to set.

            Returns:
                A special EventChain Var which will set the value when triggered.
            """
            ...

    else:

        def set_value(self, value: Any = NoValue) -> Var:
            """Set the value of the client state variable.

            Args:
                value: The value to set.

            Returns:
                A special EventChain Var which will set the value when triggered.
            """
            console.deprecate(
                feature_name="ClientStateVar.set_value",
                reason=(
                    "Use .set instead -- `cs.set` for the bare setter, "
                    "`cs.set(value)` to bind a value."
                ),
                deprecation_version="0.9.9",
                removal_version="1.0",
            )
            return self.set(value)

    @property
    def global_value(self) -> Var:
        """Read the client state variable from JS outside a React component.

        Unlike `value` this needs no hook, so it can be used in any javascript
        scope -- a wrapped library's callback, `add_custom_code`, or
        `rx.call_script`. It is a point-in-time read with no reactivity; prefer
        `value` inside components.

        Returns:
            An accessor for the client state variable.

        Raises:
            ValueError: If the ClientStateVar is not global.
        """
        if not self._global_ref:
            msg = "ClientStateVar must be global to read the value from any scope."
            raise ValueError(msg)
        return Var(
            _js_expr=f"getClientState({LiteralVar.create(self._state_name)!s})",
            _var_data=self._escape_var_data,
        ).to(self._var_type)

    @property
    def global_set(self) -> Var:
        """Set the client state variable from JS outside a React component.

        Unlike `set` this needs no hook, so the returned function can be handed
        to a wrapped library as a plain callback. Every subscribed component
        re-renders.

        Returns:
            A function Var which sets the value when called.

        Raises:
            ValueError: If the ClientStateVar is not global.
        """
        if not self._global_ref:
            msg = "ClientStateVar must be global to set the value from any scope."
            raise ValueError(msg)
        return Var(
            _js_expr=(
                f"((value) => setClientState({LiteralVar.create(self._state_name)!s}, value))"
            ),
            _var_data=self._escape_var_data,
        ).to(FunctionVar)

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
        callback_kwargs = {"callback": None}
        if callback is not None:
            callback_kwargs = {
                "callback": str(
                    format.format_queue_events(
                        callback,
                        args_spec=lambda result: [result],
                    )
                ),
            }
        return server_side(
            "_client_state_get",
            inspect.signature(_client_state_get),
            var_name=self._state_name,
            **callback_kwargs,
        )

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
        if isinstance(value, Var):
            # A Var is a client-side expression, which cannot survive the JSON
            # event payload -- it would arrive as its own source text. Evaluate
            # it on the client instead, reaching the store through `refs` (the
            # only binding in scope where run_script's code is evaluated).
            return run_script(
                f"{_client_state_store_ref!s}.set({LiteralVar.create(self._state_name)!s}, {value!s})"
            )
        return server_side(
            "_client_state_set",
            inspect.signature(_client_state_set),
            var_name=self._state_name,
            value=value,
        )


client_state = ClientStateVar.create
