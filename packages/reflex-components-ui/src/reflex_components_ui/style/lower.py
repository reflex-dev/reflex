"""Lower the styles a user writes into the style objects StyleX compiles.

The lowered form of a style is a mapping from a CSS property, in camelCase, to
its value. A value is one of:

- a literal, ``str``, ``int`` or ``float``, which becomes an atomic class;
- a ``Var``, which becomes a CSS variable set inline on the element;
- a condition map such as ``{"default": v, ":hover": v, "@media ...": v}``,
  whose values are again literals, Vars or condition maps. ``"default"`` is
  left out when the style gives the property no unconditional value;
- ``None``, which unsets the property. It only appears as the ``"default"`` of a
  condition map and in the alternatives of a state-bound variant.

Every shorthand that can be split is expanded to its longhands, so that two
styles that set the same thing set the same keys and the last one wins. The
``border`` and ``background`` shorthands are always split, because StyleX drops
them; ``animation``, which cannot be split here, is refused. A shorthand that
is kept whole, such as ``padding`` bound to state, removes its longhands from
the styles merged before it, since StyleX lets a longhand win over a shorthand
whatever their order.

Logical and physical longhands, such as ``marginInlineStart`` and
``marginLeft``, are different keys, and StyleX lets the physical one win.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from reflex_base.breakpoints import Breakpoints, breakpoint_names, breakpoints_values
from reflex_base.constants.base import REFLEX_VAR_OPENING_TAG
from reflex_base.constants.colors import Color
from reflex_base.style import media_query
from reflex_base.utils import format
from reflex_base.utils.exceptions import ReflexError
from reflex_base.vars.base import LiteralVar, Var

from reflex_components_ui._radix_tokens import VAR_GROUPS
from reflex_components_ui.constants import WEB_DIR
from reflex_components_ui.style._css_props import (
    CSS_PROPS,
    PSEUDO_CLASSES,
    PSEUDO_ELEMENTS,
)

if TYPE_CHECKING:
    from reflex_components_ui.style._css_props import StyleProps

# A property of a lowered style: a literal, a Var, a condition map or None.
LoweredValue = Any

# The properties one style sets, and the properties of earlier styles that a
# shorthand it could not expand replaces.
Layer = tuple[dict[str, LoweredValue], tuple[str, ...]]

# How a style key is lowered: the camelCase property, the longhands it expands
# to, how its value is shared between them, and what it replaces when it is
# kept whole. The third item is None when every longhand takes the whole value,
# a dict from the number of values to the longhand each goes to, or a function
# that splits the value itself. A condition has no property and its text in the
# second place.
_Entry = tuple[Any, Any, Any, Any]


class StyleError(ReflexError, ValueError):
    """A style that cannot be compiled."""


# The module whose import emits the CSS of a custom property, by the whole
# name of the property: the first word does not tell, as ``--radius-1`` and
# ``--radius-factor`` are different groups and a dozen first words are
# typography. A custom property that is not in the generated list, such as one
# an app defines, imports nothing.
VAR_MODULES: dict[str, str] = {
    name: f"$/{WEB_DIR}/{module}"
    for module, names in VAR_GROUPS.values()
    for name in names
}

# The custom properties that hold one value, which a shorthand can give to a
# longhand. A shadow and a font family are lists, and the panel properties
# are empty or invalid by design.
_MULTIPLE_VALUES = re.compile(
    r"--shadow-|--panel-solid$|--backdrop-filter-panel$|--color-panel-if-solid$"
    r"|-font-family$"
)
_SINGLE_VALUE_VARS: frozenset[str] = frozenset([
    f"var({name})"
    for _, names in VAR_GROUPS.values()
    for name in names
    if not _MULTIPLE_VALUES.search(name)
])

_VAR_NAME = re.compile(r"var\(\s*(--[\w-]+)")
_IDENTIFIER = re.compile(r"-?[A-Za-z_][\w-]*")
_PARENTHESISED = re.compile(r"\([^()]*\)")
_COMBINATOR = re.compile(r"[\s>+~,&]")
_AT_RULES = ("@media ", "@container ", "@supports ", "@starting-style")
_MISSING: Any = object()

# Which value goes to which longhand, by the number of values given.
_FOUR = {1: (0, 0, 0, 0), 2: (0, 1, 0, 1), 3: (0, 1, 2, 1), 4: (0, 1, 2, 3)}
_TWO = {1: (0, 0), 2: (0, 1)}


def _sides(prefix: str, suffix: str = "") -> tuple[str, ...]:
    """Name the four physical longhands of a box shorthand.

    Args:
        prefix: What comes before the side, such as ``border``.
        suffix: What comes after it, such as ``Width``.

    Returns:
        The top, right, bottom and left properties.
    """
    return tuple([
        f"{prefix}{side}{suffix}" for side in ("Top", "Right", "Bottom", "Left")
    ])


def _ends(prefix: str) -> tuple[str, str]:
    """Name the two logical longhands of an axis shorthand.

    Args:
        prefix: The shorthand, such as ``marginInline``.

    Returns:
        The start and end properties.
    """
    return f"{prefix}Start", f"{prefix}End"


# The shorthands that are split into longhands, with their longhands in the
# order the values of the shorthand are given.
_EXPANSIONS: dict[str, tuple[tuple[str, ...], dict[int, tuple[int, ...]]]] = {
    "margin": (_sides("margin"), _FOUR),
    "padding": (_sides("padding"), _FOUR),
    "inset": (("top", "right", "bottom", "left"), _FOUR),
    "scrollMargin": (_sides("scrollMargin"), _FOUR),
    "scrollPadding": (_sides("scrollPadding"), _FOUR),
    "borderWidth": (_sides("border", "Width"), _FOUR),
    "borderStyle": (_sides("border", "Style"), _FOUR),
    "borderColor": (_sides("border", "Color"), _FOUR),
    "borderRadius": (
        (
            "borderTopLeftRadius",
            "borderTopRightRadius",
            "borderBottomRightRadius",
            "borderBottomLeftRadius",
        ),
        _FOUR,
    ),
    "gap": (("rowGap", "columnGap"), _TWO),
    "overflow": (("overflowX", "overflowY"), _TWO),
    "overscrollBehavior": (("overscrollBehaviorX", "overscrollBehaviorY"), _TWO),
    "marginInline": (_ends("marginInline"), _TWO),
    "marginBlock": (_ends("marginBlock"), _TWO),
    "paddingInline": (_ends("paddingInline"), _TWO),
    "paddingBlock": (_ends("paddingBlock"), _TWO),
    "insetInline": (_ends("insetInline"), _TWO),
    "insetBlock": (_ends("insetBlock"), _TWO),
}

# The style keys Reflex adds to CSS: each gives its one value to every target.
_REFLEX_KEYS: dict[str, tuple[str, ...]] = {
    "paddingX": ("paddingLeft", "paddingRight"),
    "paddingY": ("paddingTop", "paddingBottom"),
    "marginX": ("marginLeft", "marginRight"),
    "marginY": ("marginTop", "marginBottom"),
    "bgColor": ("backgroundColor",),
}

# The border shorthands and the sides each one sets. StyleX compiles none of
# them, so each is split into the width, style and color of its sides.
_BORDERS: dict[str, tuple[str, ...]] = {
    "border": _sides("border"),
    "borderTop": ("borderTop",),
    "borderRight": ("borderRight",),
    "borderBottom": ("borderBottom",),
    "borderLeft": ("borderLeft",),
    "borderBlock": ("borderTop", "borderBottom"),
    "borderBlockStart": ("borderTop",),
    "borderBlockEnd": ("borderBottom",),
    "borderInline": ("borderInlineStart", "borderInlineEnd"),
    "borderInlineStart": ("borderInlineStart",),
    "borderInlineEnd": ("borderInlineEnd",),
}

# The shorthands StyleX does not compile and that cannot be split here, with
# what to set in their place.
_UNSUPPORTED: dict[str, str] = {
    "animation": "animation_name, animation_duration and its other longhands",
}

_BORDER_STYLES = frozenset((
    "none",
    "hidden",
    "dotted",
    "dashed",
    "solid",
    "double",
    "groove",
    "ridge",
    "inset",
    "outset",
))
_BORDER_WIDTH = re.compile(
    r"thin|medium|thick|-?(?:\d+\.?\d*|\.\d+)[a-z%]*|(?:calc|min|max|clamp)\(.*\)"
)
_IMAGE = re.compile(
    r"none$|(?:url|image|image-set|cross-fade|element|paint"
    r"|(?:repeating-)?(?:linear|radial|conic)-gradient)\("
)

# What a shorthand that is kept whole replaces in the styles before it: StyleX
# lets a longhand win over a shorthand whatever their order, so the longhands
# of an earlier style have to go for the later shorthand to win.
_REPLACES: dict[str, tuple[str, ...]] = {
    **{shorthand: longhands for shorthand, (longhands, _) in _EXPANSIONS.items()},
    "margin": (
        *_sides("margin"),
        "marginInline",
        "marginBlock",
        *_ends("marginInline"),
        *_ends("marginBlock"),
    ),
    "padding": (
        *_sides("padding"),
        "paddingInline",
        "paddingBlock",
        *_ends("paddingInline"),
        *_ends("paddingBlock"),
    ),
    "inset": (
        "top",
        "right",
        "bottom",
        "left",
        "insetInline",
        "insetBlock",
        *_ends("insetInline"),
        *_ends("insetBlock"),
    ),
    "outline": ("outlineColor", "outlineStyle", "outlineWidth"),
    "flex": ("flexGrow", "flexShrink", "flexBasis"),
    "flexFlow": ("flexDirection", "flexWrap"),
    "font": (
        "fontFamily",
        "fontSize",
        "fontStretch",
        "fontStyle",
        "fontVariant",
        "fontWeight",
        "lineHeight",
    ),
    "transition": (
        "transitionDelay",
        "transitionDuration",
        "transitionProperty",
        "transitionTimingFunction",
    ),
    "gridArea": (
        "gridRow",
        "gridColumn",
        "gridRowStart",
        "gridRowEnd",
        "gridColumnStart",
        "gridColumnEnd",
    ),
    "gridRow": ("gridRowStart", "gridRowEnd"),
    "gridColumn": ("gridColumnStart", "gridColumnEnd"),
    "gridTemplate": ("gridTemplateRows", "gridTemplateColumns", "gridTemplateAreas"),
    "placeContent": ("alignContent", "justifyContent"),
    "placeItems": ("alignItems", "justifyItems"),
    "placeSelf": ("alignSelf", "justifySelf"),
    "textDecoration": (
        "textDecorationLine",
        "textDecorationStyle",
        "textDecorationColor",
        "textDecorationThickness",
    ),
    "listStyle": ("listStyleType", "listStylePosition", "listStyleImage"),
    "columns": ("columnWidth", "columnCount"),
    "columnRule": ("columnRuleWidth", "columnRuleStyle", "columnRuleColor"),
}


def suggest(key: str, candidates: Any) -> str:
    """Word the suggestion that ends an error about a misspelt key.

    Args:
        key: What the user wrote.
        candidates: The keys that exist.

    Returns:
        A sentence naming the closest key, or nothing when none is close.
    """
    close = difflib.get_close_matches(key, candidates, n=1)
    return f' Did you mean "{close[0]}"?' if close else ""


def _condition(name: str, key: str) -> str | None:
    """Read a style key as the condition a block of styles applies under.

    Args:
        name: The display name of the component, for error messages.
        key: The style key.

    Returns:
        The condition as StyleX takes it, or None if the key is not one.

    Raises:
        StyleError: If the key is a selector or at-rule that styles cannot use.
    """
    first = key[:1]
    if first == "_":
        pseudo = format.to_kebab_case(key[1:])
        if pseudo in PSEUDO_ELEMENTS:
            return f"::{pseudo}"
        if pseudo in PSEUDO_CLASSES:
            return f":{pseudo}"
        if _IDENTIFIER.fullmatch(key):
            known = [
                f"_{pseudo.replace('-', '_')}"
                for pseudo in sorted(PSEUDO_CLASSES | PSEUDO_ELEMENTS)
                if not pseudo.startswith("-")
            ]
            msg = f'{name}: unknown pseudo-class "{key}".{suggest(key, known)}'
            raise StyleError(msg)
    elif first == "@":
        if key.startswith(_AT_RULES):
            return key
        msg = (
            f'{name}: style key "{key}" is an at-rule that rx.ui styles do not '
            "support. Use @media, @container, @supports or @starting-style."
        )
        raise StyleError(msg)
    elif first in (":", "[", "&"):
        selector = key[1:] if first == "&" else key
        flat = selector
        while "(" in flat:
            flat, count = _PARENTHESISED.subn("", flat)
            if not count:
                break
        if (
            selector[:1] in (":", "[")
            and not _COMBINATOR.search(flat)
            and (selector[0] == ":" or (flat.endswith("]") and flat.count("[") == 1))
        ):
            return selector
    elif _IDENTIFIER.fullmatch(key):
        return None
    msg = (
        f'{name}: style key "{key}" is a nested selector, which rx.ui styles do '
        "not support. Style the child component directly, or keep "
        f"{name.replace('rx.ui.', 'rx.', 1)} for this element."
    )
    raise StyleError(msg)


def _resolve(name: str, key: Any) -> _Entry:
    """Work out how a style key that is not a snake_case property is lowered.

    Args:
        name: The display name of the component, for error messages.
        key: The style key.

    Returns:
        The entry of the key, which is remembered for the next style.

    Raises:
        StyleError: If the key is neither a CSS property nor a condition.
    """
    if not isinstance(key, str):
        msg = f"{name}: a style key must be a string, not {key!r}."
        raise StyleError(msg)
    if key.startswith("--"):
        entry = (key, None, None, None)
    else:
        entry = _BY_CAMEL.get(format.to_camel_case(key))
        if entry is None:
            condition = _condition(name, key)
            if condition is None:
                candidates = (
                    _BY_CAMEL if "_" not in key and "-" not in key else _SNAKE_KEYS
                )
                msg = (
                    f'{name}: unknown CSS property "{key}".'
                    f"{suggest(key.replace('-', '_'), candidates)}"
                )
                raise StyleError(msg)
            entry = (None, condition, None, None)
    _ENTRIES[key] = entry
    return entry


def _tokens(value: str) -> list[str]:
    """Split a value at the white space outside its parentheses.

    Args:
        value: The value as written.

    Returns:
        Its parts.
    """
    if "(" not in value:
        return value.split()
    tokens = []
    depth = start = 0
    for index, char in enumerate(value):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char.isspace() and not depth:
            if index > start:
                tokens.append(value[start:index])
            start = index + 1
    if len(value) > start:
        tokens.append(value[start:])
    return tokens


def _split(value: str) -> list[str] | None:
    """Split the value of a shorthand into the values of its longhands.

    Args:
        value: The value as written.

    Returns:
        The values, or None when the value cannot be split safely: a custom
        property may hold several values unless it is a design token known to
        hold one, and a slash or a comma separates groups of them.
    """
    if "/" in value or "," in value or "!" in value:
        return None
    tokens = _tokens(value)
    if "var(" in value:
        single = _SINGLE_VALUE_VARS
        for token in tokens:
            if "var(" in token and token not in single:
                return None
    return tokens


def _cannot_split(name: str, key: str, value: Any, instead: str) -> StyleError:
    """Word the error for a shorthand that has to be split and cannot be.

    Args:
        name: The display name of the component.
        key: The style key as written.
        value: Its value.
        instead: The styles to set in its place.

    Returns:
        The error to raise.
    """
    if isinstance(value, Var):
        return StyleError(
            f'{name}: style "{key}" is bound to state, but rx.ui styles split '
            f"this shorthand into longhands at compile time. Bind {instead} "
            "instead."
        )
    return StyleError(
        f'{name}: style "{key}" has the value "{value}", which rx.ui styles '
        f"cannot split into longhands. Set {instead} instead."
    )


def _border(sides: tuple[str, ...]) -> Callable[[str, str, Any], list[tuple[str, Any]]]:
    """Make the expansion of a border shorthand.

    Args:
        sides: The sides the shorthand sets, such as ``borderTop``.

    Returns:
        A function that splits a value into the width, style and color of
        every side. A part the value leaves out gets its initial value, as it
        does in CSS, so that the shorthand replaces what an earlier style set.
    """
    instead = "its width, style and color"

    def expand(name: str, key: str, value: Any) -> list[tuple[str, Any]]:
        """Split one value of the shorthand.

        Args:
            name: The display name of the component, for error messages.
            key: The style key as written, for error messages.
            value: The value as written.

        Returns:
            The longhands and their values.

        Raises:
            StyleError: If the value is bound to state or its parts cannot be
                told apart.
        """
        width = style = color = None
        if value.__class__ is str:
            for token in _tokens(value):
                lowered = token.lower()
                if style is None and lowered in _BORDER_STYLES:
                    style = token
                elif width is None and _BORDER_WIDTH.fullmatch(lowered):
                    width = token
                elif (
                    color is None
                    and "!" not in token
                    and lowered not in _BORDER_STYLES
                    and not _BORDER_WIDTH.fullmatch(lowered)
                ):
                    color = token
                else:
                    raise _cannot_split(name, key, value, instead)
        elif value is None:
            return [
                (f"{side}{part}", None)
                for side in sides
                for part in ("Width", "Style", "Color")
            ]
        elif isinstance(value, Var):
            raise _cannot_split(name, key, value, instead)
        else:
            width = value
        parts = (
            ("Width", "medium" if width is None else width),
            ("Style", style or "none"),
            ("Color", color or "currentcolor"),
        )
        return [(f"{side}{part}", item) for side in sides for part, item in parts]

    return expand


def _background(name: str, key: str, value: Any) -> list[tuple[str, Any]]:
    """Split the background shorthand, which StyleX does not compile.

    Args:
        name: The display name of the component, for error messages.
        key: The style key as written, for error messages.
        value: A color or an image. A custom property is read as a color.

    Returns:
        The color and the image, one of them reset as the shorthand does.

    Raises:
        StyleError: If the value is bound to state or holds more than one of
            the two.
    """
    if value is None:
        return [("backgroundColor", None), ("backgroundImage", None)]
    if value.__class__ is str:
        tokens = _tokens(value)
        if len(tokens) == 1 and "!" not in value:
            if _IMAGE.match(value.strip().lower()):
                return [("backgroundColor", "transparent"), ("backgroundImage", value)]
            return [("backgroundColor", value), ("backgroundImage", "none")]
    raise _cannot_split(
        name,
        key,
        value,
        "background_color, background_image and its other longhands",
    )


def _unsupported(instead: str) -> Callable[[str, str, Any], list[tuple[str, Any]]]:
    """Make the refusal of a shorthand that cannot be compiled or split.

    Args:
        instead: The styles to set in its place.

    Returns:
        A function that raises for any value.
    """

    def expand(name: str, key: str, value: Any) -> list[tuple[str, Any]]:
        """Refuse the shorthand.

        Args:
            name: The display name of the component.
            key: The style key as written.
            value: The value as written.

        Raises:
            StyleError: Always.
        """
        msg = (
            f'{name}: style "{key}" is a shorthand that rx.ui styles do not '
            f"support. Set {instead} instead."
        )
        raise StyleError(msg)

    return expand


def _entries() -> tuple[dict[str, _Entry], dict[str, _Entry]]:
    """Build the tables of style keys from the generated CSS properties.

    Returns:
        How each key is lowered, by the snake_case key a user writes and by
        the camelCase name of the property.
    """
    by_key: dict[str, _Entry] = {}
    by_camel: dict[str, _Entry] = {}
    custom = {
        "background": _background,
        **{camel: _border(sides) for camel, sides in _BORDERS.items()},
        **{camel: _unsupported(instead) for camel, instead in _UNSUPPORTED.items()},
    }
    for key, camel in CSS_PROPS.items():
        if camel in custom:
            entry = (camel, (), custom[camel], None)
        elif camel in _EXPANSIONS:
            entry = (camel, *_EXPANSIONS[camel], _REPLACES[camel])
        else:
            entry = (camel, None, None, _REPLACES.get(camel))
        by_key[key] = by_camel[camel] = entry
    for camel, targets in _REFLEX_KEYS.items():
        entry = (camel, targets, None, None)
        by_key[format.to_snake_case(camel)] = by_camel[camel] = entry
    by_key["bg"] = by_camel["bg"] = by_camel["background"]
    return by_key, by_camel


# How every style key seen so far is lowered. It starts with the snake_case
# keys and learns the other spellings and the conditions as styles use them.
_ENTRIES, _BY_CAMEL = _entries()
# The snake_case keys, to suggest one for a key that is misspelt.
_SNAKE_KEYS = tuple(_ENTRIES)


def _put(
    out: dict[str, LoweredValue], prop: str, path: tuple[str, ...], value: Any
) -> None:
    """Give a property its value under the conditions of a path.

    Args:
        out: The lowered style being built.
        prop: The camelCase property.
        path: The conditions the value applies under, outermost first.
        value: The lowered value.
    """
    node = out.get(prop, _MISSING)
    if not path:
        if node.__class__ is dict and "default" not in node:
            out[prop] = {"default": value, **node}
        else:
            out[prop] = value
        return
    if node.__class__ is not dict:
        node = out[prop] = {} if node is _MISSING else {"default": node}
    for condition in path[:-1]:
        child = node.get(condition, _MISSING)
        if child.__class__ is not dict:
            child = node[condition] = {} if child is _MISSING else {"default": child}
        node = child
    last = path[-1]
    child: Any = node.get(last)
    if child.__class__ is dict and "default" not in child:
        node[last] = {"default": value, **child}
    else:
        node[last] = value


def _leaf(
    name: str,
    key: str,
    entry: _Entry,
    value: Any,
    path: tuple[str, ...],
    out: dict[str, LoweredValue],
    replaced: list[str],
) -> None:
    """Lower one literal or Var, expanding the shorthand it is given to.

    Args:
        name: The display name of the component, for error messages.
        key: The style key as written, for error messages.
        entry: How the style key is lowered.
        value: A literal, a Var or None.
        path: The conditions the value applies under.
        out: The lowered style being built.
        replaced: The properties of earlier styles this style replaces.
    """
    camel, targets, spread, replaces = entry
    if targets is not None:
        if spread is None:
            for target in targets:
                _put(out, target, path, value)
            return
        if spread.__class__ is not dict:
            for target, item in spread(name, key, value):
                _put(out, target, path, item)
            return
        if value.__class__ is str:
            tokens = _split(value)
            if tokens:
                order = spread.get(len(tokens))
                if order is not None:
                    for target, index in zip(targets, order, strict=True):
                        _put(out, target, path, tokens[index])
                    return
        elif not isinstance(value, Var):
            for target in targets:
                _put(out, target, path, value)
            return
    _put(out, camel, path, value)
    if replaces is not None and not path:
        replaced.extend(replaces)


def _value(
    name: str,
    key: str,
    entry: _Entry,
    value: Any,
    path: tuple[str, ...],
    out: dict[str, LoweredValue],
    replaced: list[str],
) -> None:
    """Lower the value of one CSS property.

    Args:
        name: The display name of the component, for error messages.
        key: The style key as written, for error messages.
        entry: How the style key is lowered.
        value: The value as written.
        path: The conditions the value applies under.
        out: The lowered style being built.
        replaced: The properties of earlier styles this style replaces.

    Raises:
        StyleError: If the value is not one a style can take.
    """
    cls = value.__class__
    if cls is str:
        if REFLEX_VAR_OPENING_TAG in value:
            value = LiteralVar.create(value)
        elif entry[1] is None:
            _put(out, entry[0], path, value)
            if entry[3] is not None and not path:
                replaced.extend(entry[3])
            return
    elif cls is int or cls is float or value is None:
        pass
    elif isinstance(value, Color):
        if (
            value.color.__class__ is not str
            or value.shade.__class__ is not int
            or value.alpha.__class__ is not bool
        ):
            _leaf(name, key, entry, LiteralVar.create(value), path, out, replaced)
            return
        value = f"{value}"
        if entry[2].__class__ is dict:
            # A color is one value, so every longhand takes its custom property.
            for target in entry[1]:
                _put(out, target, path, value)
            return
    elif isinstance(value, Mapping):
        named = isinstance(value, Breakpoints)
        for condition, item in value.items():
            if condition == "default" or condition == "initial":
                inner = path
            elif condition in breakpoint_names:
                width = breakpoints_values[breakpoint_names.index(condition)]
                inner = (*path, media_query(width))
            else:
                entry_ = _ENTRIES.get(condition)
                text = (
                    entry_[1]
                    if entry_ is not None and entry_[0] is None
                    else _value_condition(name, key, condition, named)
                )
                inner = (*path, text)
            _value(name, key, entry, item, inner, out, replaced)
        return
    elif cls is list or cls is tuple:
        if len(value) > len(breakpoints_values) + 1:
            msg = (
                f'{name}: style "{key}" has {len(value)} responsive values, but '
                f"there are only {len(breakpoints_values) + 1} breakpoints."
            )
            raise StyleError(msg)
        for index, item in enumerate(value):
            if item is not None:
                inner = (
                    (*path, media_query(breakpoints_values[index - 1]))
                    if index
                    else path
                )
                _value(name, key, entry, item, inner, out, replaced)
        return
    elif not isinstance(value, Var):
        msg = (
            f'{name}: style "{key}" cannot take a value of type '
            f"{cls.__name__}. Use a string, a number, a Var, a responsive list "
            "or a dict of conditions."
        )
        raise StyleError(msg)
    if isinstance(value, LiteralVar) and value._get_all_var_data() is None:
        literal = value._var_value
        if literal.__class__ in (str, int, float) or isinstance(literal, Color):
            _value(name, key, entry, literal, path, out, replaced)
            return
    _leaf(name, key, entry, value, path, out, replaced)


def _value_condition(name: str, key: str, condition: Any, named: bool) -> str:
    """Read a key of a property's value as the condition its item applies under.

    Args:
        name: The display name of the component, for error messages.
        key: The style key the value belongs to, for error messages.
        condition: The key inside the value.
        named: Whether the value is an ``rx.breakpoints``, whose other keys
            are the widths of custom breakpoints.

    Returns:
        The condition as StyleX takes it.

    Raises:
        StyleError: If the key is not a condition.
    """
    if not isinstance(condition, str):
        text = None
    elif named and condition[:1] not in (":", "@", "[", "_", "&"):
        return media_query(condition)
    else:
        text = _condition(name, condition)
    if text is None:
        msg = (
            f'{name}: style "{key}" is given a value under "{condition}", which '
            'is not a condition. Use "default", a pseudo-class such as '
            '":hover", an at-rule such as "@media (min-width: 48em)" or the '
            "name of a breakpoint."
        )
        raise StyleError(msg)
    _ENTRIES[condition] = (None, text, None, None)
    return text


def _block(
    name: str,
    style: Mapping[str, Any],
    path: tuple[str, ...],
    out: dict[str, LoweredValue],
    replaced: list[str],
) -> None:
    """Lower a dict of styles into the style being built.

    Args:
        name: The display name of the component, for error messages.
        style: The styles as written.
        path: The conditions the styles apply under.
        out: The lowered style being built.
        replaced: The properties of earlier styles this style replaces.

    Raises:
        StyleError: If a key or a value is not one a style can take.
    """
    entries = _ENTRIES
    for key, value in style.items():
        entry = entries.get(key) or _resolve(name, key)
        if entry[0] is not None:
            _value(name, key, entry, value, path, out, replaced)
        elif isinstance(value, Var):
            msg = (
                f'{name}: style key "{key}" is bound to state, but the styles '
                "under a condition are compiled ahead of time. Bind the values "
                "of its properties instead."
            )
            raise StyleError(msg)
        elif not isinstance(value, Mapping) or isinstance(value, Breakpoints):
            msg = (
                f'{name}: style key "{key}" is a condition, so its value must '
                f"be a dict of styles, not {type(value).__name__}."
            )
            raise StyleError(msg)
        else:
            _block(name, value, (*path, entry[1]), out, replaced)


def _space(value: Any) -> Any:
    """Read a step of the space scale.

    Args:
        value: A step from "0" to "9", negative for a margin, or any CSS value.

    Returns:
        The custom property of the step, or the value as given.
    """
    if value.__class__ is str:
        negative = value[:1] == "-"
        step = value[1:] if negative else value
        if len(step) == 1 and step.isdigit():
            if step == "0":
                return "0"
            return (
                f"calc(-1 * var(--space-{step}))"
                if negative
                else f"var(--space-{step})"
            )
    return value


def _as_written(value: Any) -> Any:
    """Read a value of a layout prop that takes the keywords of CSS.

    Args:
        value: The value.

    Returns:
        The value as given.
    """
    return value


def _tracks(value: Any) -> Any:
    """Read a number of grid tracks.

    Args:
        value: A count such as "3", or any CSS value.

    Returns:
        That many tracks of equal size, or the value as given.
    """
    if value.__class__ is str and value.isdigit():
        return f"repeat({value}, minmax(0, 1fr))"
    return value


def _keywords(names: dict[str, str]) -> Callable[[Any], Any]:
    """Make the reading of a layout prop whose keywords are not the ones of CSS.

    Args:
        names: The CSS keyword of each keyword of the prop that differs.

    Returns:
        A function that reads one value of the prop.
    """
    return lambda value: names.get(value, value)


_ALIGN = {"start": "flex-start", "end": "flex-end"}

# The breakpoints of a prop, which are those of Radix Themes whatever the
# breakpoints of the app: a responsive prop of an rx component is resolved by
# the Radix stylesheet. A responsive value in a style follows the app instead.
PROP_BREAKPOINTS: dict[str, str] = {
    "xs": "@media (min-width: 520px)",
    "sm": "@media (min-width: 768px)",
    "md": "@media (min-width: 1024px)",
    "lg": "@media (min-width: 1280px)",
    "xl": "@media (min-width: 1640px)",
}
_PROP_MEDIA = ("default", *PROP_BREAKPOINTS.values())


def prop_breakpoint(name: str, prop: str, breakpoint: Any) -> str:
    """Read a key of a responsive prop as the condition its value applies under.

    Args:
        name: The display name of the component, for error messages.
        prop: The prop.
        breakpoint: The key: ``initial`` or the name of a breakpoint.

    Returns:
        ``default``, or the media query of the breakpoint.

    Raises:
        StyleError: If the key is not a breakpoint of Radix Themes.
    """
    if breakpoint == "initial":
        return "default"
    try:
        return PROP_BREAKPOINTS[breakpoint]
    except (KeyError, TypeError):
        msg = (
            f'{name}: prop "{prop}" is given a value under "{breakpoint}", '
            'which is not a breakpoint. Use "initial", "xs", "sm", "md", "lg" '
            'or "xl", or set a style, which takes any media query.'
        )
        raise StyleError(msg) from None

# The layout props: the style each one stands for, the longhands it sets, and
# how its values are read.
_LAYOUT: dict[str, tuple[str, tuple[str, ...], Callable[[Any], Any]]] = {
    "p": ("padding", _sides("padding"), _space),
    "px": ("padding_x", ("paddingLeft", "paddingRight"), _space),
    "py": ("padding_y", ("paddingTop", "paddingBottom"), _space),
    "pt": ("padding_top", ("paddingTop",), _space),
    "pr": ("padding_right", ("paddingRight",), _space),
    "pb": ("padding_bottom", ("paddingBottom",), _space),
    "pl": ("padding_left", ("paddingLeft",), _space),
    "m": ("margin", _sides("margin"), _space),
    "mx": ("margin_x", ("marginLeft", "marginRight"), _space),
    "my": ("margin_y", ("marginTop", "marginBottom"), _space),
    "mt": ("margin_top", ("marginTop",), _space),
    "mr": ("margin_right", ("marginRight",), _space),
    "mb": ("margin_bottom", ("marginBottom",), _space),
    "ml": ("margin_left", ("marginLeft",), _space),
    "gap": ("gap", ("rowGap", "columnGap"), _space),
    "spacing": ("gap", ("rowGap", "columnGap"), _space),
    "gap_x": ("column_gap", ("columnGap",), _space),
    "gap_y": ("row_gap", ("rowGap",), _space),
    "spacing_x": ("column_gap", ("columnGap",), _space),
    "spacing_y": ("row_gap", ("rowGap",), _space),
    "columns": ("grid_template_columns", ("gridTemplateColumns",), _tracks),
    "rows": ("grid_template_rows", ("gridTemplateRows",), _tracks),
    "direction": ("flex_direction", ("flexDirection",), _as_written),
    "wrap": ("flex_wrap", ("flexWrap",), _as_written),
    "align": ("align_items", ("alignItems",), _keywords(_ALIGN)),
    "justify": (
        "justify_content",
        ("justifyContent",),
        _keywords({**_ALIGN, "between": "space-between"}),
    ),
    "flow": (
        "grid_auto_flow",
        ("gridAutoFlow",),
        _keywords({"row-dense": "row dense", "column-dense": "column dense"}),
    ),
}

# The props that set layout styles through a scale rather than a CSS value.
LAYOUT_PROPS: frozenset[str] = frozenset(_LAYOUT)


def _read_layout(name: str, prop: str, value: Any, read: Callable[[Any], Any]) -> Any:
    """Read the values of a layout prop, whatever their breakpoints.

    Args:
        name: The display name of the component, for error messages.
        prop: The layout prop.
        value: Its value: one, a list of them or a dict of them by breakpoint.
        read: How one value is read.

    Returns:
        A CSS value, or a dict of them by the media query of each breakpoint.

    Raises:
        StyleError: If a value that has to be read is bound to state, or a
            value is given under a key that is not a breakpoint.
    """
    if value.__class__ is str:
        return read(value)
    if isinstance(value, Mapping):
        return {
            prop_breakpoint(name, prop, key): _read_layout(name, prop, item, read)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        if len(value) > len(_PROP_MEDIA):
            msg = (
                f'{name}: layout prop "{prop}" has {len(value)} responsive '
                f"values, but there are only {len(_PROP_MEDIA)} breakpoints."
            )
            raise StyleError(msg)
        return {
            media: _read_layout(name, prop, item, read)
            for media, item in zip(_PROP_MEDIA, value, strict=False)
            if item is not None
        }
    if isinstance(value, Var):
        if isinstance(value, LiteralVar) and value._get_all_var_data() is None:
            return _read_layout(name, prop, value._var_value, read)
        if read is _as_written:
            return value
        msg = (
            f'{name}: layout prop "{prop}" is bound to state, but its values '
            f'are read at compile time. Bind the "{_LAYOUT[prop][0]}" style '
            "instead, which takes any CSS value."
        )
        raise StyleError(msg)
    return read(value)


def lower_layer(
    name: str,
    style: Mapping[str, Any] | None = None,
    layout: Mapping[str, Any] | None = None,
) -> Layer:
    """Lower one style, keeping what merging it over another style needs.

    Args:
        name: The display name of the component, for error messages.
        style: The styles as written.
        layout: Layout props, lowered before the styles.

    Returns:
        The lowered properties, which may hold None for a property the style
        unsets, and the properties of earlier styles it replaces.

    Raises:
        StyleError: If the style or a layout prop cannot be compiled.
    """
    out: dict[str, LoweredValue] = {}
    replaced: list[str] = []
    if layout:
        for prop, value in layout.items():
            if value is None:
                continue
            try:
                key, targets, read = _LAYOUT[prop]
            except KeyError:
                msg = (
                    f'{name}: unknown layout prop "{prop}".'
                    f"{suggest(prop, sorted(_LAYOUT))}"
                )
                raise StyleError(msg) from None
            value = _read_layout(name, prop, value, read)
            _value(name, key, (key, targets, None, None), value, (), out, replaced)
    if style:
        _block(name, style, (), out, replaced)
    return out, tuple(replaced)


def _overlay(old: Any, new: dict[str, Any]) -> dict[str, Any]:
    """Add the conditions of a later style to the value of an earlier one.

    Args:
        old: The earlier value of the property.
        new: A condition map without a default.

    Returns:
        A condition map holding both.
    """
    merged = dict(old) if old.__class__ is dict else {"default": old}
    for condition, value in new.items():
        if value.__class__ is dict and "default" not in value and condition in merged:
            merged[condition] = _overlay(merged[condition], value)
        else:
            merged[condition] = value
    return merged


def apply_layer(target: dict[str, LoweredValue], layer: Layer) -> None:
    """Merge a later style over the properties merged so far, in place.

    A property the later style sets replaces the earlier value, conditions
    included. A property it only sets under a condition, as a ``_hover`` block
    does, keeps the earlier value everywhere else.

    Args:
        target: The properties merged so far.
        layer: The later style.
    """
    props, replaced = layer
    for prop in replaced:
        target.pop(prop, None)
    for prop, value in props.items():
        if value.__class__ is dict and "default" not in value:
            old = target.get(prop)
            target[prop] = value if old is None else _overlay(old, value)
        else:
            target[prop] = value


def freeze(value: LoweredValue) -> Any:
    """Turn a lowered value into one that can be compared and hashed.

    A Var builds an expression when compared, so it stands in as its identity.

    Args:
        value: The lowered value.

    Returns:
        The value, with every dict and Var inside it replaced.
    """
    cls = value.__class__
    if cls is str or cls is int or cls is float or value is None:
        return value
    if cls is dict:
        return tuple([(key, freeze(item)) for key, item in value.items()])
    if cls is Lowered:
        return value.key
    return (Var, value._hash_key())


def _modules(value: LoweredValue, found: set[str]) -> None:
    """Collect the modules that define the custom properties a value uses.

    Args:
        value: The lowered value.
        found: The modules found so far, added to in place.
    """
    if value.__class__ is str:
        if "var(--" in value:
            for match in _VAR_NAME.finditer(value):
                module = VAR_MODULES.get(match[1])
                if module is not None:
                    found.add(module)
    elif value.__class__ is dict:
        for item in value.values():
            _modules(item, found)


class Lowered:
    """A style in the form StyleX compiles.

    Two of them are equal, and hash the same, when they would compile to the
    same declaration, so one can be the key that declarations are shared by.
    The order of the properties does not count.

    Attributes:
        style: The lowered value of each camelCase CSS property. Shared with
            every equal result: read it, never change it.
        imports: The modules to import so that the CSS of the custom
            properties the style uses is emitted, sorted.
        inline: A Var holding a whole dict of styles, to be set as the inline
            ``style`` of the element after the compiled ones.
    """

    __slots__ = ("_key", "imports", "inline", "style")

    def __init__(
        self,
        style: dict[str, LoweredValue],
        imports: tuple[str, ...] = (),
        inline: Var | None = None,
    ):
        """Hold a lowered style.

        Args:
            style: The lowered value of each camelCase CSS property.
            imports: The modules the style needs, sorted.
            inline: A Var holding a whole dict of styles.
        """
        self.style = style
        self.imports = imports
        self.inline = inline
        self._key = None

    @property
    def key(self) -> tuple[Any, ...]:
        """What the style is compared and hashed by.

        Returns:
            A hashable tuple that holds no Var.
        """
        key = self._key
        if key is None:
            key = self._key = (
                tuple(sorted([(prop, freeze(v)) for prop, v in self.style.items()])),
                self.imports,
                None if self.inline is None else self.inline._hash_key(),
            )
        return key

    def __eq__(self, other: object) -> bool:
        """Compare with another lowered style.

        Args:
            other: What to compare with.

        Returns:
            Whether both would compile to the same declaration.
        """
        return isinstance(other, Lowered) and self.key == other.key

    def __hash__(self) -> int:
        """Hash consistently with equality.

        Returns:
            The hash of the key.
        """
        return hash(self.key)

    def __repr__(self) -> str:
        """Show what the style holds.

        Returns:
            The constructor call that would rebuild it.
        """
        return f"Lowered({self.style!r}, {self.imports!r}, {self.inline!r})"


EMPTY = Lowered({})


def finish(
    props: dict[str, LoweredValue], inline: Var | None = None, unset: bool = False
) -> Lowered:
    """Wrap merged properties as a lowered style.

    Args:
        props: The merged properties, which the result takes over.
        inline: A Var holding a whole dict of styles.
        unset: Whether to keep the properties set to None. They are dropped
            otherwise, there being nothing before the style for them to unset.

    Returns:
        The lowered style, with the modules its values need.
    """
    found: set[str] = set()
    dropped = False
    for value in props.values():
        cls = value.__class__
        if cls is str:
            if "var(--" in value:
                _modules(value, found)
        elif cls is dict:
            _modules(value, found)
        elif value is None:
            dropped = True
    if dropped and not unset:
        props = {prop: value for prop, value in props.items() if value is not None}
    if not props and inline is None:
        return EMPTY
    return Lowered(props, tuple(sorted(found)) if found else (), inline)


def lower(
    name: str,
    style: StyleProps | Mapping[str, Any] | Var | None = None,
    layout: Mapping[str, Any] | None = None,
) -> Lowered:
    """Lower the style of one element into the form StyleX compiles.

    Args:
        name: The display name of the component, such as ``"rx.ui.card"``,
            which starts every error message.
        style: The styles as a user writes them, or a Var holding a whole dict
            of them, which becomes the inline style of the element.
        layout: Layout props such as ``p`` and ``gap``, lowered to styles that
            the ones in ``style`` are merged over.

    Returns:
        The lowered style.

    Raises:
        StyleError: If a key, a value or a layout prop cannot be compiled.
    """
    if isinstance(style, Var):
        if not layout:
            return Lowered({}, (), style)
        return finish(lower_layer(name, None, layout)[0], style)
    if not layout:
        return finish(lower_layer(name, style)[0])
    props, _ = lower_layer(name, None, layout)
    apply_layer(props, lower_layer(name, style))
    return finish(props)
