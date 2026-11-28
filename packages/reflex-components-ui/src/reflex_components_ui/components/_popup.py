"""What the popups share: a native popover, and what opens and closes it."""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from typing import Any, ClassVar

from reflex_base.components.component import Component
from reflex_base.components.tags import CommonTag
from reflex_base.vars.base import LiteralVar, Var, VarData

from reflex_components_ui.base import UIComponent
from reflex_components_ui.components._group import descendants, literal
from reflex_components_ui.components._script import handlers, listen, script
from reflex_components_ui.components._slot import become_child, held
from reflex_components_ui.props import style_before
from reflex_components_ui.styles.popup import OFFSET, SHIFT

# Numbers the popups of an app: what opens a popup names it by its id.
_ids = itertools.count(1)

# The events of a popup as they are rendered, by the name the script calls
# each under.
_EVENTS = {
    "onOpenChange": "open",
    "onOpenAutoFocus": "openAutoFocus",
    "onCloseAutoFocus": "closeAutoFocus",
    "onEscapeKeyDown": "escape",
    "onPointerDownOutside": "outside",
    "onFocusOutside": "focusOutside",
    "onInteractOutside": "interact",
}


def pixels(amount: Any) -> Any:
    """Write a number of pixels as a length.

    Args:
        amount: The number, or a Var of it.

    Returns:
        The length: a string when the number is known while compiling.
    """
    amount = literal(amount)
    if not isinstance(amount, Var):
        return f"{amount}px"
    return Var(
        f'(({amount!s}) + "px")', _var_type=str, _var_data=amount._get_all_var_data()
    )


def offsets(props: dict[str, Any], gap: int = 0) -> None:
    """Put how far a popup is from its anchor before its other styles.

    Args:
        props: The props a popup is created with, changed in place: its
            ``side_offset`` and its ``align_offset`` become custom
            properties the placement of the popup reads.
        gap: The room, in pixels, the popup leaves beside its anchor on top
            of the distance it is asked to keep.
    """
    distances = {
        name: pixels(
            literal(LiteralVar.create(props[prop])) + extra if extra else props[prop]
        )
        for prop, name, extra in (
            ("side_offset", OFFSET, gap),
            ("align_offset", SHIFT, 0),
        )
        if props.get(prop) is not None
    }
    if distances:
        style_before(props, distances)


class PopupRoot(UIComponent):
    """The root of a popup, which renders nothing of its own.

    Radix hands the parts of a popup its props through a context. Here the
    root finds its parts while compiling, and gives them what they render.
    """

    library = "react"

    tag = "Fragment"

    _is_tag_in_global_scope: ClassVar[bool] = False

    # What the ids of the popups of the component start with.
    _prefix: ClassVar[str] = "rx-popup"

    def _post_init(self, *args, **kwargs):
        """Initialize the popup, and give its parts what they share.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        super()._post_init(*args, **kwargs)
        name: Any = f"{self._prefix}-{next(_ids)}"
        on_open_change = self.event_triggers.pop("on_open_change", None)
        parts = list(descendants(self, PopupPart, PopupRoot))
        for part in parts:
            if isinstance(part, PopupContent) and part.id is not None:
                name = part.id
        for part in parts:
            part._join(self, name, on_open_change)

    def _exclude_props(self) -> list[str]:
        """Keep the props that are the ones of the popup off the root.

        Returns:
            Every prop: the root renders no element.
        """
        return [*super()._exclude_props(), *self.get_fields()]


class PopupPart(UIComponent):
    """A part of a popup, which its root gives a name."""

    def _post_init(self, *args, **kwargs):
        """Initialize the part, as one outside a popup.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        # The attributes the popup gives the part.
        self._popup: dict[str, Any] = {}
        super()._post_init(*args, **kwargs)

    def _join(self, root: PopupRoot, name: Any, on_open_change: Any) -> None:
        """Take from a popup what Radix hands its parts through a context.

        Args:
            root: The popup the part is in.
            name: The id of the popup.
            on_open_change: What the popup does when it opens or closes.
        """

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the part, those its popup gives it included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        for value in self._popup.values():
            if isinstance(value, Var):
                yield value


class PopupTrigger(PopupPart):
    """What opens a popup: its child, a button the browser opens the popup from."""

    # The child keeps its own styles.
    _merges_slot: ClassVar[bool] = False

    # What the trigger says it opens, to assistive technology.
    _haspopup: ClassVar[str] = "dialog"

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a part that is rendered as its child.

        Args:
            *children: The child: one element.
            **props: The properties of the component.

        Returns:
            The component.
        """
        return super().create(*held(children), **props)

    def _post_init(self, *args, **kwargs):
        """Initialize the part, rendered as its only child.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        super()._post_init(*args, **kwargs)
        become_child(self)

    def _join(self, root: PopupRoot, name: Any, on_open_change: Any) -> None:
        """Take the id of the popup the trigger opens.

        Args:
            root: The popup the trigger is in.
            name: The id of the popup.
            on_open_change: What the popup does when it opens or closes.
        """
        self._popup = {"popovertarget": name, "aria-controls": name}

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the trigger.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag: its child, which opens its popup without a script,
            with the state Radix gives what opens a popup.
        """
        return (
            super()
            ._render(props)
            .add_props(**{
                "aria-haspopup": self._haspopup,
                "aria-expanded": False,
                "data-state": "closed",
                **self._popup,
            })
        )


class PopupClose(PopupTrigger):
    """What closes a popup from inside it: its child, a button."""

    def _join(self, root: PopupRoot, name: Any, on_open_change: Any) -> None:
        """Take the id of the popup the button closes.

        Args:
            root: The popup the button is in.
            name: The id of the popup.
            on_open_change: What the popup does when it opens or closes.
        """
        self._popup = {"popovertarget": name, "popovertargetaction": "hide"}

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the button.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag: its child, which closes the popup without a script.
        """
        return UIComponent._render(self, props).add_props(**self._popup)


class PopupContent(PopupPart):
    """A native popover placed beside what opens it."""

    tag = "div"

    # The role of the popup.
    _role: ClassVar[str | None] = "dialog"

    # The room the popup leaves beside its anchor on top of its offset.
    _gap: ClassVar[int] = 0

    # Whether the browser closes the popup on Escape and on a press outside
    # it (``auto``), or its script does (``manual``).
    _popover: ClassVar[str] = "auto"

    # Whether the popup takes the focus from its script.
    _tab_index: ClassVar[int | None] = -1

    # The script of the popup: its name, what keeps the popup as its state
    # says, and what hears the events named after them.
    _script: ClassVar[tuple[str, ...]] = (
        "popup",
        "popupSync",
        "popupEvent",
        "onToggle",
        "onKeyDown",
        "onClick",
        "onBlur",
    )

    # Whether what the popup does is handed to what keeps it as its state
    # says, rather than to what hears its events.
    _synced: ClassVar[bool] = False

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a popup.

        Args:
            *children: What the popup holds.
            **props: The properties of the component.

        Returns:
            The popup, as far from its anchor as it is asked to be.
        """
        offsets(props, cls._gap)
        return super().create(*children, **props)

    def _post_init(self, *args, **kwargs):
        """Initialize the popup, as one that is not bound to state.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        # Whether the popup is open, when its state says.
        self._open: Var | None = None
        super()._post_init(*args, **kwargs)

    def _join(self, root: PopupRoot, name: Any, on_open_change: Any) -> None:
        """Take the name of the popup, and whether it is open.

        Args:
            root: The popup the element is in.
            name: The id of the popup.
            on_open_change: What the popup does when it opens or closes.
        """
        if self.id is None:
            self._popup["id"] = name
        self._open = getattr(root, "open", None)
        default_open = getattr(root, "default_open", None)
        if default_open is not None:
            self._popup["data-default-open"] = default_open
        if on_open_change is not None:
            self.event_triggers["on_open_change"] = on_open_change

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the popup, its script included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        module, sync, heard = self._script[:3]
        yield script(module, sync)
        yield script(module, heard)
        if self._open is not None:
            yield self._open

    def _exclude_props(self) -> list[str]:
        """Keep the props that say where the popup goes off the element.

        Returns:
            The props read as styles, the ones a style is made from, and
            the ones the placement of the browser has no use for.
        """
        return [
            *super()._exclude_props(),
            "side_offset",
            "align_offset",
            "avoid_collisions",
            "collision_padding",
            "sticky",
            "hide_when_detached",
            "force_mount",
        ]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the popup.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag: a popover the browser opens and closes, which says so
            to its script, and through it to the events.
        """
        tag, on = handlers(super()._render(props), _EVENTS)
        module, sync_name, heard, *events = self._script
        bound = LiteralVar.create(self._open)
        sync = script(module, sync_name)
        handed = f", {on!s}" if self._synced and on is not None else ""
        tag = tag.add_props(**{
            "popover": self._popover,
            "role": self._role,
            "tabIndex": self._tab_index,
            "data-rx-popup": "",
            **self._popup,
            # Called whenever the page renders: a popup bound to state takes
            # whether it is open from there.
            "ref": Var(
                f"((popup) => {sync_name}(popup, {bound!s}{handed}))",
                _var_data=VarData.merge(
                    sync._get_all_var_data(),
                    bound._get_all_var_data(),
                    on._get_all_var_data() if handed and on is not None else None,
                ),
            ),
        })
        return listen(
            tag,
            script(module, heard),
            *events,
            arguments=() if on is None or self._synced else (on,),
        )


class HoverTrigger(PopupTrigger):
    """What a popup opens under: its child, which hears the pointer and the focus."""

    # What the trigger hears of.
    _heard: ClassVar[tuple[str, ...]] = (
        "onPointerEnter",
        "onPointerLeave",
        "onFocus",
        "onBlur",
    )

    def _join(self, root: PopupRoot | None, name: Any, on_open_change: Any) -> None:
        """Take the id of the popup that opens under the trigger.

        Args:
            root: The popup the trigger is in.
            name: The id of the popup.
            on_open_change: What the popup does when it opens or closes.
        """
        self._popup = {"data-rx-hover": name}

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the trigger, its script included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        yield script("hover", "hoverEvent")

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the trigger.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag: its child, which opens its popup under the pointer
            and with the focus of the keyboard.
        """
        tag = UIComponent._render(self, props).add_props(**{
            "data-state": "closed",
            **self._popup,
        })
        return listen(tag, script("hover", "hoverEvent"), *self._heard)


class HoverContent(PopupContent):
    """A popup that opens under the pointer and with the focus of the keyboard."""

    _role: ClassVar[str | None] = None

    _popover: ClassVar[str] = "manual"

    _tab_index: ClassVar[int | None] = None

    _script: ClassVar[tuple[str, ...]] = (
        "hover",
        "hoverSync",
        "hoverEvent",
        "onPointerEnter",
        "onPointerLeave",
        "onBlur",
    )

    _synced: ClassVar[bool] = True
