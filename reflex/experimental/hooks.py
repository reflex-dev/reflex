"""Add standard Hooks wrapper for React."""

from reflex.utils.imports import ImportVar
from reflex.vars import Var, VarData


def _add_react_import(v: Var | None, tags: str | list):
    if v is None:
        return

    if isinstance(tags, str):
        tags = [tags]

    v._var_data = VarData(  # type: ignore
        imports={"react": [ImportVar(tag=tag, install=False) for tag in tags]},
    )


def const(name, value) -> Var | None:
    """Create a constant Var.

    Args:
        name: The name of the constant.
        value: The value of the constant.

    Returns:
        The constant Var.
    """
    if isinstance(name, list):
        return Var.create(f"const [{', '.join(name)}] = {value}")
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


def useState(var_name, default=None) -> Var | None:
    """Create a useState hook with a variable name and setter name.

    Args:
        var_name: The name of the variable.
        default: The default value of the variable.

    Returns:
        A useState hook.
    """
    setter_name = f"set{var_name.capitalize()}"
    v = const([var_name, setter_name], f"useState({default})")
    _add_react_import(v, "useState")
    return v
