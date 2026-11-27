"""Turn the merged styles of an element into the StyleX source of its module.

StyleX folds ``stylex.props(...)`` into a ``className`` string only when the
style is declared in the module that makes the call and the call has nothing
in it that is known at runtime. Everything here is shaped to keep it that way,
so that no element needs the StyleX runtime:

- Every distinct style becomes a declaration of its own, named after its
  content, followed by a constant that holds its folded class names. The
  compiler deduplicates custom code by its text: elements that share a style
  share one declaration and one string, in whichever module renders them.
- A value bound to state is declared as ``var(--vN)`` and the element sets
  that custom property in its inline ``style``, so the declaration stays
  literal.
- A variant prop bound to state gets one style per value, each holding the
  whole value of the properties the prop changes. They are folded into a
  table of class names at module level, which the element indexes with the
  value of the prop.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any

from reflex_base.utils.types import safe_issubclass
from reflex_base.vars.base import Var

from reflex_components_ui.style.lower import Keyframes, StyleError
from reflex_components_ui.style.merge import Alternatives, Merged

# The key under which a declaration holds the style every instance has.
_KEY = "s"

# Stands for the name of a declaration until its content gives it one. JSON
# escapes the character, so no style can hold it.
_NAME = "\0"

# The properties whose numbers are not lengths, as StyleX lists them: it
# appends "px" to a literal number of any other property, and so does the
# value of a custom property that stands for one.
UNITLESS: frozenset[str] = frozenset((
    "WebkitLineClamp",
    "animationIterationCount",
    "aspectRatio",
    "borderImageOutset",
    "borderImageSlice",
    "borderImageWidth",
    "columnCount",
    "counterReset",
    "counterSet",
    "fillOpacity",
    "flex",
    "flexGrow",
    "flexOrder",
    "flexShrink",
    "floodOpacity",
    "fontSizeAdjust",
    "fontWeight",
    "gridArea",
    "gridColumn",
    "gridColumnEnd",
    "gridColumnStart",
    "gridRow",
    "gridRowEnd",
    "gridRowStart",
    "hyphenateLimitChars",
    "lineClamp",
    "lineHeight",
    "maskBorderOutset",
    "maskBorderSlice",
    "maskBorderWidth",
    "mathDepth",
    "opacity",
    "order",
    "orphans",
    "rotate",
    "scale",
    "shapeImageThreshold",
    "stopOpacity",
    "strokeDasharray",
    "strokeDashoffset",
    "strokeMiterlimit",
    "strokeOpacity",
    "strokeWidth",
    "tabSize",
    "widows",
    "zIndex",
    "zoom",
))

_NOT_RENDERED_IN_PAGE = (
    "which a component rendered from state cannot apply: its code is evaluated "
    "in the browser and never reaches the StyleX compiler."
)
_RENDER_IN_PAGE = "render the component in a page and show it with rx.cond."


@dataclasses.dataclass(frozen=True, slots=True)
class Emitted:
    """The StyleX source of the styles of one element.

    Attributes:
        declaration: The module-level statements that declare the styles and
            fold them into class names, or None when the element has none.
        classes: The constant holding the class names of the style every
            instance has, or None when there is none.
        lookups: Expressions that each give the class names one group of
            state-bound props selects.
        variables: The custom properties the element sets in its inline
            style, as the entries of an object literal.
        inline: A Var holding a whole dict of styles, spread into the inline
            style after the custom properties.
        imports: The modules to import for their CSS, sorted.
        vars: Every Var the expressions above read, for the hooks and imports
            they bring.
    """

    declaration: str | None = None
    classes: str | None = None
    lookups: tuple[str, ...] = ()
    variables: tuple[str, ...] = ()
    inline: Var | None = None
    imports: tuple[str, ...] = ()
    vars: tuple[Var, ...] = ()


_NOTHING = Emitted()


def style_object(emitted: Emitted) -> tuple[str, str] | None:
    """Name the compiled style every instance has, before it is folded.

    For what joins class names when the page loads: a theme is declared in a
    module of its own, so StyleX cannot fold a call that names one. StyleX
    drops a style that is only folded, and the build hands it nothing but the
    statements that start like a declaration, so the style is kept by one.

    Args:
        emitted: The StyleX source of the styles of one element.

    Returns:
        The statement to place after the declaration and the name it gives
        the style, or None when the element has none.
    """
    classes = emitted.classes
    if classes is None:
        return None
    name = classes.removesuffix("_c")
    return f"const {name}_o = {name}.{_KEY};", f"{name}_o"


# The name of every literal declaration emitted so far, by its source.
_NAMES: dict[str, str] = {}


def _name(source: str) -> str:
    """Name a declaration after its source.

    Named after the source rather than the styles: two declarations of one
    name in a module would not parse.

    Args:
        source: What the declaration holds.

    Returns:
        The name, the same for the same source.
    """
    name = _NAMES.get(source)
    if name is None:
        name = _NAMES[source] = "sx_" + hashlib.sha256(source.encode()).hexdigest()[:10]
    return name


class _Variables:
    """The custom properties that carry the state-bound values of an element.

    Attributes:
        names: The ``var(...)`` reference of each value, by the Var and
            whether its numbers are lengths.
        entries: The entries of the inline style that set them.
        vars: The Vars the entries read.
    """

    __slots__ = ("entries", "names", "vars")

    def __init__(self):
        """Start with no custom property."""
        self.names: dict[tuple[Any, bool], str] = {}
        self.entries: list[str] = []
        self.vars: list[Var] = []

    def reference(self, var: Var, prop: str) -> str:
        """Give a state-bound value a custom property.

        Args:
            var: The value.
            prop: The camelCase property it is the value of.

        Returns:
            The literal that stands for the value in the declaration.
        """
        lengths = prop not in UNITLESS and not prop.startswith("--")
        var_type = var._var_type
        if safe_issubclass(var_type, str):
            lengths = False
        key = (var._hash_key(), lengths)
        reference = self.names.get(key)
        if reference is None:
            name = f"--v{len(self.names)}"
            reference = self.names[key] = f"var({name})"
            # Parenthesized: the expression may be a conditional.
            expression = f"({var!s})"
            if lengths and (var_type is int or var_type is float):
                expression = f'{expression} + "px"'
            else:
                if lengths:
                    expression = (
                        f'((v) => typeof v === "number" ? v + "px" : v){expression}'
                    )
                # An unset value must not pick up the property of an ancestor.
                expression = f'{expression} ?? "initial"'
            self.entries.append(f'"{name}": {expression}')
            self.vars.append(var)
        return reference

    def literal(self, value: Any, prop: str) -> Any:
        """Replace the Vars of a lowered value with their custom properties.

        Args:
            value: The lowered value of a property.
            prop: The camelCase property.

        Returns:
            The value as StyleX compiles it.
        """
        cls = value.__class__
        if (
            cls is str
            or cls is int
            or cls is float
            or value is None
            or cls is Keyframes
        ):
            return value
        if cls is dict:
            return {
                condition: self.literal(item, prop) for condition, item in value.items()
            }
        return self.reference(value, prop)


def _lookup(table: dict[str, Any], depth: int) -> str:
    """Write the table that the values of a group of props index.

    Args:
        table: The class names of each value of the first prop, or the table
            of the props after it.
        depth: How many props are left to index by.

    Returns:
        An object literal without a prototype, so that only its own keys are
        found.
    """
    entries = ", ".join([
        f"{json.dumps(value)}: {item if depth == 1 else _lookup(item, depth - 1)}"
        for value, item in table.items()
    ])
    return f"{{ __proto__: null, {entries} }}"


def _classes(key: str) -> str:
    """Write the expression StyleX folds into the class names of a style.

    Args:
        key: The key of the style in its declaration.

    Returns:
        The expression, which is a string once the module is compiled.
    """
    return f"stylex.props({_NAME}.{key}).className"


def _alternatives(
    alternatives: Alternatives,
    index: int,
    static: dict[str, Any],
    variables: _Variables,
    styles: dict[str, Any],
    tables: list[str],
) -> str:
    """Declare the styles of a group of state-bound props.

    Each value gets the whole value of every property the group changes, so
    that its class names replace those of the other values rather than
    override them. The properties are taken out of the style every instance
    has.

    Args:
        alternatives: The styles the values of the props select.
        index: The position of the group among those of the element.
        static: The style of the element without the props, changed in place.
        variables: The custom properties of the element.
        styles: The styles of the declaration, added to in place.
        tables: The statements that follow the declaration, added to in place.

    Returns:
        The expression that gives the class names of the current values.
    """
    shared = {
        prop: static.pop(prop)
        for change in alternatives.values.values()
        for prop in change.style
        if prop in static
    }
    table: dict[str, Any] = {}
    for position, (combination, change) in enumerate(alternatives.values.items()):
        style = dict(shared)
        for prop, value in change.style.items():
            if value is None:
                style.pop(prop, None)
            else:
                style[prop] = variables.literal(value, prop)
        if style:
            key = f"a{index}_{position}"
            styles[key] = style
            classes = _classes(key)
        else:
            classes = '""'
        node = table
        for value in combination[:-1]:
            node = node.setdefault(value, {})
        node[combination[-1]] = classes
    name = f"{_NAME}_{index}"
    tables.append(f"const {name} = {_lookup(table, len(alternatives.props))};")
    if shared:
        key = f"a{index}"
        styles[key] = shared
        fallback = f"{name}d"
        tables.append(f"const {fallback} = {_classes(key)};")
    else:
        fallback = '""'
    indexed = "?.".join([f"[{var!s}]" for var in alternatives.vars])
    return f"({name}{indexed} ?? {fallback})"


def _emit(merged: Merged) -> Emitted:
    """Emit styles that hold a value or a prop bound to state.

    Args:
        merged: The merged styles of one element.

    Returns:
        The declaration, with the expressions and Vars the element needs.
    """
    lowered = merged.style
    variables = _Variables()
    static = {
        prop: variables.literal(value, prop) for prop, value in lowered.style.items()
    }
    styles: dict[str, Any] = {}
    tables: list[str] = []
    imports = set(lowered.imports)
    vars: list[Var] = []
    lookups = []
    for index, alternatives in enumerate(merged.dynamic):
        lookups.append(
            _alternatives(alternatives, index, static, variables, styles, tables)
        )
        vars.extend(alternatives.vars)
        for change in alternatives.values.values():
            imports.update(change.imports)
    if static:
        styles = {_KEY: static, **styles}
        tables.insert(0, f"const {_NAME}_c = {_classes(_KEY)};")
    declaration = classes = None
    if styles:
        animations: dict[Keyframes, str] = {}

        def reference(value: Any) -> str:
            """Stand in for the keyframes of a style until they have a name.

            Args:
                value: What JSON cannot hold: the keyframes of an animation.

            Returns:
                A marker that no style can hold, as JSON escapes it.
            """
            return animations.setdefault(value, f"\1{len(animations)}\1")

        entries = ", ".join([
            f"{key}: {json.dumps(style, ensure_ascii=False, default=reference)}"
            for key, style in styles.items()
        ])
        for position, frames in enumerate(animations):
            # StyleX compiles a reference to keyframes of the same module.
            entries = entries.replace(
                f'"\\u0001{position}\\u0001"', f"{_NAME}_k{position}"
            )
        template = "\n".join([
            *[
                f"const {_NAME}_k{position} = stylex.keyframes({frames.source});"
                for position, frames in enumerate(animations)
            ],
            f"const {_NAME} = stylex.create({{ {entries} }});",
            *tables,
        ])
        name = _name(template)
        declaration = template.replace(_NAME, name)
        lookups = [lookup.replace(_NAME, name) for lookup in lookups]
        if static:
            classes = f"{name}_c"
    if lowered.inline is not None:
        vars.append(lowered.inline)
    return Emitted(
        declaration,
        classes,
        tuple(lookups),
        tuple(variables.entries),
        lowered.inline,
        tuple(sorted(imports)),
        (*variables.vars, *vars),
    )


def emit(merged: Merged) -> Emitted:
    """Emit the StyleX source of the merged styles of one element.

    Args:
        merged: The merged styles of the element. Those of its parts are
            emitted on their own, for the elements that render them.

    Returns:
        What the module that renders the element declares, and what the
        element reads from it.
    """
    lowered = merged.style
    if merged.dynamic or lowered.inline is not None:
        return _emit(merged)
    style = lowered.style
    if not style:
        return _NOTHING
    if "animationName" in style:
        return _emit(merged)
    try:
        source = json.dumps(style, ensure_ascii=False)
    except TypeError:
        # A value is a Var.
        return _emit(merged)
    name = _name(source)
    return Emitted(
        f"const {name} = stylex.create({{ {_KEY}: {source} }});\n"
        f"const {name}_c = stylex.props({name}.{_KEY}).className;",
        f"{name}_c",
        imports=lowered.imports,
    )


def inline(merged: Merged, component: str) -> dict[str, str | int | float]:
    """Turn the merged styles of an element into an inline ``style``.

    The fallback for code that is evaluated in the browser and never reaches
    the StyleX compiler. An inline style has no conditions, and nothing bound
    to state is compiled for it.

    Args:
        merged: The merged styles of the element.
        component: The name of the component, for error messages.

    Returns:
        The style, every value a literal.

    Raises:
        StyleError: If a value has conditions, or a value, a prop or the
            whole style is bound to state.
    """
    lowered = merged.style
    if merged.dynamic:
        props = ", ".join([
            f'"{prop}"'
            for alternatives in merged.dynamic
            for prop in alternatives.props
        ])
        msg = (
            f"{component}: the props {props} select a style and are bound to "
            f"state, {_NOT_RENDERED_IN_PAGE} Give them literal values there, or "
            f"{_RENDER_IN_PAGE}"
        )
        raise StyleError(msg)
    if lowered.inline is not None:
        msg = (
            f"{component}: the style is a Var, {_NOT_RENDERED_IN_PAGE} Use a "
            f"dict of literal values there, or {_RENDER_IN_PAGE}"
        )
        raise StyleError(msg)
    for prop, value in lowered.style.items():
        if value.__class__ is dict:
            conditions = ", ".join([f'"{condition}"' for condition in value])
            msg = (
                f'{component}: the style "{prop}" has conditions ({conditions}), '
                f"{_NOT_RENDERED_IN_PAGE} Use an unconditional value there, or "
                f"{_RENDER_IN_PAGE}"
            )
            raise StyleError(msg)
        if value.__class__ is Keyframes:
            msg = (
                f'{component}: the style "{prop}" plays keyframes, '
                f"{_NOT_RENDERED_IN_PAGE} Leave the animation out there, or "
                f"{_RENDER_IN_PAGE}"
            )
            raise StyleError(msg)
        if isinstance(value, Var):
            msg = (
                f'{component}: the style "{prop}" is bound to state, '
                f"{_NOT_RENDERED_IN_PAGE} Use a literal value there, or "
                f"{_RENDER_IN_PAGE}"
            )
            raise StyleError(msg)
    return lowered.style
