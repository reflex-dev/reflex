"""Merge Tailwind CSS classes utility."""

from reflex.utils.imports import ImportVar
from reflex.vars import FunctionVar, Var
from reflex.vars.base import VarData

CLSX = Var(
    "clsx",
    _var_data=VarData(imports={"clsx@2.1.1": ImportVar(tag="clsx", is_default=True)}),
).to(FunctionVar)

TW_MERGE = Var(
    "twMerge",
    _var_data=VarData(imports={"tailwind-merge@3.6.0": ImportVar(tag="twMerge")}),
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
    return TW_MERGE.call(CLSX.call(*classes)).to(str)
