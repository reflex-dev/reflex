"""Real dashboard combining component prerelease changes with state APIs."""

import json
from typing import Any

import plotly.graph_objects as go
import reflex as rx
from reflex_components_radix.primitives.progress import progress as primitive_progress
from reflex_components_radix.primitives.slider import slider as primitive_slider


class Dashboard(rx.State):
    """Server state shared by analytics and operations panels."""

    currency: str = "$"
    layout: dict[str, Any] = {"title": "Revenue overview", "height": 270}
    revenue: list[dict[str, Any]] = [
        {"name": "Jan", "value": 120},
        {"name": "Feb", "value": 180},
        {"name": "Mar", "value": 150},
    ]
    plot_data: go.Figure = go.Figure(
        data=[{"x": ["Jan", "Feb", "Mar"], "y": [120, 180, 150], "type": "bar"}]
    )
    submitted: str = ""
    progress: int = 25
    uploaded: str = ""
    toast_count: int = 0
    media_plays: int = 0
    icon_name: str = "chart-no-axes-combined"
    table_data: list[list[str]] = [["Alpha", "12"], ["Beta", "9"]]
    edited: str = ""
    code_background: str = "rgb(17, 34, 51)"

    @rx.event
    def update_analytics(self):
        """Update titles, chart data, formatter metadata and icon together."""
        self.currency = "€"
        self.layout = {"title": "Updated revenue", "height": 270}
        self.revenue = [{"name": "Apr", "value": 210}, {"name": "May", "value": 90}]
        self.plot_data = go.Figure(
            data=[{"x": ["Apr", "May"], "y": [210, 90], "type": "bar"}]
        )
        self.icon_name = "check"
        self.code_background = "rgb(51, 34, 17)"

    @rx.event
    def submit(self, payload: dict):
        """Save the real submitted field payload.

        Args:
            payload: Fields sent by the browser form.
        """
        self.submitted = json.dumps(dict(payload), sort_keys=True)

    @rx.event
    def set_progress(self, values: list[float]):
        """Drive a progress bar from the updated Radix slider.

        Args:
            values: Selected slider values.
        """
        self.progress = int(values[0])

    @rx.event
    async def upload(self, files: list[rx.UploadFile]):
        """Read actual uploaded attachments without persisting them.

        Args:
            files: Uploaded files from the dropzone.
        """
        self.uploaded = json.dumps(
            [
                {"name": item.filename, "bytes": len(await item.read())}
                for item in files
            ],
            sort_keys=True,
        )

    @rx.event
    def acknowledge(self):
        """Count the toast action's backend roundtrip."""
        self.toast_count += 1

    @rx.event
    def played(self):
        """Count local media playback events."""
        self.media_plays += 1

    @rx.event
    def edit_cell(self, position: tuple[int, int], cell: dict[str, Any]):
        """Store an edited dataeditor cell.

        Args:
            position: Column and row of the edited cell.
            cell: New grid cell data.
        """
        col, row = position
        self.table_data[row][col] = str(cell["data"])
        self.edited = json.dumps({"position": position, "value": cell["data"]})


class WrappedControl(rx.Component):
    """A custom ID-backed native control explicitly included in form data."""

    tag = "DispatchControl"
    _is_form_control = True
    default_value: rx.Var[str]

    def add_imports(self) -> dict:
        """Import the React ref forwarding API used by the custom control.

        Returns:
            The required React import.
        """
        return {"react": [rx.ImportVar(tag="forwardRef")]}

    def add_custom_code(self) -> list[str]:
        """Define a real custom React control that forwards its input ref.

        Returns:
            The custom control implementation.
        """
        return [
            "const DispatchControl = forwardRef((props, ref) => <input {...props} ref={ref} />);"
        ]


class InventoryCard(rx.ComponentState):
    """An independently stateful inventory card."""

    stock: int = 0

    @rx.event
    def increase(self):
        """Add one unit to this inventory card."""
        self.stock += 1

    @classmethod
    def get_component(cls, label: str, identifier: str) -> rx.Component:
        """Build one independent card with a case-condition-only match.

        Args:
            label: Visible inventory name.
            identifier: Stable browser-test identifier.

        Returns:
            The card with its own count and status.
        """
        return rx.card(
            rx.heading(label, size="3"),
            rx.match(
                True,
                (cls.stock > 0, rx.badge("In stock", color_scheme="green")),
                rx.badge("Out of stock", color_scheme="red"),
            ),
            rx.text(cls.stock, id=f"stock-{identifier}"),
            rx.button(
                "Receive stock", on_click=cls.increase, id=f"receive-{identifier}"
            ),
            id=f"inventory-{identifier}",
        )


local_mode = rx._x.client_state(default="compact")


@rx.memo
def report_markdown(content: rx.Var[str]) -> rx.Component:
    """Memoize a Markdown report component.

    Args:
        content: Markdown content to render.

    Returns:
        The report panel.
    """
    return rx.markdown(content)


@rx.memo
def state_plot(layout: rx.Var[dict[str, Any]], data: rx.Var[go.Figure]) -> rx.Component:
    """Memoize the chart while preserving its state-derived layout.

    Args:
        layout: Plotly layout containing a string title.
        data: Plotly traces.

    Returns:
        The stateful Plotly chart.
    """
    return rx.plotly(data=data, layout=layout, id="plot-state", width="100%")


@rx.memo
def availability_panel() -> rx.Component:
    """Render a literal-subject match whose only state is in the condition.

    Returns:
        A currency-dependent availability label.
    """
    return rx.match(
        True,
        (Dashboard.currency == "€", rx.text("European report", id="memo-match")),
        rx.text("US report", id="memo-match"),
    )


def index() -> rx.Component:
    """Build a combined analytics and operations dashboard.

    Returns:
        The dashboard page.
    """
    formatter = rx.vars.FunctionStringVar.create(
        "((prefix, value) => prefix + Number(value).toFixed(0))"
    ).partial(Dashboard.currency)
    return rx.vstack(
        rx.heading("Published component dashboard"),
        rx.text(Dashboard.router.session.client_token, id="token"),
        rx.hstack(
            rx.icon("activity", id="static-icon"),
            rx.icon(Dashboard.icon_name, id="dynamic-icon"),
        ),
        rx.hstack(
            rx.button(
                "Update analytics",
                id="update-analytics",
                on_click=Dashboard.update_analytics,
            ),
            rx.button(
                "Detailed view",
                id="local-mode-button",
                on_click=local_mode.set_value("detailed"),
            ),
            rx.text(local_mode.value, id="local-mode"),
            availability_panel(),
        ),
        rx.box(
            rx.foreach(
                ["Primary", "Secondary"],
                lambda label: rx.match(
                    True,
                    (Dashboard.currency == "€", rx.text(label + " euro")),
                    rx.text(label + " dollar"),
                ),
            ),
            id="foreach-match",
        ),
        rx.box(
            report_markdown(
                content="# Weekly report\n\n**Revenue** is healthy.\n\n- Orders fulfilled\n- Stock reviewed\n\n|Team|Status|\n|---|---|\n|Ops|Ready|"
            ),
            id="markdown-report",
        ),
        rx.hstack(
            InventoryCard.create(label="Warehouse Alpha", identifier="alpha"),
            InventoryCard.create(label="Warehouse Beta", identifier="beta"),
        ),
        rx.box(
            rx.recharts.bar_chart(
                rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
                rx.recharts.x_axis(data_key="name"),
                rx.recharts.y_axis(tick_formatter=formatter),
                rx.recharts.bar(data_key="value", fill="#6366f1"),
                data=Dashboard.revenue,
                width="100%",
                height=260,
            ),
            id="recharts-panel",
            width="100%",
        ),
        rx.grid(
            rx.plotly(
                data=go.Figure(data=[{"x": [1, 2], "y": [4, 7], "type": "scatter"}]),
                layout={"title": "Static string title", "height": 270},
                id="plot-static",
            ),
            rx.plotly(
                data=go.Figure(data=[{"x": [1, 2], "y": [3, 6], "type": "bar"}]),
                layout={
                    "title": {
                        "text": "Object title retained",
                        "font": {"color": "rgb(128, 0, 128)"},
                    },
                    "height": 270,
                },
                id="plot-object",
            ),
            state_plot(layout=Dashboard.layout, data=Dashboard.plot_data),
            columns="3",
            width="100%",
        ),
        rx.el.form(
            rx.el.label("Contact", html_for="contact", id="contact-label"),
            rx.box(
                rx.input(id="contact", default_value="buyer@example.com"),
                id="contact-wrapper",
            ),
            rx.el.input(id="empty-control"),
            WrappedControl.create(id="custom-control", default_value="custom-value"),
            rx.el.textarea(name="notes", default_value="Ready for dispatch"),
            rx.text("Only controls belong in the payload", id="validation-message"),
            rx.box(
                rx.code_block(
                    "print('dispatch')",
                    language="python",
                    can_copy=True,
                    wrap_long_lines=True,
                    custom_style={"background_color": Dashboard.code_background},
                ),
                id="code-in-form",
            ),
            rx.box(
                rx._x.code_block(
                    "print('default transformer') # [!code highlight]",
                    language="python",
                    use_transformers=True,
                ),
                id="shiki-default",
            ),
            rx.box(
                rx._x.code_block(
                    "print('shiki upgraded') # [!code highlight]",
                    language="python",
                    can_copy=True,
                    transformers=[
                        rx._x.code_block.create_transformer(
                            "@shikijs/transformers@4.5.0",
                            ["transformerNotationHighlight"],
                        )
                    ],
                ),
                id="shiki-in-form",
            ),
            rx.el.button("Submit dispatch", type="submit", id="dispatch-submit"),
            on_submit=Dashboard.submit,
            id="dispatch-form",
        ),
        rx.text(Dashboard.submitted, id="submitted"),
        rx.slider(
            default_value=[25],
            min=0,
            max=100,
            step=5,
            on_change=Dashboard.set_progress,
            id="progress-slider",
            width="320px",
        ),
        rx.progress(
            value=Dashboard.progress, max=100, id="progress-bar", width="320px"
        ),
        rx.text(Dashboard.progress, id="progress-value"),
        primitive_slider(
            default_value=[25],
            min=0,
            max=100,
            step=5,
            on_value_change=Dashboard.set_progress,
            id="primitive-slider",
        ),
        primitive_progress(value=Dashboard.progress, max=100, id="primitive-progress"),
        rx.hstack(
            rx.moment(
                "2024-03-14T15:09:26", format="dddd D MMMM YYYY", id="moment-english"
            ),
            rx.moment(
                "2024-03-14T15:09:26",
                format="dddd D MMMM YYYY",
                locale="fr",
                id="moment-french",
            ),
            rx.moment(
                date="2026-08-30T00:30:00",
                duration="2026-08-30T00:00:00",
                format="h [hrs] m [min]",
                trim="large",
                id="moment-duration",
            ),
            rx.moment(
                "2024-03-14T15:00:00Z",
                format="YYYY-MM-DD HH:mm",
                tz="Europe/Paris",
                id="moment-timezone",
            ),
        ),
        rx.upload.root(
            rx.text("Drop attachments"),
            id="attachments",
            multiple=True,
            max_files=2,
            accept={"text/plain": [".txt"]},
        ),
        rx.button(
            "Send attachments",
            on_click=Dashboard.upload(rx.upload_files(upload_id="attachments")),
            id="send-attachments",
        ),
        rx.text(Dashboard.uploaded, id="uploaded"),
        rx.button(
            "Confirm dispatch",
            id="show-toast",
            on_click=rx.toast(
                "Dispatch ready",
                action={"label": "Acknowledge", "on_click": Dashboard.acknowledge},
                duration=30000,
            ),
        ),
        rx.text(Dashboard.toast_count, id="toast-count"),
        rx.box(
            rx.data_table(
                data=Dashboard.table_data,
                columns=["Product", "Stock"],
                pagination=True,
                search=True,
                sort=True,
            ),
            id="gridjs-panel",
            width="100%",
        ),
        rx.box(
            rx.data_editor(
                data=Dashboard.table_data,
                columns=[
                    {"title": "Product", "id": "product", "type": "str"},
                    {"title": "Stock", "id": "stock", "type": "str"},
                ],
                on_cell_edited=Dashboard.edit_cell,
                width="480px",
                height="180px",
            ),
            id="dataeditor-panel",
        ),
        rx.text(Dashboard.edited, id="edited"),
        rx.box(
            rx.audio(
                src="/tone.wav",
                controls=True,
                on_play=Dashboard.played,
                width="400px",
                height="60px",
            ),
            id="media-panel",
        ),
        rx.text(Dashboard.media_plays, id="media-plays"),
        width="100%",
        max_width="1400px",
        padding="24px",
        spacing="5",
        align="stretch",
    )


app = rx.App()
app.add_page(index)
