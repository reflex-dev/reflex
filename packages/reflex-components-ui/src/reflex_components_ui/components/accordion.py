"""An accordion: items that are native ``details``, opened by their summary."""

from __future__ import annotations

import itertools
from collections.abc import Iterator, Sequence
from typing import Any, ClassVar, Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.components.tags import CommonTag
from reflex_base.event import EventHandler
from reflex_base.vars.base import LiteralVar, Var, VarData
from reflex_components_lucide.icon import Icon

from reflex_components_ui.base import UIComponent
from reflex_components_ui.components._group import (
    choose,
    descendants,
    either,
    has_value,
    is_value,
    literal,
)
from reflex_components_ui.components._script import listen, script
from reflex_components_ui.props import style_before
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.accordion import (
    ACCORDION,
    ACCORDION_CONTENT,
    ACCORDION_HEADER,
    ACCORDION_ITEM,
    ACCORDION_TRIGGER,
    DIVIDER,
    DURATION,
    EASING,
)
from reflex_components_ui.themes import LiteralAccentColor

LiteralAccordionType = Literal["single", "multiple"]
LiteralAccordionDir = Literal["ltr", "rtl"]
LiteralAccordionOrientation = Literal["vertical", "horizontal"]
LiteralAccordionVariant = Literal["classic", "soft", "surface", "outline", "ghost"]
LiteralRadius = Literal["none", "small", "medium", "large", "full"]

DEFAULT_ANIMATION_DURATION = 250
DEFAULT_ANIMATION_EASING = "cubic-bezier(0.87, 0, 0.13, 1)"

# Numbers the accordions of an app, and the items that are given no value.
_ids = itertools.count(1)


def _is_one_of(values: Sequence[Var | None], wanted: tuple[str, ...]) -> Var | bool:
    """Say whether one of several props has one of the values wanted.

    Args:
        values: The props, any of which may be left out.
        wanted: The values.

    Returns:
        Whether one has: a bool when every prop is known while compiling.
    """
    bound = []
    for value in values:
        known = literal(value)
        if isinstance(known, Var):
            bound.append(known)
        elif known in wanted:
            return True
    if not bound:
        return False
    listed = LiteralVar.create(list(wanted))
    return Var(
        "(" + " || ".join([f"{listed!s}.includes({value!s})" for value in bound]) + ")",
        _var_type=bool,
        _var_data=VarData.merge(*(value._get_all_var_data() for value in bound)),
    )


def _joined(prefix: str, value: Var) -> Any:
    """Make an id from a prefix and the value of an item.

    Args:
        prefix: What the id starts with.
        value: The value of the item.

    Returns:
        The id: a string when the value is known while compiling.
    """
    known = literal(value)
    if not isinstance(known, Var):
        return f"{prefix}{known}"
    return Var(
        f"({LiteralVar.create(prefix)!s} + {known!s})",
        _var_type=str,
        _var_data=known._get_all_var_data(),
    )


class AccordionComponent(UIComponent):
    """Base class for the components of an accordion."""

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child."
    )

    color_scheme: Var[LiteralAccentColor] = field(
        doc="The color scheme of the component."
    )

    variant: Var[LiteralAccordionVariant] = field(doc="The variant of the component.")

    def _exclude_props(self) -> list[str]:
        """Keep the variant off the element: it selects styles.

        Returns:
            The props read as styles, and the variant.
        """
        return [*super()._exclude_props(), "variant"]


def on_value_change_handler(value: Var[str | list[str]]) -> tuple[Var[str | list[str]]]:
    """Handle the on_value_change event.

    Args:
        value: The value of the event.

    Returns:
        The value of the event.
    """
    return (value,)


class AccordionRoot(AccordionComponent):
    """An accordion component."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = ACCORDION

    type: Var[LiteralAccordionType] = field(
        doc="The type of accordion (single or multiple)."
    )

    value: Var[str | Sequence[str]] = field(doc="The value of the item to expand.")

    default_value: Var[str | Sequence[str]] = field(
        doc="The default value of the item to expand."
    )

    collapsible: Var[bool] = field(doc="Whether or not the accordion is collapsible.")

    disabled: Var[bool] = field(doc="Whether or not the accordion is disabled.")

    dir: Var[LiteralAccordionDir] = field(
        doc="The reading direction of the accordion when applicable."
    )

    orientation: Var[LiteralAccordionOrientation] = field(
        doc="The orientation of the accordion."
    )

    radius: Var[LiteralRadius] = field(doc="The radius of the accordion corners.")

    duration: Var[int] = field(
        default=LiteralVar.create(DEFAULT_ANIMATION_DURATION),
        doc="The time in milliseconds to animate open and close",
    )

    easing: Var[str] = field(
        default=LiteralVar.create(DEFAULT_ANIMATION_EASING),
        doc="The easing function to use for the animation.",
    )

    show_dividers: Var[bool] = field(doc="Whether to show divider lines between items.")

    _valid_children: ClassVar[list[str]] = ["AccordionItem"]

    on_value_change: EventHandler[on_value_change_handler] = field(
        doc="Fired when the opened the accordions changes."
    )

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create an AccordionRoot.

        Args:
            *children: The items of the accordion.
            **props: The properties of the component.

        Returns:
            The AccordionRoot component, which says how its panels move and
            how thick the line between two items is.
        """
        duration = literal(
            LiteralVar.create(props.get("duration", DEFAULT_ANIMATION_DURATION))
        )
        handed: dict[str, Any] = {
            DURATION: (
                Var(
                    f'({duration!s} + "ms")',
                    _var_type=str,
                    _var_data=duration._get_all_var_data(),
                )
                if isinstance(duration, Var)
                else f"{duration}ms"
            ),
            EASING: props.get("easing", DEFAULT_ANIMATION_EASING),
        }
        if props.get("show_dividers") is not None:
            shown = literal(LiteralVar.create(props["show_dividers"]))
            handed[DIVIDER] = choose(shown, "1px", "0")
        style_before(props, handed)
        return super().create(*children, **props)

    def _post_init(self, *args, **kwargs):
        """Initialize the accordion, and give its items what they share.

        Radix hands the parts of an accordion its props through a context.
        Here the root finds its items while compiling, and gives them what
        they render.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        super()._post_init(*args, **kwargs)
        self._name = f"rx-accordion-{next(_ids)}"
        # The line between two items is as thick as the accordion says, and
        # it says so when asked to, or drawn with an outline.
        self._divided: Var | bool = self.show_dividers is not None or _is_one_of(
            [self.variant], ("outline", "surface")
        )
        for item in descendants(self, AccordionItem, AccordionRoot):
            item._join(self)

    @property
    def _multiple(self) -> Var | bool:
        """Whether several items can be open at once.

        Returns:
            Whether they can: a bool when the type is known while compiling.
        """
        return _is_one_of([self.type], ("multiple",))

    def _exclude_props(self) -> list[str]:
        """Keep the props that are the ones of the items off the element.

        Returns:
            The props read as styles, and what the accordion hands its
            items or its script.
        """
        return [
            *super()._exclude_props(),
            "type",
            "value",
            "default_value",
            "collapsible",
            "disabled",
            "orientation",
            "duration",
            "easing",
            "show_dividers",
        ]

    @property
    def _scripted(self) -> bool:
        """Whether the accordion does something the browser does not.

        Returns:
            Whether an item that is open stays open when it is pressed,
            the accordion is bound to state, or says what is open.
        """
        return (
            self.value is not None
            or "on_value_change" in self.event_triggers
            or not (self._multiple is True or literal(self.collapsible) is True)
        )

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the accordion, its script included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        if self._scripted:
            yield script("accordion", "accordionClick")

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the element around the accordion.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag. The browser opens and closes the items; a script
            hears a press on a header only for what the browser does not
            do.
        """
        tag = super()._render(props)
        if not self._scripted:
            return tag
        rendered = dict(tag.props)
        on_value_change = rendered.pop("onValueChange", None)
        tag = tag.set(props=rendered).add_props(**{
            "data-rx-accordion": choose(self._multiple, "multiple", "single"),
            "data-collapsible": self.collapsible,
            "data-bound": None if self.value is None else "",
        })
        return listen(
            tag,
            script("accordion", "accordionClick"),
            "onClick",
            arguments=() if on_value_change is None else (on_value_change,),
        )


class AccordionItem(AccordionComponent):
    """An accordion component."""

    tag = "details"

    styles: ClassVar[ComponentStyles] = ACCORDION_ITEM

    value: Var[str] = field(doc="A unique identifier for the item.")

    disabled: Var[bool] = field(
        doc="When true, prevents the user from interacting with the item."
    )

    header: Var[Component | str] = field(doc="The header of the accordion item.")

    content: Var[Component | str | None] = field(
        default=Var.create(None), doc="The content of the accordion item."
    )

    _valid_children: ClassVar[list[str]] = [
        "AccordionHeader",
        "AccordionTrigger",
        "AccordionContent",
    ]

    _valid_parents: ClassVar[list[str]] = ["AccordionRoot"]

    @classmethod
    def create(
        cls,
        *children,
        **props,
    ) -> Component:
        """Create an accordion item.

        Args:
            *children: The list of children to use if header and content are not provided.
            **props: Additional properties to apply to the accordion item.

        Returns:
            The accordion item.
        """
        header = props.pop("header", None)
        content = props.pop("content", None)

        # The item requires a value to toggle (a name no other item of the
        # app has if not provided).
        value = props.pop("value", None)
        if value is None:
            value = f"rx-accordion-item-{next(_ids)}"

        if "AccordionItem" not in (
            cls_name := props.pop("class_name", "AccordionItem")
        ):
            cls_name = f"{cls_name} AccordionItem"

        color_scheme = props.get("color_scheme")
        variant = props.get("variant")

        if (header is not None) and (content is not None):
            children = [
                AccordionHeader.create(
                    AccordionTrigger.create(
                        header,
                        AccordionIcon.create(
                            color_scheme=color_scheme,
                            variant=variant,
                        ),
                        color_scheme=color_scheme,
                        variant=variant,
                    ),
                    color_scheme=color_scheme,
                    variant=variant,
                ),
                AccordionContent.create(
                    content,
                    color_scheme=color_scheme,
                    variant=variant,
                ),
            ]
        else:
            # The summary of a `details` is its child: a trigger without a
            # header is given one.
            children = [
                AccordionHeader.create(child)
                if isinstance(child, AccordionTrigger)
                else child
                for child in children
            ]

        return super().create(*children, value=value, **props, class_name=cls_name)

    def _post_init(self, *args, **kwargs):
        """Initialize the item, as one of an accordion without props.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        # What the style table reads as variants, and the attributes the
        # accordion gives the item: both are set by the root around it.
        self._ghost: Any = None
        self._divided: Any = None
        self._accordion: dict[str, Any] = {}
        super()._post_init(*args, **kwargs)

    def _join(self, accordion: AccordionRoot) -> None:
        """Take from an accordion what Radix hands its items through a context.

        Args:
            accordion: The accordion the item is in.
        """
        self._ghost = choose(
            _is_one_of([self.variant, accordion.variant], ("ghost",)), "true", "false"
        )
        self._divided = choose(accordion._divided, "true", "false")
        multiple = accordion._multiple
        selected = (
            accordion.value if accordion.value is not None else accordion.default_value
        )
        attributes: dict[str, Any] = {
            # The browser closes the other items of a name when one opens.
            "name": choose(multiple, None, accordion._name),
        }
        if selected is not None:
            several, one = (
                has_value(selected, self.value),
                is_value(selected, self.value),
            )
            attributes["open"] = (
                several
                if multiple is True
                else one
                if multiple is False
                else choose(multiple, several, one)
            )
        self._accordion = attributes
        self._merge_styles()  # pyright: ignore[reportAttributeAccessIssue]
        disabled = either(accordion.disabled, self.disabled)
        prefix = f"{accordion._name}-"
        for part in descendants(self, AccordionPart, AccordionRoot):
            part._join(accordion, self, disabled, prefix)

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the item, those its accordion gives it included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        for value in self._accordion.values():
            if isinstance(value, Var):
                yield value

    def _exclude_props(self) -> list[str]:
        """Keep the props of an item off the element.

        Returns:
            The props read as styles, and the ones its parts render.
        """
        return [*super()._exclude_props(), "header", "content", "value", "disabled"]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the item.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag: a ``details`` the browser opens and closes.
        """
        return (
            super()
            ._render(props)
            .add_props(**{
                "data-rx-accordion-item": "",
                "data-value": self.value,
                **self._accordion,
            })
        )


class AccordionPart(AccordionComponent):
    """A part of an item, which the accordion gives a look and a name."""

    def _post_init(self, *args, **kwargs):
        """Initialize the part, as one of an accordion without props.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        # What the style table reads as variants, and the attributes the
        # accordion gives the part: both are set by the root around it.
        self._classic: Any = None
        self._divided: Any = None
        self._accordion: dict[str, Any] = {}
        super()._post_init(*args, **kwargs)

    def _join(
        self,
        accordion: AccordionRoot,
        item: AccordionItem,
        disabled: Var | None,
        prefix: str,
    ) -> None:
        """Take from an accordion what Radix hands its parts through a context.

        Args:
            accordion: The accordion the part is in.
            item: The item the part is in.
            disabled: Whether the item is disabled.
            prefix: What the ids of the parts of the accordion start with.
        """
        # A part is classic when it, its item or its accordion is, and an
        # accordion is unless it says otherwise.
        self._classic = choose(
            accordion.variant is None
            or _is_one_of(
                [self.variant, item.variant, accordion.variant], ("classic",)
            ),
            "true",
            "false",
        )
        self._divided = choose(accordion._divided, "true", "false")
        self._accordion = self._attributes(item, disabled, prefix)
        self._merge_styles()  # pyright: ignore[reportAttributeAccessIssue]

    def _attributes(
        self, item: AccordionItem, disabled: Var | None, prefix: str
    ) -> dict[str, Any]:
        """Work out the attributes the accordion gives the part.

        Args:
            item: The item the part is in.
            disabled: Whether the item is disabled.
            prefix: What the ids of the parts of the accordion start with.

        Returns:
            The attributes.
        """
        return {}

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the part, those its accordion gives it included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        for value in self._accordion.values():
            if isinstance(value, Var):
                yield value

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the part.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with what its accordion gives it.
        """
        return super()._render(props).add_props(**self._accordion)


class AccordionHeader(AccordionPart):
    """An accordion component."""

    tag = "summary"

    styles: ClassVar[ComponentStyles] = ACCORDION_HEADER

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the Accordion header component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The Accordion header Component.
        """
        if "AccordionHeader" not in (
            cls_name := props.pop("class_name", "AccordionHeader")
        ):
            cls_name = f"{cls_name} AccordionHeader"

        return super().create(*children, class_name=cls_name, **props)

    def _attributes(
        self, item: AccordionItem, disabled: Var | None, prefix: str
    ) -> dict[str, Any]:
        """Say that the header of a disabled item opens nothing.

        Args:
            item: The item the header is in.
            disabled: Whether the item is disabled.
            prefix: What the ids of the parts of the accordion start with.

        Returns:
            The attributes: a disabled header says so, and Tab passes it.
        """
        if disabled is None:
            return {}
        off = literal(disabled)
        return {"aria-disabled": off, "tabIndex": choose(off, -1, None)}


class AccordionTrigger(AccordionPart):
    """An accordion component."""

    tag = "h3"

    styles: ClassVar[ComponentStyles] = ACCORDION_TRIGGER

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the Accordion trigger component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The Accordion trigger Component.
        """
        if "AccordionTrigger" not in (
            cls_name := props.pop("class_name", "AccordionTrigger")
        ):
            cls_name = f"{cls_name} AccordionTrigger"

        return super().create(*children, class_name=cls_name, **props)

    def _attributes(
        self, item: AccordionItem, disabled: Var | None, prefix: str
    ) -> dict[str, Any]:
        """Take the id the panel of the item is named by.

        Args:
            item: The item the trigger is in.
            disabled: Whether the item is disabled.
            prefix: What the ids of the parts of the accordion start with.

        Returns:
            The attributes.
        """
        if self.id is not None:
            return {}
        return {"id": _joined(f"{prefix}trigger-", item.value)}


class AccordionIcon(Icon):
    """An accordion icon component."""

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the Accordion icon component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The Accordion icon Component.
        """
        if "AccordionChevron" not in (
            cls_name := props.pop("class_name", "AccordionChevron")
        ):
            cls_name = f"{cls_name} AccordionChevron"

        # A rule of the base stylesheet turns it over in an open item.
        props.setdefault("custom_attrs", {}).setdefault("data-rx-accordion-icon", "")
        return super().create(tag="chevron_down", class_name=cls_name, **props)


class AccordionContent(AccordionPart):
    """An accordion component."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = ACCORDION_CONTENT

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the Accordion content component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The Accordion content Component.
        """
        if "AccordionContent" not in (
            cls_name := props.pop("class_name", "AccordionContent")
        ):
            cls_name = f"{cls_name} AccordionContent"

        return super().create(*children, class_name=cls_name, **props)

    def _attributes(
        self, item: AccordionItem, disabled: Var | None, prefix: str
    ) -> dict[str, Any]:
        """Name the panel by the trigger of its item.

        Args:
            item: The item the panel is in.
            disabled: Whether the item is disabled.
            prefix: What the ids of the parts of the accordion start with.

        Returns:
            The attributes.
        """
        trigger = next(iter(descendants(item, AccordionTrigger, AccordionRoot)), None)
        return {
            "aria-labelledby": (
                _joined(f"{prefix}trigger-", item.value)
                if trigger is None or trigger.id is None
                else trigger.id
            )
        }

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the panel.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with the role of a region of the page.
        """
        return super()._render(props).add_props(role="region")


class Accordion(ComponentNamespace):
    """Accordion component."""

    content = staticmethod(AccordionContent.create)
    header = staticmethod(AccordionHeader.create)
    item = staticmethod(AccordionItem.create)
    icon = staticmethod(AccordionIcon.create)
    root = staticmethod(AccordionRoot.create)
    trigger = staticmethod(AccordionTrigger.create)


accordion = Accordion()
