"""Special Vars for rendering values from the environment."""

from typing import Any

from reflex_base.utils.types import GenericType
from reflex_base.vars.base import Var, VarData, get_unique_variable_name


def use_hook_var(library: str, hook: str, _var_type: GenericType = Any) -> Var:
    """Get a Var representing a React hook's value.

    The value will depend on the context of the component in which it is used.

    Args:
        library: The library to import the hook from.
        hook: The name of the hook.
        _var_type: The type of the Var.

    Returns:
        A Var representing the React hook.
    """
    return Var(
        var_name := get_unique_variable_name(),
        _var_type=_var_type,
        _var_data=VarData(
            imports={library: hook},
            hooks=(f"const {var_name} = {hook}();",),
        ),
    ).guess_type()


def use_id() -> Var[str]:
    """Get the stable React useId hook value for a component.

    Returns:
        A Var representing the useId hook value.
    """
    return use_hook_var(library="react", hook="useId", _var_type=str)
