"""Turn a lowered style into the StyleX source the compiler places in a module.

A lowered style is a StyleX style object: a mapping from a camelCase CSS
property to a literal, or to a condition map such as
``{"default": "red", ":hover": "blue"}``.

StyleX folds ``stylex.props(...)`` into a ``className`` string only when the
style is declared in the module that renders the element, so every distinct
style becomes a declaration of its own, named after its content. The compiler
deduplicates custom code by its text: elements that share a style share one
declaration, in whichever module each of them is rendered.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping
from typing import TypeAlias, cast

from reflex_base.utils.exceptions import ReflexError
from reflex_base.vars.base import Var

# A literal, or the value of a property under each condition.
LoweredValue: TypeAlias = "str | int | float | Mapping[str, LoweredValue]"
# What `lower` produces and StyleX compiles: camelCase property to value.
LoweredStyle: TypeAlias = Mapping[str, LoweredValue]

# The key under which a declaration holds its style.
_KEY = "s"


class UnsupportedStyleError(ReflexError, TypeError):
    """Raised when an rx.ui component has a style that cannot be compiled."""


@dataclasses.dataclass(frozen=True, slots=True)
class StyleXStyle:
    """The StyleX source of one style.

    Attributes:
        declaration: The module-level ``stylex.create`` statement.
        ref: The expression naming the style, an argument of ``stylex.props``.
    """

    declaration: str
    ref: str


def _check_value(
    value: object, prop: str, component: str, conditions: tuple[str, ...]
) -> None:
    """Fail on a value StyleX cannot compile to a class.

    Args:
        value: The value of the property, or of one of its conditions.
        prop: The style property the value belongs to.
        component: The name of the component, for the error message.
        conditions: The conditions the value is nested under.

    Raises:
        UnsupportedStyleError: If the value is bound to state or is not a
            literal or a condition map.
    """
    if isinstance(value, Mapping):
        for condition, nested in value.items():
            _check_value(nested, prop, component, (*conditions, condition))
        return
    # A bool is an int to isinstance, and no CSS value.
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return
    where = f'"{prop}"' + "".join(f' under "{c}"' for c in conditions)
    if isinstance(value, Var):
        msg = (
            f"{component}: the style {where} is bound to state, which rx.ui "
            "components cannot compile yet. Give it a literal value, or set it "
            "from state with a class_name."
        )
    else:
        msg = (
            f"{component}: the style {where} is {value!r}, a "
            f"{type(value).__name__}. Use a string or a number, or a mapping "
            'from condition to value such as {"default": "red", ":hover": "blue"}.'
        )
    raise UnsupportedStyleError(msg)


def emit(style: LoweredStyle, component: str) -> StyleXStyle | None:
    """Emit the StyleX declaration of a lowered style.

    Args:
        style: The lowered style of one element.
        component: The name of the component, for error messages.

    Returns:
        The declaration and the expression that refers to it, or None when the
        style is empty.

    Raises:
        UnsupportedStyleError: If a value is bound to state or is not a literal.
    """
    if not style:
        return None
    for prop, value in style.items():
        _check_value(value, prop, component, ())
    source = json.dumps(style, ensure_ascii=False)
    # Named after the source rather than the mapping: two declarations of one
    # name in a module would not parse.
    name = "sx_" + hashlib.sha256(source.encode()).hexdigest()[:10]
    return StyleXStyle(
        declaration=f"const {name} = stylex.create({{ {_KEY}: {source} }});",
        ref=f"{name}.{_KEY}",
    )


def props_call(refs: tuple[str, ...], class_name: str | None = None) -> str:
    """Build the ``stylex.props`` call that an element spreads into its props.

    A class name given here is folded into the same ``className`` string as the
    styles, so the element keeps a single static attribute.

    Args:
        refs: The styles to apply, the last one winning a conflict.
        class_name: Literal class names the element also carries.

    Returns:
        The JavaScript expression.
    """
    args = list(refs)
    if class_name:
        # A compiled style is a map of class names marked with `$$css`; this
        # one carries the element's own classes through the fold.
        args.append(f"{{ $$css: true, className: {json.dumps(class_name)} }}")
    return f"stylex.props({', '.join(args)})"


def inline(style: LoweredStyle, component: str) -> dict[str, str | int | float]:
    """Check that a lowered style can be an inline ``style`` attribute.

    The fallback for code that is evaluated in the browser and never reaches
    the StyleX compiler. An inline style has no conditions.

    Args:
        style: The lowered style of one element.
        component: The name of the component, for error messages.

    Returns:
        The style, every value a literal.

    Raises:
        UnsupportedStyleError: If a value has conditions, is bound to state or
            is not a literal.
    """
    result: dict[str, str | int | float] = {}
    for prop, value in style.items():
        if isinstance(value, Mapping):
            conditions = ", ".join(f'"{c}"' for c in value)
            msg = (
                f'{component}: the style "{prop}" has conditions '
                f"({conditions}), which a component rendered from state cannot "
                "apply: its code is evaluated in the browser and never reaches "
                "the StyleX compiler. Use an unconditional value there, or "
                "render the component in a page and show it with rx.cond."
            )
            raise UnsupportedStyleError(msg)
        _check_value(value, prop, component, ())
        result[prop] = cast("str | int | float", value)
    return result
