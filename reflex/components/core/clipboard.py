"""Global on_paste handling for Reflex app."""

from __future__ import annotations

from typing import Dict, List, Union

from reflex.components.base.fragment import Fragment
from reflex.components.tags.tag import Tag
from reflex.event import EventChain, EventHandler
from reflex.utils.format import format_prop, wrap
from reflex.utils.imports import ImportVar
from reflex.vars import Var, get_unique_variable_name


class Clipboard(Fragment):
    """Clipboard component."""

    # The element ids to attach the event listener to. Defaults to all child components or the document.
    targets: Var[List[str]]

    # Called when the user pastes data into the document. Data is a list of tuples of (mime_type, data). Binary types will be base64 encoded as a data uri.
    on_paste: EventHandler[lambda data: [data]]

    # Save the original event actions for the on_paste event.
    on_paste_event_actions: Var[Dict[str, Union[bool, int]]]

    @classmethod
    def create(cls, *children, **props):
        """Create a Clipboard component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The Clipboard Component.
        """
        if "targets" not in props:
            # Add all children as targets if not specified.
            targets = props.setdefault("targets", [])
            for c in children:
                if c.id is None:
                    c.id = f"clipboard_{get_unique_variable_name()}"
                targets.append(c.id)

        if "on_paste" in props:
            # Capture the event actions for the on_paste handler if not specified.
            props.setdefault("on_paste_event_actions", props["on_paste"].event_actions)

        return super().create(*children, **props)

    def _exclude_props(self) -> list[str]:
        return super()._exclude_props() + ["on_paste", "on_paste_event_actions"]

    def _render(self) -> Tag:
        tag = super()._render()
        tag.remove_props("targets")
        # Ensure a different Fragment component is created whenever targets differ
        tag.add_props(key=self.targets)
        return tag

    def add_imports(self) -> dict[str, ImportVar]:
        """Add the imports for the Clipboard component.

        Returns:
            The import dict for the component.
        """
        return {
            "/utils/helpers/paste.js": ImportVar(
                tag="usePasteHandler", is_default=True
            ),
        }

    def add_hooks(self) -> list[str]:
        """Add hook to register paste event listener.

        Returns:
            The hooks to add to the component.
        """
        on_paste = self.event_triggers["on_paste"]
        if on_paste is None:
            return []
        if isinstance(on_paste, EventChain):
            on_paste = wrap(str(format_prop(on_paste)).strip("{}"), "(")
        return [
            "usePasteHandler(%s, %s, %s)"
            % (
                self.targets._var_name_unwrapped,
                self.on_paste_event_actions._var_name_unwrapped,
                on_paste,
            )
        ]


clipboard = Clipboard.create
