"""AG Grid with custom formatters."""

import dataclasses
import datetime
from typing import Any, TypedDict

import reflex as rx
from reflex.components import dynamic

import reflex_enterprise as rxe
from reflex_enterprise.components.ag_grid.resource import RendererParams

from .common import demo

# This ensures that `@rx.memo` components are available to cell_renderer functions.
def _bundle_renderer_libraries():
    """Make @rx.memo components available to cell_renderer functions.

    FIX for reflex>=0.9.8: memo components bundle under $/app_components/<module>
    and compile_app() resets bundled libraries before compiling pages, so this
    must run at page evaluation time, not only at import time.
    """
    # NOTE: "$/utils/components" (the demo original) no longer exists in reflex>=0.9.8
    dynamic.bundle_library("$/app_components/ag_grid/formatters")


_bundle_renderer_libraries()

# A regex defined as literal JS expression
GROUP_THREE_DIGITS = rx.vars.StringVar(r"/\B(?=(\d{3})+(?!\d))/g")


class RowData(TypedDict):
    """Type for the row data."""

    name: str
    percent: float
    country: str
    number: float
    symbol: str


# The row data used by this example.
row_data: list[RowData] = [
    {
        "name": "John",
        "percent": 0.56,
        "country": "USA",
        "number": 12345.6789,
        "symbol": "$",
    },
    {
        "name": "Anna",
        "percent": 0.25,
        "country": "Sweden",
        "number": 3243.6789,
        "symbol": "€",
    },
    {
        "name": "Tom",
        "percent": 0.12,
        "country": "Germany",
        "number": 12345.6789,
        "symbol": "£",
    },
    {
        "name": "Mike",
        "percent": 0.35,
        "country": "Canada",
        "number": 8745.1234,
        "symbol": "$",
    },
    {
        "name": "Chaz",
        "percent": 0.9999,
        "country": "Utopia",
        "number": 42.42,
        "symbol": "฿",
    },
]

# A formatter function can be defined in Javascript as a FunctionStringVar
PERCENT_FORMATTER = rx.vars.FunctionStringVar.create("""(params) => {
if (typeof params.value === 'undefined' || Number.isNaN(params.value)) {
    return '';
}
var rounded = (params.value * 100).toFixed(2);
return `${rounded}%`;}
""")


# Alternatively, a formatter can be defined as a Python function that accepts
# Var typed arguments. The following type is defined to ensure that Var
# Operations use the correct field types for the row automatically.
@dataclasses.dataclass
class FormatterParams:
    """Type for the formatter params."""

    data: RowData
    value: str | float


# These python formatter functions accept Var typed arguments and may only use
# Var Operations to construct the return value.
def currency_formatter(params: rx.vars.ObjectVar[FormatterParams]) -> str:
    """Format a number as currency."""
    rounded_value = round(params.data.number, 2).to_string()
    money_value = rounded_value.replace(GROUP_THREE_DIGITS, ",")
    return f"{params.data.symbol}{money_value}"


def flag_formatter(params: rx.vars.ObjectVar[FormatterParams]) -> rx.Var[str]:
    """Format a country as a flag emoji."""
    return rx.Var.create(
        {
            "USA": "🇺🇸",
            "Sweden": "🇸🇪",
            "Germany": "🇩🇪",
            "Canada": "🇨🇦",
        }
    ).get(params.value.to(str), "🏳️‍🌈")  # Default to rainbow flag if country not found


cols_defs: list[dict] = [
    {"field": "name"},
    {
        "field": "name reversed",
        # synthetic column getter defined as a string (plotly style).
        "value_getter": {"function": 'params.data.name.split("").reverse().join("")'},
    },
    # Formatter defined as a plain string, interpreted as a JS expression with `params` in scope.
    {"field": "country", "value_formatter": "params.value.toUpperCase()"},
    # Formatter defined as FunctionStringVar.
    {"field": "percent", "value_formatter": PERCENT_FORMATTER},
    {
        "field": "flag",
        # Synthetic column getter defined as a python lambda.
        "value_getter": lambda params: params.data.country,
        # Formatter defined as a python function of Var typed arguments.
        "value_formatter": flag_formatter,
    },
    {
        "field": "number",
        # Cell renderer defined as a python lambda with generic params.
        "cell_renderer": lambda params: rx.text(
            params.value,
            font_family="monospace",
            line_height="inherit",
            color="rebeccapurple",
        ),
    },
    {
        "field": "currency number",
        "value_getter": "params.data.number",
        # Formatter defined as a python function of Var typed arguments.
        "value_formatter": currency_formatter,
    },
    {
        "field": "scaled number",
        # Synthetic column getter defined as a plain string, interpreted as a JS expression with `params` in scope.
        "value_getter": "params.data.number * params.data.percent",
        # Formatter defined as a lambda with generic params (why .to(float) is needed).
        "value_formatter": lambda params: round(params.value.to(float), 4),
        # Renderer defined as a lambda with generic params.
        "cell_renderer": lambda params: rx.tooltip(
            rx.text(params.valueFormatted, line_height="inherit", width="fit-content"),
            content=f"{params.data.number} * {params.data.percent}",
            side="left",
        ),
    },
    {
        "field": "row counter",
        "header_name": "# Clicks (Last click)",
        # Cell renderer is complex, so use `@rx.memo` component to encapsulate it.
        "cell_renderer": lambda params: row_counter(rowid=params.node.id),
        "sortable": False,
    },
    {
        "field": "raw data",
        "header_name": "Show raw data",
        # The component was registered with the grid and can be passed by name.
        "cell_renderer": "dataDialog",
        "sortable": False,
    },
]


# The following state and rx.memo component shows how to include complex interactive
# elements in the grid using a cell_renderer (see "row counter" field).
class RowClickCounterState(rx.State):
    """Keep track of button clicks per row."""

    row_clicks: dict[str, int] = {}
    last_click: dict[str, datetime.datetime] = {}

    @rx.event
    def handle_click(self, rowid: str):
        """Handle a row click."""
        if rowid in self.row_clicks:
            self.row_clicks[rowid] += 1
        else:
            self.row_clicks[rowid] = 1
        self.last_click[rowid] = datetime.datetime.now()

    @rx.var
    def button_colors(self) -> dict[str, str]:
        """Get the button colors."""
        return {
            rowid: "red" if count % 2 == 0 else "blue"
            for rowid, count in self.row_clicks.items()
        }


# Because react hooks cannot be evaluated at runtime, it is not possible to
# directly return dynamic components (like rx.moment) or use component event
# triggers in a renderer function. Instead, wrapping the component in rx.memo
# enables the hooks/imports/custom code to be evaluated at compile time and the
# resulting component may then referenced from an eval'd renderer function.
@rx.memo
def row_counter(rowid: str) -> rx.Component:
    """Create a row counter component."""
    return rx.flex(
        rx.button(
            RowClickCounterState.row_clicks.get(rowid, 0),
            rx.cond(
                RowClickCounterState.last_click[rowid],
                rx.moment(
                    RowClickCounterState.last_click[rowid],
                    format="(mm:ss)",
                    interval=1000,
                    duration_from_now=True,
                ),
                " (∞)",
            ),
            color_scheme=RowClickCounterState.button_colors.get(rowid, "gray"),
            on_click=RowClickCounterState.handle_click(rowid),
        ),
        height="100%",
        align="center",
    )


# Alternatively, a component can be registered with the grid at compile time and
# then set by string in the column def. Use rxe.static decorator to allow hooks,
# but preclude direct usage from state. This is fine, because in state we
# reference it by the registered name.
@rxe.static
def data_dialog(params: rx.vars.ObjectVar[RendererParams]) -> rx.Component:
    """Create a data dialog component."""
    return rx.flex(
        rx.dialog.root(
            rx.dialog.trigger(rx.button("Raw Data")),
            rx.dialog.content(
                rx.dialog.title("Raw Row Data"),
                rx.dialog.description("JSON representation of the row data."),
                rx.code_block(
                    params.data.to_string(),
                ),
            ),
        ),
        height="100%",
        align="center",
    )


class FormatterState(rx.State):
    """State for the formatter demo."""

    cols_defs: list[dict] = cols_defs


def formatter_grid(id: str, column_defs: Any) -> rx.Component:
    """Create a grid with the given id, column defs and default props."""
    return rxe.ag_grid(
        id=id,
        column_defs=column_defs,
        row_data=row_data,
        width="100%",
        height="50vh",
        auto_size_strategy={"type": "fitCellContents"},
        components={
            "dataDialog": data_dialog,
        },
    )


@demo(
    route="/formatters",
    title="AG Grid Formatters",
    description="AG Grid with custom formatters.",
)
def formatter_page():
    """AG Grid with custom formatters."""
    _bundle_renderer_libraries()
    return rx.vstack(
        rx.box(
            row_counter(rowid=""), display="none"
        ),  # to ensure row_counter is compiled.
        rx.text(
            "Each of the three methods of setting column defs should work the same"
        ),
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger(
                    "Inline",
                    value="inline",
                ),
                rx.tabs.trigger(
                    "State",
                    value="state",
                ),
                rx.tabs.trigger(
                    "API",
                    value="api",
                ),
            ),
            rx.tabs.content(
                formatter_grid(
                    id="formatter-grid-bare",
                    column_defs=cols_defs,
                ),
                value="inline",
            ),
            rx.tabs.content(
                formatter_grid(
                    id="formatter-grid-state",
                    column_defs=FormatterState.cols_defs,
                ),
                value="state",
            ),
            rx.tabs.content(
                rx.button(
                    "Set column defs",
                    on_click=[
                        (api := rxe.ag_grid.api("formatter-grid-api")).set_grid_option(
                            "column_defs",
                            cols_defs,
                        ),
                        api.size_columns_to_fit(),
                    ],
                ),
                rx.button(
                    "Clear column defs",
                    on_click=rxe.ag_grid.api("formatter-grid-api").set_grid_option(
                        "columnDefs",
                        [],
                    ),
                ),
                formatter_grid(id="formatter-grid-api", column_defs=[]),
                value="api",
            ),
            default_value="inline",
            width="100%",
        ),
        width="100%",
    )
