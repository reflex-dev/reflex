"""Actual Reflex event roundtrips into the server-owned Python draft engine."""

import json
from collections.abc import Callable
from typing import Any, cast

import numpy as np
import reflex as rx
import reflex_xy
from reflex.vars.object import ObjectVar
from reflex_components_internal.components.base.button import button as shared_button
from reflex_components_internal.components.base.community_grid import community_grid
from reflex_components_internal.components.base.input import input as shared_input
from reflex_components_internal.experimental.customization import (
    Item,
    Option,
    Registry,
    Widget,
)

from session_demo.model import Session
from session_demo.pointer import pointer_surface

ROWS = [
    {
        "id": f"acct-{i}",
        "name": f"Account {i:02d}",
        "region": ("North", "South", "West")[i % 3],
        "revenue": 1200 + i * 173,
    }
    for i in range(1, 31)
]
DATA = {
    "day": np.arange(1, 15, dtype=float),
    "actual": np.array(
        [12, 15, 14, 18, 22, 20, 24, 23, 26, 29, 27, 31, 34, 33], dtype=float
    ),
    "plan": np.array(
        [13, 14, 16, 17, 20, 21, 23, 24, 25, 28, 29, 30, 32, 34], dtype=float
    ),
}


def render_trend(
    card: ObjectVar[dict[str, Any]], preview: bool = False
) -> rx.Component:
    """Render the real XY adapter from the same registry entry in both contexts.

    Returns:
        The registered content or its projected presentation values.
    """

    def chart(hidden: bool) -> rx.Component:
        return reflex_xy.chart(
            reflex_xy.line("day", "actual", name="Actual", color="#6e56cf"),
            reflex_xy.line("day", "plan", name="Plan", color="#12a594"),
            reflex_xy.legend(
                show=not hidden, loc="lower center", anchor=(0.5, 1.06), ncols=2
            ),
            reflex_xy.interaction_config(
                navigation=True,
                pan=True,
                zoom=True,
                select=False,
                brush=False,
                default_drag_action="pan",
            ),
            reflex_xy.x_axis(grid=False, label="Day"),
            reflex_xy.y_axis(grid=True, label="Synthetic revenue"),
            data=DATA,
            padding=(48, 12, 64, 54),
            height="260px" if preview else card["content_height"].to(str) + "px",
            width="100%",
            style={
                "font-family": "Inter, system-ui, sans-serif",
                "--chart-bg": "#fcfcfc",
                "--chart-text": "#202020",
                "--chart-grid": "#e8e8e8",
                "--chart-axis": "#d9d9d9",
            },
        )

    return rx.cond(card["legend_hidden"], chart(True), chart(False))


def render_accounts(
    card: ObjectVar[dict[str, Any]], preview: bool = False
) -> rx.Component:
    """Render the actual Community wrapper with independent renderer instances.

    Returns:
        The registered content or its projected presentation values.
    """
    return community_grid(
        row_data=ROWS,
        column_defs=[
            {"field": "name", "minWidth": 130},
            {"field": "region", "minWidth": 110},
            {"field": "revenue", "filter": "agNumberColumnFilter", "minWidth": 120},
        ],
        page_size=card["page_size"].to(int),
        pagination=not preview,
        quick_filter=State.query,
        height="230px" if preview else card["content_height"].to(str) + "px",
        initial_state=card["grid_state"].to(dict),
        on_state_changed=lambda state: State.grid_presentation(card["id"], state),
        selection_mode="none",
    )


def render_search(
    card: ObjectVar[dict[str, Any]], preview: bool = False
) -> rx.Component:
    """Render the shared search input without a business-write handler.

    Returns:
        The registered content or its projected presentation values.
    """
    return rx.el.div(
        rx.el.label(
            "Find an account",
            html_for=rx.cond(
                preview, "catalog-search", "account-search-" + card["id"].to(str)
            ),
        ),
        shared_input.root(
            value=State.query,
            on_change=State.set_query,
            placeholder="Try North or Account 12",
            id=rx.cond(
                preview, "catalog-search", "account-search-" + card["id"].to(str)
            ),
            style={"width": "100%"},
        ),
        rx.el.p(
            "Search filters the loaded Community grid. It writes no business data.",
            class_name="muted",
        ),
        class_name="search-content",
    )


REGISTRY = Registry((
    Widget(
        "trend",
        render_trend,
        (Option("legend", ("outside", "hidden"), "outside"),),
        min_width=6,
        min_height=3,
        max_height=8,
    ),
    Widget(
        "accounts",
        render_accounts,
        (Option("page_size", (10, 25), 10),),
        min_width=6,
        min_height=3,
        max_height=8,
    ),
    Widget("search", render_search, min_width=6, min_height=2, max_height=5),
))
TITLES = {"trend": "Revenue trend", "accounts": "Accounts", "search": "Account search"}


def card_data(item: Item) -> dict[str, Any]:
    """Project validated presentation preferences for the Reflex render tree.

    Returns:
        The registered content or its projected presentation values.
    """
    options = dict(item.options)
    return {
        "id": item.id,
        "widget": item.widget,
        "title": TITLES[item.widget],
        "width": item.width,
        "height": item.height,
        "content_height": item.height * 72 + 22,
        "min_height": REGISTRY.widget(item.widget).min_height,
        "max_height": REGISTRY.widget(item.widget).max_height,
        "legend_hidden": options.get("legend") == "hidden",
        "page_size": options.get("page_size", 10),
    }


def pointer_payload(command: dict[str, Any]) -> dict[str, Any]:
    """Project browser gesture metadata into the exact Python command contract.

    Returns:
        The operation-specific command validated by Session.pointer.
    """
    keys = {
        "add": ("op", "revision", "widget", "before"),
        "move": ("op", "revision", "id", "before"),
        "resize": ("op", "revision", "id", "width", "height"),
    }
    operation = command.get("op")
    if type(operation) is not str or operation not in keys:
        message = "Unsupported pointer operation"
        raise ValueError(message)
    return {key: command.get(key) for key in keys[operation]}


class State(rx.State):
    """Keep each client's server transaction separate from all business records."""

    cards: list[dict[str, Any]] = []
    editing: bool = False
    catalog_open: bool = False
    navigation: str = "top"
    query: str = ""
    error: str = ""
    status: str = "Session-only personal view. Server restart clears saved layouts."
    engine_calls: int = 0
    operation: str = "Session defaults"
    preferences_json: str = ""
    pointer_result: dict[str, Any] = {}
    _grid_states: dict[str, dict[str, Any]] = {}
    _session: Session | None = None

    def _get_session(self) -> Session:
        if self._session is None:
            self._session = Session(REGISTRY)
        return self._session

    def _sync(self):
        session = self._get_session()
        self.cards = [
            {**card_data(item), "grid_state": self._grid_states.get(item.id, {})}
            for item in session.current.items
        ]
        self.navigation = session.current.navigation
        self.editing = session.draft is not None
        self.engine_calls = session.engine_calls
        self.operation = session.last_operation
        self.preferences_json = json.dumps(
            {
                "navigation": session.current.navigation,
                "items": [
                    {
                        "id": item.id,
                        "x": item.x,
                        "y": item.y,
                        "width": item.width,
                        "height": item.height,
                        "options": dict(item.options),
                    }
                    for item in session.current.items
                ],
            },
            sort_keys=True,
        )

    def _perform(self, operation: Callable[[], None]):
        self.error = ""
        try:
            operation()
        except (ValueError, OSError) as error:
            self.error = str(error)
        self._sync()

    @rx.event
    def grid_presentation(self, item_id: str, value: dict[str, Any]):
        """Retain Community presentation for real catalog-to-canvas additions."""
        allowed = {item.id for item in self._get_session().current.items} | {
            "preview-accounts"
        }
        if item_id in allowed:
            self._grid_states[item_id] = value

    @rx.event
    def pointer_command(self, command: dict[str, Any]):
        """Validate one completed pointer command through the actual Python Draft."""
        self.error = ""
        result: dict[str, Any] = {}
        operation = command.get("op")
        try:
            payload = pointer_payload(command)
            result = self._get_session().pointer(payload)
            if operation == "add" and command.get("widget") == "accounts":
                self._grid_states[result["id"]] = dict(
                    self._grid_states.get("preview-accounts", {})
                )
        except ValueError as error:
            self.error = str(error)
        self._sync()
        self.pointer_result = {
            "request_id": command.get("request_id", ""),
            "accepted": not self.error,
            "id": result.get("id", ""),
            "error": self.error,
        }

    @rx.event
    def set_query(self, value: str):
        """Filter the synthetic loaded grid through a real server event."""
        self.query = value

    @rx.event
    def load(self):
        """Initialize this client session and render its saved view."""
        self._sync()

    @rx.event
    def begin(self):
        """Enter a Python Draft transaction for this client."""
        self._perform(self._get_session().begin)
        self.status = "Editing my session layout. Changes remain a draft."

    @rx.event
    def cancel(self):
        """Discard draft changes and restore session preferences."""
        self._perform(self._get_session().cancel)
        if not self.error:
            self.catalog_open = False
            self.status = "Draft canceled. Saved session layout restored."

    @rx.event
    def save(self):
        """Synchronously save only this session view under the Reflex state lock."""
        self._perform(self._get_session().save)
        if not self.error:
            self.catalog_open = False
            self.status = "My layout saved for this browser session only."

    @rx.event
    def reset_layout(self):
        """Stage builder defaults without committing the session view."""
        self._perform(self._get_session().reset)
        self.status = "Defaults staged. Save to keep them or Cancel to restore my view."

    @rx.event
    def move(self, item_id: str, offset: int):
        """Apply an explicit before or after command through Python Draft."""
        self._perform(lambda: self._get_session().move(item_id, offset))

    @rx.event
    def size(self, item_id: str):
        """Stage the requested instance width through Python Draft."""
        self._perform(lambda: self._get_session().size(item_id))

    @rx.event
    def toggle_setting(self, item_id: str, widget: str):
        """Toggle the setting allowlisted for the registered widget."""
        item = next(
            item for item in self._get_session().current.items if item.id == item_id
        )
        options = dict(item.options)
        if widget == "trend":
            self._perform(
                lambda: self._get_session().option(
                    item_id,
                    "legend",
                    "outside" if options.get("legend") == "hidden" else "hidden",
                )
            )
        elif widget == "accounts":
            self._perform(
                lambda: self._get_session().option(
                    item_id,
                    "page_size",
                    25 if options.get("page_size", 10) == 10 else 10,
                )
            )

    @rx.event
    def set_navigation(self, value: str):
        """Stage top or left navigation through Python Draft."""
        self._perform(lambda: self._get_session().navigation(value))

    @rx.event
    def add(self, key: str):
        """Append one builder-approved widget through Python Draft."""
        self._perform(lambda: self._get_session().add(key))

    @rx.event
    def toggle_catalog(self):
        """Toggle the dock without staging geometry and focus the visible target.

        Returns:
            A focus event after the new catalog state renders.
        """
        self.catalog_open = not self.catalog_open
        return rx.set_focus(
            "catalog-title" if self.catalog_open else "add-widgets-toggle"
        )


def button(label: Any, action: Any, **props: Any) -> rx.Component:
    """Use the actual shared button renderer with existing palette tokens.

    Returns:
        The registered content or its projected presentation values.
    """
    return shared_button(label, on_click=action, variant="outline", size="sm", **props)


def render_widget(
    card: ObjectVar[dict[str, Any]], preview: bool = False
) -> rx.Component:
    """Dispatch both catalog and canvas through the same registered renderers.

    Returns:
        The registered content or its projected presentation values.
    """
    return cast(
        rx.Component,
        rx.match(
            card["widget"],
            *(
                (key, cast(rx.Component, REGISTRY.widget(key).render(card, preview)))
                for key in TITLES
            ),
            rx.el.p("Unavailable widget"),
        ),
    )


def canvas_card(card: ObjectVar[dict[str, Any]]) -> rx.Component:
    """Wrap actual content in reversible edit boundaries and keyboard commands.

    Returns:
        The registered content or its projected presentation values.
    """
    return rx.el.section(
        rx.el.div(
            rx.el.div(
                rx.cond(
                    State.editing,
                    button(
                        "⠿",
                        None,
                        aria_label="Drag " + card["title"].to(str),
                        custom_attrs={"data-pointer-action": "move"},
                        class_name="pointer-grip",
                    ),
                ),
                rx.el.h2(card["title"]),
                class_name="widget-title",
            ),
            rx.cond(
                State.editing,
                rx.el.div(
                    button(
                        "Move before",
                        State.move(card["id"], -1),
                        aria_label="Move " + card["title"].to(str) + " before",
                    ),
                    button(
                        "Move after",
                        State.move(card["id"], 1),
                        aria_label="Move " + card["title"].to(str) + " after",
                    ),
                    button(
                        rx.cond(card["width"] == 12, "Half width", "Full width"),
                        State.size(card["id"]),
                    ),
                    rx.cond(
                        card["widget"] != "search",
                        button(
                            rx.cond(
                                card["widget"] == "trend",
                                rx.cond(
                                    card["legend_hidden"], "Show legend", "Hide legend"
                                ),
                                rx.cond(card["page_size"] == 10, "25 rows", "10 rows"),
                            ),
                            State.toggle_setting(card["id"], card["widget"]),
                        ),
                    ),
                    class_name="edit-commands",
                ),
            ),
            class_name="card-heading",
        ),
        rx.el.div(
            render_widget(card),
            class_name="widget-content",
            style={"min_height": card["content_height"].to(str) + "px"},
            custom_attrs={"data-widget-content": ""},
        ),
        rx.cond(
            State.editing,
            button(
                "↘ Resize",
                None,
                aria_label="Resize " + card["title"].to(str),
                custom_attrs={"data-pointer-action": "resize"},
                class_name="pointer-resize",
            ),
        ),
        class_name=rx.cond(card["width"] == 6, "widget half", "widget full"),
        key=card["id"],
        custom_attrs={
            "data-widget": card["widget"],
            "data-instance": card["id"],
            "data-columns": card["width"],
            "data-rows": card["height"],
            "data-min-height": card["min_height"],
            "data-max-height": card["max_height"],
        },
    )


def catalog():
    """Keep a nonmodal dock with actual registered content previews.

    Returns:
        The registered content or its projected presentation values.
    """
    return rx.el.aside(
        rx.el.div(
            rx.el.h2("Add widgets", id="catalog-title", tab_index=-1),
            button("Close catalog", State.toggle_catalog),
            class_name="catalog-heading",
        ),
        rx.el.p(
            "Builder-approved widgets. Adding appends a new instance.",
            class_name="muted",
        ),
        *[
            rx.el.div(
                rx.el.div(
                    button(
                        "⠿",
                        None,
                        aria_label="Drag add " + TITLES[key],
                        custom_attrs={"data-pointer-action": "add"},
                        class_name="pointer-grip",
                    ),
                    rx.el.h3(TITLES[key]),
                    class_name="widget-title",
                ),
                render_widget(
                    rx.Var.create({
                        "id": "preview-" + key,
                        "widget": key,
                        "title": TITLES[key],
                        "legend_hidden": False,
                        "page_size": 10,
                        "grid_state": {},
                        "content_height": 260,
                    }),
                    True,
                ),
                button("Add " + TITLES[key], State.add(key)),
                class_name="catalog-card",
                custom_attrs={"data-catalog-widget": key},
            )
            for key in TITLES
        ],
        class_name="catalog",
        aria_label="Widget catalog",
        id="widget-catalog",
    )


def index():
    """Render the bounded server-session proof without overlay or backdrop.

    Returns:
        The registered content or its projected presentation values.
    """
    return rx.el.div(
        rx.el.nav(
            rx.el.strong("Reflex / Overview"),
            rx.el.span("Workspace", class_name="muted"),
            class_name="navigation",
            aria_label="Workspace navigation",
        ),
        rx.el.main(
            rx.el.header(
                rx.el.div(
                    rx.el.p("MY WORKSPACE", class_name="eyebrow"),
                    rx.el.h1("A view that fits your work"),
                    rx.el.p(
                        "Synthetic accounts · session-only personal layout",
                        class_name="muted",
                    ),
                ),
                rx.el.div(
                    rx.cond(
                        State.editing,
                        rx.el.div(
                            button(
                                "Add widgets",
                                State.toggle_catalog,
                                id="add-widgets-toggle",
                                aria_expanded=State.catalog_open,
                                aria_controls="widget-catalog",
                            ),
                            button("Top nav", State.set_navigation("top")),
                            button("Left nav", State.set_navigation("left")),
                            button("Reset", State.reset_layout),
                            button("Cancel", State.cancel),
                            button("Save my session layout", State.save),
                            class_name="toolbar",
                        ),
                        button("Customize", State.begin),
                    ),
                ),
                class_name="page-heading",
            ),
            rx.el.p(State.status, role="status", id="session-status"),
            rx.cond(State.error != "", rx.el.p(State.error, role="alert")),
            pointer_surface(
                rx.el.div(
                    rx.el.div(
                        rx.foreach(State.cards, canvas_card),
                        class_name=rx.cond(State.editing, "canvas editing", "canvas"),
                    ),
                    rx.cond(State.editing & State.catalog_open, catalog()),
                    class_name="workspace",
                ),
                editing=State.editing,
                revision=State.engine_calls,
                result=State.pointer_result,
                on_command=State.pointer_command,
            ),
            rx.el.details(
                rx.el.summary("Session verification"),
                rx.el.p(
                    "Server engine calls: ",
                    rx.el.span(State.engine_calls, id="engine-calls"),
                ),
                rx.el.p(State.operation, id="engine-operation"),
                rx.el.pre(State.preferences_json, id="preferences"),
                class_name="session-evidence",
            ),
        ),
        class_name=rx.cond(
            State.navigation == "left", "shell nav-left", "shell nav-top"
        ),
    )


app = rx.App(stylesheets=["/session.css"])
app.add_page(index, on_load=State.load, title="Reflex personal layout session")
