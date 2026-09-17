"""Special Vars for rendering values from the environment."""

import json
from collections.abc import Sequence
from types import UnionType
from typing import Any, TypeVar, cast, get_args, get_origin, overload

from typing_extensions import TypeForm

from reflex_base.utils import format
from reflex_base.utils.imports import ImportVar
from reflex_base.utils.types import GenericType
from reflex_base.vars.base import Var, VarData, get_unique_variable_name
from reflex_base.vars.function import FunctionStringVar, FunctionVar, ReflexCallable
from reflex_base.vars.object import ObjectVar
from reflex_base.vars.sequence import _determine_value_of_array_index

HOOK_VAR_TYPE = TypeVar("HOOK_VAR_TYPE")
_REACT_LIBRARY = "react"
_USE_ID_HOOK = "useId"


def _assignment_rhs(value: Var) -> str:
    """Render a Var as the right-hand side of an assignment.

    Call operations wrap themselves in parentheses so they are safe to embed in
    a larger expression; the right-hand side of an assignment needs no such
    protection, so one redundant layer is peeled off for readable output.

    Args:
        value: The value being assigned.

    Returns:
        The JS expression to assign.
    """
    expr = str(value)
    return expr[1:-1] if format.is_wrapped(expr, "(") else expr


def _object_key(field: str) -> str:
    """Render a field name as a JavaScript object key.

    Args:
        field: The field name.

    Returns:
        The field name, quoted if it is not a bare identifier.
    """
    return field if field.isidentifier() else json.dumps(field)


def _bind(binding: str, var_type: GenericType, statement: str, source: Var) -> Var:
    """Build the Var for a single name bound by a declaration statement.

    Args:
        binding: The JS identifier the value is bound to.
        var_type: The type of the bound value.
        statement: The declaration statement to carry as a hook.
        source: The Var being bound, whose imports and hooks must come along.

    Returns:
        A Var referring to the binding, carrying the declaration as a hook.
    """
    return Var(
        binding,
        _var_type=var_type,
        _var_data=VarData.merge(
            # Merged first so the value's own hooks are declared before the
            # statement that references them.
            source._get_all_var_data(),
            VarData(hooks=(statement,)),
        ),
    ).guess_type()


def _bindings_for(
    names: Sequence[str | None] | None, count: int, what: str
) -> list[str | None]:
    """Resolve the JS identifiers to bind, generating any that were not given.

    Args:
        names: The caller-supplied names, or None to generate all of them.
        count: How many names are needed.
        what: The name of the argument `names` must line up with, for errors.

    Returns:
        One name per position, where None marks a skipped position.

    Raises:
        ValueError: If the wrong number of names was supplied.
    """
    if names is None:
        return [get_unique_variable_name() for _ in range(count)]
    if len(names) != count:
        msg = f"Got {len(names)} names for {count} {what}."
        raise ValueError(msg)
    return list(names)


def _fixed_tuple_args(var_type: GenericType) -> tuple[Any, ...] | None:
    """Get the element types of a fixed-length tuple type.

    Args:
        var_type: The type to inspect.

    Returns:
        The element types, or None if var_type is not a fixed-length tuple.
    """
    if get_origin(var_type) is not tuple:
        return None
    args = get_args(var_type)
    if not args or (len(args) == 2 and args[1] is ...):
        return None
    return args


@overload
def const(
    value: Var[HOOK_VAR_TYPE], /, *, name: str | None = None
) -> Var[HOOK_VAR_TYPE]: ...


@overload
def const(value: Any, /, *, name: str | None = None) -> Var: ...


def const(value: Any, /, *, name: str | None = None) -> Var:
    """Bind a value to a ``const`` declaration in the component's hook scope.

    The returned Var renders as the bound name and carries the declaration as a
    hook, so it can be used like any other Var and the statement is emitted in
    whichever component reads it.

    Args:
        value: The value to bind.
        name: The JS identifier to bind to, used verbatim. Defaults to a fresh
            unique name. Passing the same name and value twice yields the same
            statement, which the component's hook collection deduplicates;
            passing the same name for different values redeclares it.

    Returns:
        A Var referring to the bound name.
    """
    value_var = Var.create(value)
    binding = name or get_unique_variable_name()
    return _bind(
        binding,
        value_var._var_type,
        f"const {binding} = {_assignment_rhs(value_var)};",
        value_var,
    )


def const_unpack(
    value: Any,
    count: int,
    /,
    *,
    names: Sequence[str | None] | None = None,
    rest: str | bool = False,
) -> tuple[Var, ...]:
    """Bind the leading elements of an array value by destructuring it.

    Renders ``const [a, b] = value;``. Each binding is typed as the element at
    that index of ``value``, so a ``tuple[int, Callable]`` unpacks into a
    ``NumberVar`` and a ``FunctionVar``.

    Args:
        value: The array value to destructure.
        count: How many leading elements to bind.
        names: The JS identifiers to bind to, used verbatim, one per element.
            A None entry leaves that position empty (``const [, b] = value;``)
            and returns no Var for it. Defaults to fresh unique names.
        rest: Bind the remaining elements as a rest element. Pass a string to
            name it. The rest Var is returned last.

    Returns:
        One Var per bound element, followed by the rest Var if requested.

    Raises:
        ValueError: If count exceeds the length of a fixed-length tuple value.
    """
    value_var = Var.create(value)
    tuple_args = _fixed_tuple_args(value_var._var_type)
    if tuple_args is not None and count > len(tuple_args):
        msg = (
            f"Cannot unpack {count} elements from {value_var._var_type}, "
            f"which has {len(tuple_args)}."
        )
        raise ValueError(msg)

    bindings = _bindings_for(names, count, "elements")
    slots = [binding or "" for binding in bindings]
    rest_binding = (
        (rest if isinstance(rest, str) else get_unique_variable_name())
        if rest
        else None
    )
    if rest_binding is not None:
        slots.append(f"...{rest_binding}")
    statement = f"const [{', '.join(slots)}] = {_assignment_rhs(value_var)};"

    bound = [
        _bind(
            binding,
            _determine_value_of_array_index(value_var._var_type, index),
            statement,
            value_var,
        )
        for index, binding in enumerate(bindings)
        if binding is not None
    ]
    if rest_binding is not None:
        bound.append(
            _bind(
                rest_binding,
                tuple[tuple_args[count:]]  # pyright: ignore [reportInvalidTypeArguments]
                if tuple_args is not None
                else value_var._var_type,
                statement,
                value_var,
            )
        )
    return tuple(bound)


def const_fields(
    value: Any,
    /,
    *fields: str,
    names: Sequence[str] | None = None,
    rest: str | bool = False,
) -> tuple[Var, ...]:
    """Bind fields of an object value by destructuring it.

    Renders ``const { a: x, b: y } = value;``, or the shorthand ``const { a }``
    where the binding keeps the field's own name. Each binding is typed as that
    field of ``value``, so the fields of a TypedDict or dataclass come back with
    their declared types and an unknown field raises.

    Args:
        value: The object value to destructure.
        *fields: The field names to bind.
        names: The JS identifiers to bind to, used verbatim, one per field.
            Defaults to fresh unique names.
        rest: Bind the remaining fields as a rest element. Pass a string to name
            it. The rest Var is returned last.

    Returns:
        One Var per field, followed by the rest Var if requested.
    """
    value_var = Var.create(value)
    object_var = (
        value_var if isinstance(value_var, ObjectVar) else value_var.to(ObjectVar)
    )
    bindings = cast(list[str], _bindings_for(names, len(fields), "fields"))

    slots = []
    for field, binding in zip(fields, bindings, strict=True):
        key = _object_key(field)
        slots.append(key if binding == key else f"{key}: {binding}")
    rest_binding = (
        (rest if isinstance(rest, str) else get_unique_variable_name())
        if rest
        else None
    )
    if rest_binding is not None:
        slots.append(f"...{rest_binding}")
    statement = f"const {{ {', '.join(slots)} }} = {_assignment_rhs(value_var)};"

    bound = [
        _bind(binding, object_var[field]._var_type, statement, value_var)
        for field, binding in zip(fields, bindings, strict=True)
    ]
    if rest_binding is not None:
        bound.append(_bind(rest_binding, value_var._var_type, statement, value_var))
    return tuple(bound)


def hook_fn(library: str, hook: str, *, returns: Any = Any) -> FunctionVar:
    """Get a callable Var for a hook imported from a library.

    The hook is imported under a unique alias, so hooks of the same name from
    different libraries do not collide. Calling it yields the hook's return
    value as an expression, which :func:`const` can bind to a name.

    Args:
        library: The library to import the hook from.
        hook: The name of the hook.
        returns: The type the hook returns.

    Returns:
        A callable Var for the hook, carrying its import.
    """
    alias = f"{hook}_{get_unique_variable_name()}"
    return FunctionStringVar.create(
        alias,
        _var_type=ReflexCallable[Any, returns],
        _var_data=VarData(imports={library: ImportVar(tag=hook, alias=alias)}),
    )


@overload
def use_hook_var(library: str, hook: str, *args: Var | Any) -> Var[Any]: ...


@overload
def use_hook_var(
    library: str, hook: str, *args: Var | Any, _var_type: TypeForm[HOOK_VAR_TYPE]
) -> Var[HOOK_VAR_TYPE]: ...


@overload
def use_hook_var(
    library: str, hook: str, *args: Var | Any, _var_type: UnionType
) -> Var[Any]: ...


def use_hook_var(
    library: str, hook: str, *args: Var | Any, _var_type: Any = Any
) -> Var:
    """Get a Var representing a React hook's value.

    The hook is called once in each compiled component that reads the var, so
    every element sharing one value must render inside the same component, such
    as an ``rx.el.svg`` root, an ``@rx.memo`` body, or a custom renderer body.

    Args:
        library: The library to import the hook from.
        hook: The name of the hook.
        *args: Arguments to pass to the hook call.
        _var_type: The type of the Var.

    Returns:
        A Var representing the React hook.

    Raises:
        TypeError: If a type is passed positionally, which used to set _var_type.
    """
    if args and isinstance(args[0], (type, UnionType)):
        msg = (
            "use_hook_var() forwards positional arguments to the hook call; pass "
            "the var type as the keyword argument `_var_type=` instead."
        )
        raise TypeError(msg)
    return const(
        hook_fn(library, hook, returns=cast(GenericType, _var_type)).call(*args)
    )


def use_id() -> Var[str]:
    """Get the stable React useId hook value for a component.

    Returns:
        A Var representing the useId hook value.
    """
    return use_hook_var(_REACT_LIBRARY, _USE_ID_HOOK, _var_type=str)
