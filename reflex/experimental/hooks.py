"""Add standard Hooks wrapper for React."""

from __future__ import annotations

from reflex.ivars.base import ImmutableVar
from reflex.utils.imports import ImportVar
from reflex.vars import VarData


def _compose_react_imports(tags: list[str]) -> dict[str, list[ImportVar]]:
    return {"react": [ImportVar(tag=tag) for tag in tags]}


def const(name, value) -> ImmutableVar:
    """Create a constant Var.

    Args:
        name: The name of the constant.
        value: The value of the constant.

    Returns:
        The constant Var.
    """
    if isinstance(name, list):
        return ImmutableVar.create_safe(f"const [{', '.join(name)}] = {value}")
    return ImmutableVar.create_safe(f"const {name} = {value}")


def useCallback(func, deps) -> ImmutableVar:
    """Create a useCallback hook with a function and dependencies.

    Args:
        func: The function to wrap.
        deps: The dependencies of the function.

    Returns:
        The useCallback hook.
    """
    return ImmutableVar.create_safe(
        f"useCallback({func}, {deps})" if deps else f"useCallback({func})",
        _var_data=VarData(imports=_compose_react_imports(["useCallback"])),
    )


def useContext(context) -> ImmutableVar:
    """Create a useContext hook with a context.

    Args:
        context: The context to use.

    Returns:
        The useContext hook.
    """
    return ImmutableVar.create_safe(
        f"useContext({context})",
        _var_data=VarData(imports=_compose_react_imports(["useContext"])),
    )


def useRef(default) -> ImmutableVar:
    """Create a useRef hook with a default value.

    Args:
        default: The default value of the ref.

    Returns:
        The useRef hook.
    """
    return ImmutableVar.create_safe(
        f"useRef({default})",
        _var_data=VarData(imports=_compose_react_imports(["useRef"])),
    )


def useState(var_name, default=None) -> ImmutableVar:
    """Create a useState hook with a variable name and setter name.

    Args:
        var_name: The name of the variable.
        default: The default value of the variable.

    Returns:
        A useState hook.
    """
    return const(
        [var_name, f"set{var_name.capitalize()}"],
        ImmutableVar.create_safe(
            f"useState({default})",
            _var_data=VarData(imports=_compose_react_imports(["useState"])),
        ),
    )
