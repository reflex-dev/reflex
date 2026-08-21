"""Class name utilities for the Reflex UI component library.

Class merging happens client side with ``tailwind-merge`` so user-provided
classes override the built-in defaults, following Tailwind semantics rather
than CSS source order.
"""

from __future__ import annotations

from collections.abc import Mapping

from reflex_base.utils.imports import ImportVar
from reflex_base.vars import FunctionVar, Var
from reflex_base.vars.base import LiteralVar, VarData

CLSX = Var(
    "clsx",
    _var_data=VarData(imports={"clsx@2.1.1": ImportVar(tag="clsx", is_default=True)}),
).to(FunctionVar)

TW_MERGE = Var(
    "twMerge",
    _var_data=VarData(imports={"tailwind-merge@3.6.0": ImportVar(tag="twMerge")}),
).to(FunctionVar)


def cn(*classes: Var | str | tuple | list | None) -> Var[str]:
    """Merge Tailwind CSS classes, resolving conflicts in favor of later ones.

    Args:
        *classes: Any number of class strings, Vars, tuples, or lists.

    Returns:
        A Var representing the merged class string.
    """
    return TW_MERGE.call(CLSX.call(*classes)).to(str)


def variant_class(
    value: str | Var | None,
    variants: Mapping[str, str],
    *,
    default: str,
    prop: str,
    component: str,
) -> str | Var[str]:
    """Resolve a variant prop to its Tailwind class string.

    Static values are resolved at compile time. ``Var`` values compile to a
    JavaScript expression selecting among the variant class strings, keeping
    every class literal visible to the Tailwind scanner.

    Args:
        value: The variant selected by the user, or None for the default.
        variants: Mapping of variant name to class string.
        default: The variant to use when value is None.
        prop: The prop name, used in error messages.
        component: The component name, used in error messages.

    Returns:
        The class string for the selected variant.

    Raises:
        ValueError: If a static value is not a valid variant name.
    """
    if value is None:
        return variants[default]
    if isinstance(value, Var):
        from reflex_components_core.core.match import match

        cases = [
            (name, LiteralVar.create(classes)) for name, classes in variants.items()
        ]
        resolved = match(value, *cases, LiteralVar.create(variants[default]))
        if not isinstance(resolved, Var):
            msg = f"Expected a Var when resolving {prop!r} for {component}."
            raise ValueError(msg)  # pragma: no cover - match always returns a Var here
        return resolved.to(str)
    if value not in variants:
        options = ", ".join(map(repr, variants))
        msg = f"Invalid {prop} {value!r} for {component}. Valid options: {options}."
        raise ValueError(msg)
    return variants[value]
