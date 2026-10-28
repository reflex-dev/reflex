"""Private browser gesture surface forwarding validated commands to Reflex."""

from typing import Annotated, Any

import reflex as rx
from reflex.assets import asset
from reflex.event import passthrough_event_spec


class PointerSurface(rx.Component):
    """A local gesture adapter; Python owns all draft preference changes."""

    tag = "PointerSurface"
    editing: rx.Var[bool]
    revision: rx.Var[int]
    result: rx.Var[dict[str, Any]]
    on_command: Annotated[rx.EventHandler, passthrough_event_spec(dict)]

    @classmethod
    def create(cls, *children, **props) -> rx.Component:
        """Link the private gesture renderer around actual widget children.

        Returns:
            The browser gesture surface.
        """
        props["library"] = asset("PointerSurface.js", shared=True).importable_path
        return super().create(*children, **props)


pointer_surface = PointerSurface.create
