"""Add standard Hooks wrapper for React."""

from __future__ import annotations

from reflex.utils.imports import ImportVar
from reflex.vars import Var, VarData


def _compose_react_imports(tags: list[str]) -> dict[str, list[ImportVar]]:
    return {"react": [ImportVar(tag=tag, install=False) for tag in tags]}


def const(name, value) -> Var:
    """Create a constant Var.

    Args:
        name: The name of the constant.
        value: The value of the constant.

    Returns:
        The constant Var.
    """
    if isinstance(name, list):
        return Var.create_safe(
            f"const [{', '.join(name)}] = {value}", _var_is_string=False
        )
    return Var.create_safe(f"const {name} = {value}", _var_is_string=False)


def useCallback(func, deps) -> Var:
    """Create a useCallback hook with a function and dependencies.

    Args:
        func: The function to wrap.
        deps: The dependencies of the function.

    Returns:
        The useCallback hook.
    """
    return Var.create_safe(
        f"useCallback({func}, {deps})" if deps else f"useCallback({func})",
        _var_is_string=False,
        _var_data=VarData(imports=_compose_react_imports(["useCallback"])),
    )


def useContext(context) -> Var:
    """Create a useContext hook with a context.

    Args:
        context: The context to use.

    Returns:
        The useContext hook.
    """
    return Var.create_safe(
        f"useContext({context})",
        _var_is_string=False,
        _var_data=VarData(imports=_compose_react_imports(["useContext"])),
    )


def useRef(default) -> Var:
    """Create a useRef hook with a default value.

    Args:
        default: The default value of the ref.

    Returns:
        The useRef hook.
    """
    return Var.create_safe(
        f"useRef({default})",
        _var_is_string=False,
        _var_data=VarData(imports=_compose_react_imports(["useRef"])),
    )


def useState(var_name, default=None) -> Var:
    """Create a useState hook with a variable name and setter name.

    Args:
        var_name: The name of the variable.
        default: The default value of the variable.

    Returns:
        A useState hook.
    """
    return const(
        [var_name, f"set{var_name.capitalize()}"],
        Var.create_safe(
            f"useState({default})",
            _var_is_string=False,
            _var_data=VarData(imports=_compose_react_imports(["useState"])),
        ),
    )
