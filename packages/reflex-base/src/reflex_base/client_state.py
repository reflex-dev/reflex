"""Handle client side state with `useClientState`."""

from __future__ import annotations

import contextlib
import dataclasses
import inspect
import itertools
import json
import re
import sys
from collections.abc import Callable, Iterable, Iterator
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from reflex_base.components.client_state_context import get_client_state_app_wraps
from reflex_base.constants import Dirs
from reflex_base.constants.state import CAMEL_CASE_CLIENT_STATE_MARKER, CLIENT_STATE_REF
from reflex_base.event import (
    EventChain,
    EventHandler,
    EventSpec,
    event_args_signature,
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

# Raised for every path that addresses a var by name from outside its tree.
_NOT_GLOBAL_MSG = (
    "Cannot {action}: this client state var is unnamed, so it is scoped to the "
    "component tree that uses it. Give it a name to make it global and "
    'addressable: rx.client_state(default, name="my_name").'
)

# Appended to _NOT_GLOBAL_MSG when the default could have been meant as a name,
# as in the name-first order of the deprecated `rx._x.client_state`.
_NAME_AS_DEFAULT_MSG = (
    " Its default is {default}: the first positional argument is the default, "
    "so if that was meant as the name, write "
    "rx.client_state(default, name={default})."
)

# Default prefix for generated names.
_DEFAULT_NAME_PREFIX = "cs"

# Names and prefixes are emitted inside javascript identifiers. `$` is left out:
# it separates a generated name's prefix from its counter, so a chosen name can
# never equal a generated one.
_VALID_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")

# The javascript bindings of a var are its name plus a fixed suffix each, so
# they are injective in the name and the three kinds never coincide (the
# getter ends in `State`, the others in `Set` and `Arg`).
_GETTER_SUFFIX = CAMEL_CASE_CLIENT_STATE_MARKER
_SETTER_SUFFIX = f"{CAMEL_CASE_CLIENT_STATE_MARKER}Set"
_PLACEHOLDER_SUFFIX = f"{CAMEL_CASE_CLIENT_STATE_MARKER}Arg"

# A `useClientState` declaration: the default expression, then the name.
_DECLARATION = re.compile(r'= useClientState\((.*), "([A-Za-z0-9_$]+)"(?:, true)?\)\Z')

# The declarations rendered so far in the current compile, by name. Unset
# outside a compile, where only declarations within one body are compared.
_compile_declarations: ContextVar[dict[str, str] | None] = ContextVar(
    "_compile_declarations", default=None
)

# Where each named declaration was last created, by its hook line, for the
# conflict error. Bounded by the distinct named declarations in the process.
_declaration_sites: dict[str, str] = {}

# Modules whose frames sit between the user's call and `_create`.
_FACTORY_MODULES = frozenset({__name__, "reflex.experimental.client_state"})


def _validate_name(value: Any, kind: str) -> str:
    """Check that a name or prefix can be emitted in a javascript identifier.

    Args:
        value: The name or prefix.
        kind: ``"name"`` or ``"prefix"``, for the error message.

    Returns:
        The value, now known to be a valid string.

    Raises:
        ValueError: If the value is not a string or breaks the naming rule.
    """
    if isinstance(value, Var):
        msg = (
            f"{kind} must be a string, not a Var. The name keys the client "
            "state store and is embedded in the events that `push`, "
            "`retrieve` and `global_set` send, so it has to be known at "
            "compile time."
        )
        raise ValueError(msg)
    if not isinstance(value, str):
        msg = f"{kind} must be a string, got {type(value).__name__}: {value!r}"
        raise ValueError(msg)
    if not _VALID_NAME.match(value):
        msg = (
            f"{kind} {value!r} is not a valid client state {kind}: it must be "
            "an ASCII identifier, a letter or underscore followed by letters, "
            "digits or underscores. It must not contain '$', which is "
            "reserved for generated names."
        )
        raise ValueError(msg)
    return value


def _generate_name(prefix: str = _DEFAULT_NAME_PREFIX) -> str:
    """Build the name of an unnamed var from a prefix and the shared counter.

    ``$`` separates the two and is not allowed in the prefix, so two generated
    names are equal only when both their prefixes and their counters are, and
    never equal a chosen name.

    Args:
        prefix: The readable part of the name.

    Returns:
        The generated name, a valid javascript identifier.
    """
    return f"{_validate_name(prefix, 'prefix')}${next(_name_counter)}"


def _caller_site() -> str:
    """Locate the user code that created a client state var.

    Returns:
        ``file:line`` of the first frame outside the client state factories.
    """
    frame = sys._getframe(1)
    while frame.f_back is not None and frame.f_globals.get("__name__") in (
        _FACTORY_MODULES
    ):
        frame = frame.f_back
    return f"{frame.f_code.co_filename}:{frame.f_lineno}"


def _describe_declaration(hook: str) -> str:
    """Describe a declaration by its default and where it was created.

    Args:
        hook: A ``useClientState`` hook line.

    Returns:
        The default expression, and the creation site when known.
    """
    match = _DECLARATION.search(hook)
    default = f"`{match[1]}`" if match else repr(hook)
    site = _declaration_sites.get(hook)
    return f"{default} (declared at {site})" if site else default


def _check_declarations(hooks: Iterable[str]) -> None:
    """Reject a client state name declared with two different defaults.

    Called on every body's hooks as it is rendered. During a compile (see
    `_collect_declarations`) the comparison spans every body; otherwise it
    covers the one body.

    Args:
        hooks: The hook lines of one body.

    Raises:
        ValueError: If a name is declared with a different default than before.
    """
    seen = _compile_declarations.get()
    if seen is None:
        seen = {}
    for hook in hooks:
        if "= useClientState(" not in hook or not (match := _DECLARATION.search(hook)):
            continue
        name = match[2]
        first = seen.setdefault(name, hook)
        if first != hook:
            msg = (
                f"Client state var {name!r} is declared with two different "
                f"defaults: {_describe_declaration(first)} and "
                f"{_describe_declaration(hook)}. A named client state var is "
                "one app-wide value, so every declaration of it must use the "
                "same default. Declare it once and import it where it is used, "
                "or give the declarations different names."
            )
            raise ValueError(msg)


@contextlib.contextmanager
def _collect_declarations() -> Iterator[None]:
    """Compare client state declarations across every body rendered inside.

    A fresh record per compile, so a declaration edited before a hot reload
    is not compared against its old self.

    Yields:
        Nothing; the record is dropped on exit.
    """
    token = _compile_declarations.set({})
    try:
        yield
    finally:
        _compile_declarations.reset(token)


# The store's entry point on the global `refs` object. This is the only binding
# reachable from the scope `run_script` code is evaluated in, and doubles as the
# devtools handle for inspecting client state.
_client_state_store_ref = Var(
    _js_expr=f"refs[{json.dumps(CLIENT_STATE_REF)}]",
    _var_data=VarData(
        imports={f"$/{Dirs.STATE_PATH}": [ImportVar(tag="refs")]},
    ),
)


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

        # The value may read the arguments of the trigger it is attached to,
        # which the wrapper then has to declare.
        return ArgsFunctionOperationBuilder.create(
            args_names=event_args_signature(value_var),
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
            _js_expr=f"prev{next(_placeholder_counter)}{_PLACEHOLDER_SUFFIX}",
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

    # Whether the name resolves in the app-wide root scope (and is therefore
    # reachable from the backend) rather than being owned by a component tree.
    _is_global: bool = dataclasses.field(default=True)

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
            self._is_global,
        ))

    @classmethod
    def create(
        cls,
        default: Any = NoValue,
        *,
        name: str | None = None,
        prefix: str = _DEFAULT_NAME_PREFIX,
    ) -> ClientStateVar:
        """Create a client state Var that can be accessed and updated on the client.

        Whether the state is shared app-wide follows from whether you name it:

        - ``rx.client_state(default, name="my_name")`` is **global**. It
          resolves in one app-wide store, so any component and the backend can
          read and write it, and `push`, `retrieve`, `global_value` and
          `global_set` work. The name must be an ASCII identifier without
          ``$``. Declaring one name in several places is allowed only with the
          same default; the compile fails on two different defaults.
        - ``rx.client_state()`` is **tree-scoped**. It gets a compile-time name
          and is owned by the outermost page or ``@rx.memo`` body that uses
          it, so each instance of that component gets its own state -- like
          React's ``useState`` -- and nothing outside the tree can address it.
          A page owns its vars only while it is mounted.

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
            default: The default value of the variable.
            name: Optional name. Naming the var makes it global.
            prefix: Prefix for the generated name when the var is unnamed, to
                keep the compiled javascript readable. Must not contain ``$``.
                Ignored when ``name`` is given.

        Returns:
            ClientStateVar

        Raises:
            ValueError: If name or prefix is not a valid identifier string.
        """
        # Named -> global, unnamed -> tree-scoped.
        if name is None:
            return cls._create(default, _generate_name(prefix), is_global=False)
        return cls._create(default, _validate_name(name, "name"), is_global=True)

    @classmethod
    def _create(cls, default: Any, var_name: str, *, is_global: bool) -> ClientStateVar:
        """Build a client state var for an already validated name.

        Args:
            default: The default value of the variable, or ``NoValue``.
            var_name: The store key, a chosen or generated name.
            is_global: Whether the name resolves in the app-wide root scope.

        Returns:
            The client state var.
        """
        if default is NoValue:
            # Explicit `undefined` rather than an empty expression: the name is
            # passed as a second argument, so an empty first argument would emit
            # `useClientState(, "name")` -- a syntax error.
            default_var = Var(_js_expr="undefined")
        elif not isinstance(default, Var):
            default_var = LiteralVar.create(default)
        else:
            default_var = default
        # The suffixes keep a user-chosen name from colliding with a JS reserved
        # word, and with each other; the store key stays the bare name.
        getter_name = f"{var_name}{_GETTER_SUFFIX}"
        setter_name = f"{var_name}{_SETTER_SUFFIX}"
        # The name is always passed: it identifies the slot within whichever
        # scope owns it. The trailing flag is what escapes to the root scope.
        args = f"{default_var!s}, {LiteralVar.create(var_name)!s}"
        if is_global:
            args += ", true"
        hook = f"const [{getter_name}, {setter_name}] = useClientState({args})"
        if is_global:
            # Only a named var can be declared twice, so only its site is kept.
            _declaration_sites[hook] = _caller_site()
        hooks: dict[str, VarData | None] = {hook: None}
        app_wraps = get_client_state_app_wraps()
        return cls(
            _js_expr="null",
            _setter_name=setter_name,
            _getter_name=getter_name,
            _state_name=var_name,
            _is_global=is_global,
            _var_type=default_var._var_type,
            _var_data=VarData.merge(
                # ``_get_all_var_data``, not ``._var_data``: a derived or cast
                # default (a state var read, a cast var) keeps its hooks and
                # imports on the var it wraps, and dropping them compiles the
                # default's identifier into a dangling reference.
                default_var._get_all_var_data(),
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

    def _require_global(self, action: str) -> None:
        """Reject addressing an unnamed var by name.

        Args:
            action: What the caller tried to do.

        Raises:
            ValueError: If the var is unnamed, pointing out a default that
                looks like a misplaced name.
        """
        if self._is_global:
            return
        msg = _NOT_GLOBAL_MSG.format(action=action)
        # Read back from the hook: this is an error path, so no field is
        # spent on remembering the default.
        for hook in self._var_data.hooks if self._var_data else ():
            match = _DECLARATION.search(hook)
            if match and match[2] == self._state_name:
                default = match[1]
                if (
                    len(default) > 2
                    and default[0] == default[-1] == '"'
                    and _VALID_NAME.match(default[1:-1])
                ):
                    msg += _NAME_AS_DEFAULT_MSG.format(default=default)
                break
        raise ValueError(msg)

    @property
    def value(self) -> Var:
        """A placeholder for the Var.

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
                deprecation_version="0.11.0",
                removal_version="1.0",
            )
            return self.set(value)

    @property
    def global_value(self) -> Var:
        """Read the client state variable from JS outside a React component.

        Unlike `value` this needs no hook, so it can be used in any javascript
        scope that has the page's imports -- a wrapped library's callback or
        `add_custom_code`. It is a point-in-time read with no reactivity; prefer
        `value` inside components. Code passed to `rx.call_script` runs in the
        runtime module instead; it reaches the store through ``refs``.

        Returns:
            An accessor for the client state variable.

        Raises:
            ValueError: If the ClientStateVar is not global.
        """
        self._require_global("read the value from outside the tree")
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
        self._require_global("set the value from outside the tree")
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
        self._require_global("retrieve the value")
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
        self._require_global("push a value")
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
