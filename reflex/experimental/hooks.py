"""Add standard Hooks wrapper for React."""

from reflex.utils.imports import ImportVar
from reflex.vars import Var, VarData


def _add_react_import(v: Var | None, tags: str | list):
    if v is None:
        return

    if isinstance(tags, str):
        tags = [tags]

    v._var_data = VarData(  # type: ignore
        imports={"react": [ImportVar(tag=tag) for tag in tags]},
    )


def const(name, value) -> Var | None:
    """Create a constant Var.

    Args:
        name: The name of the constant.
        value: The value of the constant.

    Returns:
        The constant Var.
    """
    return Var.create(f"const {name} = {value}")


def useCallback(func, deps) -> Var | None:
    """Create a useCallback hook with a function and dependencies.

    Args:
        func: The function to wrap.
        deps: The dependencies of the function.

    Returns:
        The useCallback hook.
    """
    if deps:
        v = Var.create(f"useCallback({func}, {deps})")
    else:
        v = Var.create(f"useCallback({func})")
    _add_react_import(v, "useCallback")
    return v


def useContext(context) -> Var | None:
    """Create a useContext hook with a context.

    Args:
        context: The context to use.

    Returns:
        The useContext hook.
    """
    v = Var.create(f"useContext({context})")
    _add_react_import(v, "useContext")
    return v


def useRef(default) -> Var | None:
    """Create a useRef hook with a default value.

    Args:
        default: The default value of the ref.

    Returns:
        The useRef hook.
    """
    v = Var.create(f"useRef({default})")
    _add_react_import(v, "useRef")
    return v
