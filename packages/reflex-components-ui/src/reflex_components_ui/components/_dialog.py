"""What a dialog and an alert dialog share: a native ``dialog`` and its parts."""

from __future__ import annotations

import dataclasses
import itertools
from collections.abc import Iterator
from typing import Any, ClassVar

from reflex_base.components.component import Component
from reflex_base.components.tags import CommonTag
from reflex_base.vars.base import LiteralVar, Var, VarData

from reflex_components_ui.base import Part, UIComponent
from reflex_components_ui.components._group import descendants
from reflex_components_ui.components._script import handlers, listen, script
from reflex_components_ui.layout.flex import Flex
from reflex_components_ui.style import ComponentStyles, StyleError
from reflex_components_ui.styles.dialog import (
    DIALOG,
    DIALOG_DESCRIPTION,
    DIALOG_ROOT,
    DIALOG_TITLE,
)

# Numbers the dialogs of an app: a dialog is named by the id of its title.
_ids = itertools.count(1)

# The events of a dialog as they are rendered, by the name the script calls
# each under.
_EVENTS = {
    "onOpenChange": "open",
    "onOpenAutoFocus": "openAutoFocus",
    "onCloseAutoFocus": "closeAutoFocus",
    "onEscapeKeyDown": "escape",
    "onPointerDownOutside": "outside",
    "onInteractOutside": "interact",
}


class DialogRootBase(UIComponent):
    """The element around the parts of a dialog.

    Radix hands the parts of a dialog its props through a context. Here the
    root finds its parts while compiling, and gives them what they render.
    """

    tag = "div"

    styles: ClassVar[ComponentStyles] = DIALOG_ROOT

    def _post_init(self, *args, **kwargs):
        """Initialize the dialog, and give its parts what they share.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        super()._post_init(*args, **kwargs)
        name = f"rx-dialog-{next(_ids)}"
        on_open_change = self.event_triggers.pop("on_open_change", None)
        parts = list(descendants(self, DialogPart, DialogRootBase))
        named: dict[str, Any] = {}
        for part in parts:
            if part._names is not None:
                if part.id is None:
                    part.id = LiteralVar.create(f"{name}-{part._names}")
                named.setdefault(f"aria-{part._names}", part.id)
        for part in parts:
            part._join(self, name, named, on_open_change)

    def _exclude_props(self) -> list[str]:
        """Keep the props that are the ones of the dialog off the element.

        Returns:
            The props read as styles, and whether the dialog is open.
        """
        return [*super()._exclude_props(), "open", "default_open"]

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the dialog, the script that opens it included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        yield script("dialog", "dialogClick")

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the element around the dialog.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, which hears a press on what opens the dialog, on what
            closes it and beside its panel.
        """
        tag = super()._render(props).add_props(**{"data-rx-dialog-root": ""})
        return listen(tag, script("dialog", "dialogClick"), "onClick")


class DialogPart(UIComponent):
    """A part of a dialog, which its root gives a name."""

    # What the part is to the dialog: ``labelledby`` for its title,
    # ``describedby`` for its description.
    _names: ClassVar[str | None] = None

    def _post_init(self, *args, **kwargs):
        """Initialize the part, as one outside a dialog.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        # The attributes the dialog gives the part.
        self._dialog: dict[str, Any] = {}
        super()._post_init(*args, **kwargs)

    def _join(
        self,
        root: DialogRootBase,
        name: str,
        named: dict[str, Any],
        on_open_change: Any,
    ) -> None:
        """Take from a dialog what Radix hands its parts through a context.

        Args:
            root: The dialog the part is in.
            name: The id of the dialog.
            named: What names and describes the dialog, by the attribute.
            on_open_change: What the dialog does when it opens or closes.
        """

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the part, those its dialog gives it included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        for value in self._dialog.values():
            if isinstance(value, Var):
                yield value


class DialogSlot(DialogPart):
    """A part of a dialog that is rendered as its child: what opens or closes it.

    These parts act on a press, and so does a child with a handler of its
    own for one: such a child is put in a flex container, which is then the
    part, as in the Radix components.
    """

    # The child keeps its own styles.
    _merges_slot: ClassVar[bool] = False

    # The command a button gives the dialog without a script, where the
    # browser has commands.
    _command: ClassVar[str] = "close"

    # The attribute the script finds the part by.
    _mark: ClassVar[str] = "data-rx-dialog-close"

    # What the attribute says of the part.
    _marked: ClassVar[str] = ""

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a part that is rendered as its child.

        Args:
            *children: The child: one element.
            **props: The properties of the component.

        Returns:
            The component.
        """
        for child in children:
            if "on_click" in getattr(child, "event_triggers", {}):
                children = (Flex.create(*children),)
                break
        return super().create(*children, **props)

    def _post_init(self, *args, **kwargs):
        """Initialize the part, rendered as its only child.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.

        Raises:
            StyleError: If the part does not have exactly one child that is
                an element.
        """
        super()._post_init(*args, **kwargs)
        if "as_child" in self.get_fields():
            # The part says itself whether it is its child, and is a button
            # around its children otherwise.
            if not self._as_child:
                self.tag = "button"
            return
        children = self.children
        if (
            len(children) != 1
            or not isinstance(children[0], Component)
            or type(children[0]).render not in (Component.render, UIComponent.render)
        ):
            name = self._display_name()  # pyright: ignore[reportAttributeAccessIssue]
            msg = (
                f"{name}: it is rendered as its child, so it needs exactly one "
                "child that is an element, such as a button."
            )
            raise StyleError(msg)
        self._as_child = True
        # The child has to stay the child: a compile would otherwise move
        # one that is bound to state into a component of its own.
        self._memoization_mode = dataclasses.replace(
            self._memoization_mode, recursive=False
        )

    def _join(
        self,
        root: DialogRootBase,
        name: str,
        named: dict[str, Any],
        on_open_change: Any,
    ) -> None:
        """Take the id of the dialog, for a button that commands it.

        Args:
            root: The dialog the part is in.
            name: The id of the dialog.
            named: What names and describes the dialog, by the attribute.
            on_open_change: What the dialog does when it opens or closes.
        """
        if getattr(root, "open", None) is None:
            # A dialog bound to state opens and closes when its state says.
            self._dialog = {"commandfor": name, "command": self._command}

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the part.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag: its child, marked for the script of the dialog.
        """
        return (
            super()
            ._render(props)
            .add_props(**{self._mark: self._marked, **self._dialog})
        )


class DialogTriggerBase(DialogSlot):
    """What opens a dialog: its child, which says so."""

    _command: ClassVar[str] = "show-modal"

    _mark: ClassVar[str] = "data-rx-dialog-trigger"

    def _join(
        self,
        root: DialogRootBase,
        name: str,
        named: dict[str, Any],
        on_open_change: Any,
    ) -> None:
        """Take the id of the dialog the trigger opens.

        Args:
            root: The dialog the trigger is in.
            name: The id of the dialog.
            named: What names and describes the dialog, by the attribute.
            on_open_change: What the dialog does when it opens or closes.
        """
        super()._join(root, name, named, on_open_change)
        self._dialog["aria-controls"] = name

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the trigger.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag: its child, with the state Radix gives what opens a
            dialog.
        """
        return (
            super()
            ._render(props)
            .add_props(**{
                "aria-haspopup": "dialog",
                "aria-expanded": False,
                "data-state": "closed",
            })
        )


class DialogSurface(DialogPart):
    """The native dialog: it covers the page, around the panel of the dialog."""

    tag = "dialog"

    styles: ClassVar[ComponentStyles] = DIALOG

    # The role of the dialog, when it is not the one the element has.
    _role: ClassVar[str | None] = None

    # What does not dismiss the dialog: ``outside`` for a press beside its
    # panel, ``all`` for that and Escape.
    _keeps: ClassVar[str | None] = None

    def _post_init(self, *args, **kwargs):
        """Initialize the dialog, as one that is not bound to state.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        # Whether the dialog is open, when its state says.
        self._open: Var | None = None
        super()._post_init(*args, **kwargs)

    def _join(
        self,
        root: DialogRootBase,
        name: str,
        named: dict[str, Any],
        on_open_change: Any,
    ) -> None:
        """Take the name of the dialog, and whether it is open.

        Args:
            root: The dialog the element is in.
            name: The id of the dialog.
            named: What names and describes the dialog, by the attribute.
            on_open_change: What the dialog does when it opens or closes.
        """
        self._dialog = {"id": name, **named}
        self._open = getattr(root, "open", None)
        default_open = getattr(root, "default_open", None)
        if default_open is not None:
            self._dialog["data-default-open"] = default_open
        if on_open_change is not None:
            self.event_triggers["on_open_change"] = on_open_change

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the dialog, its script included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        yield script("dialog", "dialogSync")
        yield script("dialog", "dialogEvent")
        if self._open is not None:
            yield self._open

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the dialog.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag: a ``dialog`` the script opens over the page, which
            follows the state it is bound to and says what happens to it.
        """
        tag, on = handlers(super()._render(props), _EVENTS)
        bound = LiteralVar.create(self._open)
        sync = script("dialog", "dialogSync")
        tag = tag.add_props(**{
            "data-rx-popup": "",
            "role": self._role,
            "data-rx-keep": self._keeps,
            **self._dialog,
            # Called whenever the page renders: a dialog bound to state
            # takes whether it is open from there.
            "ref": Var(
                f"((dialog) => dialogSync(dialog, {bound!s}, {'null' if on is None else on!s}))",
                _var_data=VarData.merge(
                    sync._get_all_var_data(),
                    bound._get_all_var_data(),
                    None if on is None else on._get_all_var_data(),
                ),
            ),
        })
        return listen(tag, script("dialog", "dialogEvent"), "onCancel", "onClose")


def surface(
    kind: type[DialogSurface], content: Component, events: dict[str, Any]
) -> Component:
    """Put the panel of a dialog in the native dialog that covers the page.

    Args:
        kind: The class of the dialog.
        content: The panel.
        events: What the dialog does when it opens, closes or is dismissed.

    Returns:
        The dialog: the room around the panel is what scrolls a tall one.
    """
    return kind.create(
        Part.create(
            content,
            part="pad",
            tag="div",
            custom_attrs={"data-rx-dialog-pad": ""},
        ),
        **events,
    )


class DialogTitleBase(DialogPart):
    """The title of a dialog, which names it."""

    tag = "h1"

    styles: ClassVar[ComponentStyles] = DIALOG_TITLE

    _names: ClassVar[str | None] = "labelledby"


class DialogDescriptionBase(DialogPart):
    """The description of a dialog, which a screen reader reads with its name."""

    tag = "p"

    styles: ClassVar[ComponentStyles] = DIALOG_DESCRIPTION

    _names: ClassVar[str | None] = "describedby"
