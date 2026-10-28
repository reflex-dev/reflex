"""Experimental read-only AG Grid Community adapter."""

from typing import Any, Literal

from reflex.assets import asset
from reflex.components.component import Component, NoSSRComponent
from reflex.event import EventHandler, passthrough_event_spec
from reflex.vars.base import Var


class CommunityGrid(NoSSRComponent):
    """A client-side Community grid with a deliberately bounded configuration."""

    tag = "CommunityGrid"
    lib_dependencies: list[str] = [
        "ag-grid-community@34.3.1",
        "ag-grid-react@34.3.1",
    ]

    row_data: Var[list[dict[str, Any]]]
    column_defs: Var[list[dict[str, Any]]]
    row_id_key: Var[str] = Var.create("id")
    selection_mode: Var[Literal["none", "singleRow", "multiRow"]] = Var.create("none")
    pagination: Var[bool] = Var.create(True)
    page_size: Var[int] = Var.create(25)
    quick_filter: Var[str] = Var.create("")
    loading: Var[bool] = Var.create(False)
    initial_state: Var[dict[str, Any]]
    on_state_changed: EventHandler[passthrough_event_spec(dict)]
    on_selection_changed: EventHandler[passthrough_event_spec(list[str])]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the grid and link its browser-only renderer.

        Args:
            *children: Unused; the grid renders its own content.
            **props: Grid properties and normal Reflex layout properties.

        Returns:
            The grid component.
        """
        props.setdefault("height", "420px")
        props.setdefault("width", "100%")
        if "library" not in props:
            props["library"] = asset("CommunityGrid.js", shared=True).importable_path
        return super().create(*children, **props)


community_grid = CommunityGrid.create
