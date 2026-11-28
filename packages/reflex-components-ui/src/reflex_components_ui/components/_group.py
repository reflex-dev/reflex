"""What a group of form controls shares: finding its items, and their state."""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from typing import Any, ClassVar, TypeVar

from reflex_base.components.component import BaseComponent, Component
from reflex_base.components.tags import CommonTag
from reflex_base.vars.base import LiteralVar, Var, VarData

from reflex_components_ui.base import UIComponent
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.control import GROUP_ITEM, GROUP_ITEM_INNER
from reflex_components_ui.typography.text import Text

T = TypeVar("T")

# Numbers the groups that are given no name of their own.
_names = itertools.count(1)


def group_name(name: Var | None, kind: str) -> Var:
    """Get the name the inputs of a group share.

    The browser takes radio buttons for one group by their name, so a group
    without one is given a name no other group of the app has.

    Args:
        name: The name the group was created with, or None.
        kind: What the group holds, such as ``radio``.

    Returns:
        The name of the inputs.
    """
    if name is not None:
        return name
    return LiteralVar.create(f"rx-{kind}-{next(_names)}")


class GroupRoot(UIComponent):
    """The root of a group of inputs, which says how its items look and are.

    Radix hands the items of a group its props through a context. Here the
    root finds its items while compiling, below it at any depth, and gives
    them what they render: nothing is looked up in the browser. An item that
    is not below its root in the tree a page is built from, such as one a
    memoized component renders, has the look of a group without props.
    """

    def _post_init(self, *args, **kwargs):
        """Initialize the group, and give its items what they share.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        super()._post_init(*args, **kwargs)
        self._bind()
        # The size Radix Themes gives a group that is not given one.
        size = getattr(self, "size", None)
        if size is None:
            size = LiteralVar.create("2")
        for label in descendants(self, GroupItemLabel):
            label.size = size
            label._merge_styles()
        for item in descendants(self, GroupInput):
            item._join(self)

    def _bind(self) -> None:
        """Work out what the items of the group are given, before they join."""


def descendants(component: BaseComponent, kind: type[T]) -> Iterator[T]:
    """Find the items of a group below its root, at any depth.

    Args:
        component: The root of the group, or what is searched below it.
        kind: The class of the items.

    Yields:
        Each item, in the order of the tree. What is below the root of
        another group is the business of that group.
    """
    for child in component.children:
        if isinstance(child, kind):
            yield child
        if not isinstance(child, GroupRoot):
            yield from descendants(child, kind)


class GroupItemLabel(Text):
    """The label around an item of a group that is given children."""

    def add_style(self) -> dict[str, Any]:
        """Lay the input and its text out in a row.

        Returns:
            The styles Radix Themes gives the label of an item.
        """
        return GROUP_ITEM


class GroupItemInner(UIComponent):
    """The children of an item of a group, beside its input."""

    tag = "span"

    styles: ClassVar[ComponentStyles] = GROUP_ITEM_INNER


class GroupInput(UIComponent):
    """An item of a group: a native input its group gives a look and a state."""

    tag = "input"

    # The type of the input.
    _type: ClassVar[str]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an item: an input, in a label when it has children.

        Args:
            *children: What is shown beside the input.
            **props: The props of the item. With children, its styles are
                those of the label.

        Returns:
            The input, or the label that holds it.
        """
        if not children:
            return super().create(**props)
        fields = cls.get_fields()
        own = {
            key: props.pop(key)
            for key in list(props)
            if key in fields or key.startswith(("on_", "aria_", "data_"))
        }
        return GroupItemLabel.create(
            super().create(**own),
            GroupItemInner.create(*children),
            as_="label",
            **props,
        )

    def _post_init(self, *args, **kwargs):
        """Initialize the item, with the look of a group without props.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        # What the style table reads as variants, and the attributes the
        # group gives its items: both are set by the group around the item.
        self._size: Any = None
        self._variant: Any = None
        self._high_contrast: Any = None
        self._group: dict[str, Any] = {}
        super()._post_init(*args, **kwargs)

    def _join(self, group: Any) -> None:
        """Take from a group what Radix hands its items through a context.

        Args:
            group: The group the item is in.
        """
        self._size = group.size
        self._variant = group.variant
        self._high_contrast = group.high_contrast
        attributes: dict[str, Any] = {"name": group._name}
        disabled = either(group.disabled, getattr(self, "disabled", None))
        if disabled is not None:
            attributes["disabled"] = disabled
        required = either(group.required, getattr(self, "required", None))
        if required is not None:
            attributes["required"] = required
        value = getattr(self, "value", None)
        if group.value is not None:
            # An input React keeps checked says who changes it: the group.
            attributes["checked"] = group._holds(group.value, value)
            attributes["read_only"] = True
        elif group.default_value is not None:
            checked = group._holds(group.default_value, value)
            if checked is not False:
                attributes["default_checked"] = checked
        self._group = attributes
        self._merge_styles()

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the item, those its group gives it included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        for value in self._group.values():
            if isinstance(value, Var):
                yield value

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the input.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with the type of the input and what its group gives it.
        """
        return super()._render(props).add_props(type=self._type, **self._group)


def literal(value: Any) -> Any:
    """Read a value that is known while compiling.

    Args:
        value: A prop of a component.

    Returns:
        What a literal Var holds, or the value as given.
    """
    if isinstance(value, LiteralVar) and value._get_all_var_data() is None:
        return value._var_value
    return value


def either(first: Var | None, second: Var | None) -> Var | None:
    """Combine two flags, either of which may be left out.

    Args:
        first: A flag, such as whether a group is disabled.
        second: Another one, such as whether one of its items is.

    Returns:
        Whether one of them is set, or None when neither is given.
    """
    if first is None or second is None:
        return second if first is None else first
    one, other = literal(first), literal(second)
    if not isinstance(one, Var) and not isinstance(other, Var):
        return LiteralVar.create(bool(one or other))
    return Var(
        f"({first!s} || {second!s})",
        _var_type=bool,
        _var_data=VarData.merge(first._get_all_var_data(), second._get_all_var_data()),
    )


def is_value(selected: Var, value: Var | None) -> Var | bool:
    """Say whether an item is the one a group has selected.

    Args:
        selected: The value of the group.
        value: The value of the item.

    Returns:
        Whether they are equal: a bool when both are known while compiling.
    """
    if value is None:
        return False
    one, other = literal(selected), literal(value)
    if not isinstance(one, Var) and not isinstance(other, Var):
        return one == other
    return Var(
        f"({selected!s} === {value!s})",
        _var_type=bool,
        _var_data=VarData.merge(
            selected._get_all_var_data(), value._get_all_var_data()
        ),
    )


def has_value(selected: Var, value: Var | None) -> Var | bool:
    """Say whether an item is among the ones a group has selected.

    Args:
        selected: The values of the group.
        value: The value of the item.

    Returns:
        Whether the value is one of them: a bool when both are known while
        compiling.
    """
    if value is None:
        return False
    several, one = literal(selected), literal(value)
    if not isinstance(several, Var) and not isinstance(one, Var):
        return one in several
    return Var(
        f"({selected!s}.includes({value!s}))",
        _var_type=bool,
        _var_data=VarData.merge(
            selected._get_all_var_data(), value._get_all_var_data()
        ),
    )
