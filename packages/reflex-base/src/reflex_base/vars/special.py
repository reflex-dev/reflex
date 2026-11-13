"""Special Vars for rendering values from the environment."""

from types import UnionType
from typing import Any, TypeVar, cast, overload

from typing_extensions import TypeForm

from reflex_base.utils.imports import ImportVar
from reflex_base.utils.types import GenericType
from reflex_base.vars.base import Var, VarData, get_unique_variable_name

HOOK_VAR_TYPE = TypeVar("HOOK_VAR_TYPE")
_REACT_LIBRARY = "react"
_USE_ID_HOOK = "useId"


@overload
def use_hook_var(library: str, hook: str) -> Var[Any]: ...


@overload
def use_hook_var(
    library: str, hook: str, _var_type: TypeForm[HOOK_VAR_TYPE]
) -> Var[HOOK_VAR_TYPE]: ...


@overload
def use_hook_var(library: str, hook: str, _var_type: UnionType) -> Var[Any]: ...


def use_hook_var(library: str, hook: str, _var_type: Any = Any) -> Var:
    """Get a Var representing a React hook's value.

    The hook is called once in each compiled component that reads the var, so
    every element sharing one value must render inside the same component, such
    as an ``rx.el.svg`` root, an ``@rx.memo`` body, or a custom renderer body.

    Args:
        library: The library to import the hook from.
        hook: The name of the hook.
        _var_type: The type of the Var.

    Returns:
        A Var representing the React hook.
    """
    var_name = get_unique_variable_name()
    hook_alias = f"{hook}_{var_name}"
    return Var(
        var_name,
        _var_type=cast(GenericType, _var_type),
        _var_data=VarData(
            imports={library: ImportVar(tag=hook, alias=hook_alias)},
            hooks=(f"const {var_name} = {hook_alias}();",),
        ),
    ).guess_type()


def use_id() -> Var[str]:
    """Get the stable React useId hook value for a component.

    Returns:
        A Var representing the useId hook value.
    """
    return use_hook_var(library=_REACT_LIBRARY, hook=_USE_ID_HOOK, _var_type=str)
