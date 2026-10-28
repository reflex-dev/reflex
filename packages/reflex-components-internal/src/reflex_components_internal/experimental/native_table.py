"""Experimental native HTML table with bounded client-side controls."""

from typing import Any

from reflex.assets import asset
from reflex.components.component import Component, NoSSRComponent
from reflex.event import EventHandler, passthrough_event_spec
from reflex.vars.base import Var


class NativeTable(NoSSRComponent):
    """A read-only semantic table; no AG Grid dependency or compatibility promise."""

    tag = "NativeTable"

    rows: Var[list[dict[str, Any]]]
    columns: Var[list[dict[str, Any]]]
    row_id_key: Var[str] = Var.create("id")
    page_size: Var[int] = Var.create(25)
    loading: Var[bool] = Var.create(False)
    error: Var[str] = Var.create("")
    on_selection_changed: EventHandler[passthrough_event_spec(list[str])]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the experimental browser table.

        Args:
            *children: Unused; this component renders its own content.
            **props: Data, columns and standard Reflex layout properties.

        Returns:
            Browser-only table component.
        """
        props.setdefault("width", "100%")
        asset("nativeTableModel.js", shared=True)
        props.setdefault(
            "library", asset("NativeTable.js", shared=True).importable_path
        )
        return super().create(*children, **props)


native_table = NativeTable.create
