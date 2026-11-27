"""Merge the style table of a component with the style of one element.

The styles are merged by property and the last one wins: the base of the
table, each variant the props of the element select, the compound styles that
match, the layout props and then the style the user wrote. The result is what
the compiler emits as StyleX declarations, so nothing has to be overridden in
the browser.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import product
from typing import TYPE_CHECKING, Any, TypedDict

from reflex_base.breakpoints import breakpoints_values
from reflex_base.vars.base import LiteralVar, Var

from reflex_components_ui.style.lower import (
    Layer,
    Lowered,
    LoweredValue,
    StyleError,
    apply_layer,
    finish,
    freeze,
    lower_layer,
)

if TYPE_CHECKING:
    from reflex_components_ui.style._css_props import StyleProps


class CompoundStyle(TypedDict):
    """Styles for an element whose props have a combination of values."""

    props: dict[str, str]
    style: StyleProps


class ComponentStyles(TypedDict, total=False):
    """The look of a component: a table of styles selected by its props.

    A variant is keyed by the name of a prop and then by its values, written
    as strings: ``"true"`` and ``"false"`` for a boolean prop.
    """

    base: StyleProps
    variants: dict[str, dict[str, StyleProps]]
    compound: list[CompoundStyle]
    parts: dict[str, ComponentStyles]


_TABLE_KEYS = frozenset(("base", "variants", "compound", "parts"))
_NO_PROPS: Mapping[str, Any] = {}


class Alternatives:
    """The styles of the props of an element that are bound to state.

    The compiler emits one declaration per entry of ``values`` and the page
    picks one at runtime, by the values the Vars then have, applying it after
    the style of the element. Each entry holds only what differs from that
    style, with None for a property to unset. Props that set the same
    property, or that a compound style combines, are grouped so that every
    group can be picked independently of the others.

    Attributes:
        props: The names of the props.
        vars: The Var each prop is bound to.
        values: The style for each combination of values of the props that
            changes anything, keyed by the values in the order of ``props``.
    """

    __slots__ = ("_key", "props", "values", "vars")

    def __init__(
        self,
        props: tuple[str, ...],
        vars: tuple[Var, ...],
        values: dict[tuple[str, ...], Lowered],
    ):
        """Hold the alternatives of a group of props.

        Args:
            props: The names of the props.
            vars: The Var each prop is bound to.
            values: The style for each combination of their values.
        """
        self.props = props
        self.vars = vars
        self.values = values
        self._key = None

    @property
    def key(self) -> tuple[Any, ...]:
        """What the alternatives are compared and hashed by.

        Returns:
            A hashable tuple that holds no Var.
        """
        key = self._key
        if key is None:
            key = self._key = (
                self.props,
                tuple([var._hash_key() for var in self.vars]),
                tuple([(combo, style.key) for combo, style in self.values.items()]),
            )
        return key

    def __eq__(self, other: object) -> bool:
        """Compare with other alternatives.

        Args:
            other: What to compare with.

        Returns:
            Whether both hold the same styles for the same Vars.
        """
        return isinstance(other, Alternatives) and self.key == other.key

    def __hash__(self) -> int:
        """Hash consistently with equality.

        Returns:
            The hash of the key.
        """
        return hash(self.key)

    def __repr__(self) -> str:
        """Show what the alternatives hold.

        Returns:
            The constructor call that would rebuild them.
        """
        return f"Alternatives({self.props!r}, {self.vars!r}, {self.values!r})"


class Merged:
    """The styles of one element of a component and of its inner elements.

    Two of them are equal, and hash the same, when they would compile to the
    same declarations.

    Attributes:
        style: The style of the element, with every prop that has a value at
            compile time resolved.
        dynamic: The styles of the props that are bound to state, in the order
            they apply after ``style``.
        parts: The merged styles of each inner element, by its name.
    """

    __slots__ = ("_key", "dynamic", "parts", "style")

    def __init__(
        self,
        style: Lowered,
        dynamic: tuple[Alternatives, ...] = (),
        parts: Mapping[str, Merged] = _NO_PROPS,
    ):
        """Hold the merged styles of an element.

        Args:
            style: The style of the element.
            dynamic: The styles of the props that are bound to state.
            parts: The merged styles of each inner element.
        """
        self.style = style
        self.dynamic = dynamic
        self.parts = parts
        self._key = None

    @property
    def key(self) -> tuple[Any, ...]:
        """What the merged styles are compared and hashed by.

        Returns:
            A hashable tuple that holds no Var.
        """
        key = self._key
        if key is None:
            key = self._key = (
                self.style.key,
                tuple([alternatives.key for alternatives in self.dynamic]),
                tuple([(part, merged.key) for part, merged in self.parts.items()]),
            )
        return key

    def __eq__(self, other: object) -> bool:
        """Compare with other merged styles.

        Args:
            other: What to compare with.

        Returns:
            Whether both would compile to the same declarations.
        """
        return isinstance(other, Merged) and self.key == other.key

    def __hash__(self) -> int:
        """Hash consistently with equality.

        Returns:
            The hash of the key.
        """
        return hash(self.key)

    def __repr__(self) -> str:
        """Show what the merged styles hold.

        Returns:
            The constructor call that would rebuild them.
        """
        return f"Merged({self.style!r}, {self.dynamic!r}, {dict(self.parts)!r})"


class _Table:
    """A style table with every style in it lowered once.

    Attributes:
        source: The table as written, kept so that its id stays its own.
        breakpoints: The breakpoints the table was lowered with.
        consulted: The props the table or one of its parts reads, in the order
            their values are keyed by.
        base: The lowered base style.
        variants: For each variant, the position of its prop in ``consulted``
            and the lowered style of each value.
        compound: For each compound style, the positions and values of the
            props it needs and its lowered style.
        parts: The table of each inner element.
        resolved: The properties the table gives for each choice of values.
        merged: The result for each choice of values without a user style.
    """

    __slots__ = (
        "base",
        "breakpoints",
        "compound",
        "consulted",
        "merged",
        "parts",
        "resolved",
        "source",
        "variants",
    )

    def __init__(self, name: str, source: Mapping[str, Any]):
        """Lower a style table.

        Args:
            name: The display name of the component, for error messages.
            source: The table as written.

        Raises:
            StyleError: If the table has a key that is not part of one, or a
                style in it cannot be compiled.
        """
        for key in source:
            if key not in _TABLE_KEYS:
                msg = (
                    f'{name}: unknown key "{key}" in a style table. Use "base", '
                    '"variants", "compound" or "parts".'
                )
                raise StyleError(msg)
        self.source = source
        self.breakpoints = list(breakpoints_values)
        self.base = lower_layer(name, source.get("base"))
        self.parts = tuple([
            (part, _Table(name, table))
            for part, table in source.get("parts", _NO_PROPS).items()
        ])
        variants = source.get("variants", _NO_PROPS)
        compound = source.get("compound", ())
        positions: dict[str, int] = dict.fromkeys(variants, 0)
        for item in compound:
            positions.update(dict.fromkeys(item["props"], 0))
        for _, part in self.parts:
            positions.update(dict.fromkeys(part.consulted, 0))
        positions = {prop: position for position, prop in enumerate(positions)}
        self.consulted = tuple(positions)
        self.variants: tuple[tuple[int, dict[str | None, Layer]], ...] = tuple([
            (
                positions[prop],
                {value: lower_layer(name, style) for value, style in values.items()},
            )
            for prop, values in variants.items()
        ])
        self.compound: tuple[tuple[tuple[tuple[int, str], ...], Layer], ...] = tuple([
            (
                tuple([
                    (positions[prop], value) for prop, value in item["props"].items()
                ]),
                lower_layer(name, item["style"]),
            )
            for item in compound
        ])
        self.resolved: dict[tuple[str | None, ...], dict[str, LoweredValue]] = {}
        self.merged: dict[tuple[str | None, ...], Merged] = {}

    def resolve(self, keys: tuple[str | None, ...]) -> dict[str, LoweredValue]:
        """Merge the styles of the table that a choice of prop values selects.

        Args:
            keys: The value of each consulted prop, or None for one that is
                not set.

        Returns:
            The merged properties, shared by every element with these values.
        """
        props = self.resolved.get(keys)
        if props is None:
            props = dict(self.base[0])
            for position, values in self.variants:
                layer = values.get(keys[position])
                if layer is not None:
                    apply_layer(props, layer)
            for needed, layer in self.compound:
                for position, value in needed:
                    if keys[position] != value:
                        break
                else:
                    apply_layer(props, layer)
            self.resolved[keys] = props
        return props


# The lowered form of every style table merged so far, by the id of the table.
_TABLES: dict[int, _Table] = {}


def _table(name: str, styles: Mapping[str, Any]) -> _Table:
    """Find the lowered form of a style table, lowering it the first time.

    Args:
        name: The display name of the component, for error messages.
        styles: The style table.

    Returns:
        The lowered table.
    """
    table = _TABLES.get(id(styles))
    if (
        table is None
        or table.source is not styles
        or table.breakpoints != breakpoints_values
    ):
        table = _TABLES[id(styles)] = _Table(name, styles)
    return table


def _variant_key(value: Any) -> Any:
    """Read the value of a prop as the key its variant is listed under.

    Args:
        value: The value of the prop, which is neither a string nor None.

    Returns:
        The key, or the Var itself for a prop that is bound to state.
    """
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, Var):
        if isinstance(value, LiteralVar) and value._get_all_var_data() is None:
            literal = value._var_value
            return literal if literal.__class__ is str else _variant_key(literal)
        return value
    return str(value)


def _difference(
    static: dict[str, LoweredValue], full: dict[str, LoweredValue]
) -> dict[str, LoweredValue]:
    """Find what a style changes in another one.

    Args:
        static: The style of the element without a prop.
        full: Its style with a value for the prop.

    Returns:
        The properties whose value differs, with None for one that goes away.
    """
    changed = {
        prop: value
        for prop, value in full.items()
        if prop not in static or freeze(static[prop]) != freeze(value)
    }
    for prop in static:
        if prop not in full:
            changed[prop] = None
    return changed


def _merge_dynamic(
    table: _Table,
    keys: tuple[str | None, ...],
    bound: dict[int, Var],
    layers: list[Layer],
) -> tuple[dict[str, LoweredValue], tuple[Alternatives, ...]]:
    """Merge the styles of an element some of whose props are bound to state.

    Args:
        table: The lowered style table.
        keys: The value of each consulted prop, None for the bound ones.
        bound: The Var of each bound prop, by its position in ``keys``.
        layers: The lowered layout props and user style.

    Returns:
        The properties of the element without the bound props, and the
        alternatives that the values of the bound props select.
    """

    def merged_with(assigned: dict[int, str]) -> dict[str, LoweredValue]:
        """Merge the styles of the element for a choice of the bound props.

        Args:
            assigned: The value of each bound prop that has one, by position.

        Returns:
            The merged properties.
        """
        chosen = list(keys)
        for position, value in assigned.items():
            chosen[position] = value
        props = dict(table.resolve(tuple(chosen)))
        for layer in layers:
            apply_layer(props, layer)
        return props

    static = merged_with({})
    domains: dict[int, dict[Any, None]] = {position: {} for position in bound}
    for position, values in table.variants:
        if position in bound:
            domains[position].update(dict.fromkeys(values))
    # Each bound prop starts in a group of its own.
    group_of = {position: [position] for position in bound}
    for needed, _ in table.compound:
        together = [position for position, _ in needed if position in bound]
        for position, value in needed:
            if position in bound:
                domains[position][value] = None
        _join(group_of, together)

    changes: dict[int, dict[str, dict[str, LoweredValue]]] = {}
    for position, domain in domains.items():
        changes[position] = {
            value: _difference(static, merged_with({position: value}))
            for value in domain
        }
    touched: dict[str, int] = {}
    for position, by_value in changes.items():
        for change in by_value.values():
            for prop in change:
                _join(group_of, [touched.setdefault(prop, position), position])

    alternatives = []
    for position in bound:
        group = group_of[position]
        if group[0] != position:
            continue
        if len(group) == 1:
            values = {
                (value,): finish(change, unset=True)
                for value, change in changes[position].items()
                if change
            }
        else:
            values = {}
            for combo in product(*[domains[member] for member in group]):
                change = _difference(
                    static, merged_with(dict(zip(group, combo, strict=True)))
                )
                if change:
                    values[combo] = finish(change, unset=True)
        if values:
            alternatives.append(
                Alternatives(
                    tuple([table.consulted[member] for member in group]),
                    tuple([bound[member] for member in group]),
                    values,
                )
            )
    return static, tuple(alternatives)


def _join(group_of: dict[int, list[int]], members: list[int]) -> None:
    """Put props that depend on each other in one group.

    Args:
        group_of: The group of each prop, shared by its members and changed in
            place.
        members: Props that have to be in the same group.
    """
    first = group_of[members[0]] if members else []
    for member in members[1:]:
        group = group_of[member]
        if group is not first:
            first.extend(group)
            first.sort()
            for moved in group:
                group_of[moved] = first


def _merge(
    name: str,
    table: _Table,
    props: Mapping[str, Any],
    style: Mapping[str, Any] | Var | Sequence[Mapping[str, Any] | Var] | None,
    layout: Mapping[str, Any] | None,
) -> Merged:
    """Merge a lowered style table with the style of one element.

    Args:
        name: The display name of the component, for error messages.
        table: The lowered style table.
        props: The props of the element.
        style: The style the user wrote, or several of them in the order
            they apply.
        layout: The layout props of the element.

    Returns:
        The merged styles.
    """
    chosen = []
    bound = None
    for prop in table.consulted:
        value = props.get(prop)
        if value.__class__ is not str and value is not None:
            value = _variant_key(value)
            if value.__class__ is not str:
                if bound is None:
                    bound = {}
                bound[len(chosen)] = value
                value = None
        chosen.append(value)
    keys = tuple(chosen)

    if bound is None:
        merged = table.merged.get(keys)
        if merged is None:
            merged = table.merged[keys] = Merged(
                finish(table.resolve(keys)),
                (),
                {
                    part: _merge(name, inner, props, None, None)
                    for part, inner in table.parts
                },
            )
        if style is None and not layout:
            return merged
        parts = merged.parts
    else:
        parts = {
            part: _merge(name, inner, props, None, None) for part, inner in table.parts
        }

    layers = [lower_layer(name, None, layout)] if layout else []
    inline = None
    if isinstance(style, Var):
        inline = style
    elif isinstance(style, Mapping):
        if style:
            layers.append(lower_layer(name, style))
    elif style:
        for item in style:
            if isinstance(item, Var):
                inline = item
            elif item:
                layers.append(lower_layer(name, item))

    if bound is None:
        merged_props = dict(table.resolve(keys))
        for layer in layers:
            apply_layer(merged_props, layer)
        return Merged(finish(merged_props, inline), (), parts)
    merged_props, dynamic = _merge_dynamic(table, keys, bound, layers)
    return Merged(finish(merged_props, inline), dynamic, parts)


def merge(
    name: str,
    styles: ComponentStyles | Mapping[str, Any],
    props: Mapping[str, Any] | None = None,
    style: StyleProps
    | Mapping[str, Any]
    | Var
    | Sequence[StyleProps | Mapping[str, Any] | Var]
    | None = None,
    layout: Mapping[str, Any] | None = None,
) -> Merged:
    """Merge the style table of a component with the style of one element.

    The table is lowered the first time it is seen and kept by its identity,
    so it has to be a constant that is not changed afterwards.

    Args:
        name: The display name of the component, such as ``"rx.ui.button"``,
            which starts every error message.
        styles: The style table of the component.
        props: The props of the element that select variants and compound
            styles, defaults included. A value is a string, a bool, a number
            or, for a prop bound to state, a Var. Props the table does not
            read are ignored.
        style: The style the user wrote, or a Var holding a whole dict of
            styles, which becomes the inline style of the element. A list or
            tuple of them is merged in order, each over the ones before it.
        layout: The layout props of the element, such as ``p`` and ``gap``,
            which are merged after the table and before ``style``.

    Returns:
        The merged styles of the element and of each of its parts.

    Raises:
        StyleError: If the table, the style or a layout prop cannot be
            compiled.
    """
    return _merge(name, _table(name, styles), props or _NO_PROPS, style, layout)
