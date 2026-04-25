"""Merge Tailwind CSS classes utility."""

from reflex.utils.imports import ImportVar
from reflex.vars import FunctionVar, Var
from reflex.vars.base import VarData

CN = Var(
    "cn",
    _var_data=VarData(imports={"clsx-for-tailwind": ImportVar(tag="cn")}),
).to(FunctionVar)


def cn(
    *classes: Var | str | tuple | list | None,
) -> Var:
    """Merge Tailwind CSS classes. Accepts strings, Vars, lists, or tuples.

    Args:
        *classes: Any number of class strings, Vars, tuples, or lists.

    Returns:
        Var: A Var representing the merged classes string.

    """
    return CN.call(*classes).to(str)
