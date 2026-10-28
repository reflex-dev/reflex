"""Synthetic Reflex adapter runtime fixture."""

import reflex_components_internal as ui

import reflex as rx


class State(rx.State):
    """Keep only synthetic grid event results."""

    selected: str = "none"
    sort: str = "none"

    @rx.event
    def selection(self, ids: list[str]):
        """Receive selected stable row IDs."""
        self.selected = ",".join(ids)

    @rx.event
    def view_updated(self, state: dict):
        """Receive a small state summary for the runtime probe."""
        self.sort = str(state.get("sort", {}))


def index():
    """Render the actual Python adapter and event results.

    Returns:
        The synthetic grid page.
    """
    return rx.vstack(
        ui.community_grid(
            row_data=[
                {"id": "a", "name": "Account A", "revenue": 123},
                {"id": "b", "name": "Account B", "revenue": 456},
            ],
            column_defs=[
                {"field": "name"},
                {"field": "revenue", "filter": "agNumberColumnFilter"},
            ],
            selection_mode="multiRow",
            on_selection_changed=State.selection,
            on_state_changed=State.view_updated,
        ),
        rx.text(State.selected, id="selected"),
        rx.text(State.sort, id="sort"),
        width="100%",
        padding="24px",
    )


app = rx.App()
app.add_page(index)
