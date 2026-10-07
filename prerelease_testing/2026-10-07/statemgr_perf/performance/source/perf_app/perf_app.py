"""Low-render-cost event page plus a separate Var/memo compile route."""

import reflex as rx
from .compile_page import compile_page
from .model import Workload


def index() -> rx.Component:
    """Build visible checks without rendering 5,000 rows on each event.

    Returns:
        Event controls and invariant outputs.
    """
    return rx.vstack(
        rx.heading("Shipment processing benchmark"),
        rx.button(
            "Process shipments", id="process", on_click=Workload.process_shipments
        ),
        rx.button(
            "Validate sorted output",
            id="validate",
            on_click=Workload.validate_shipments,
        ),
        rx.text(Workload.order_valid.to_string(), id="order-valid"),
        rx.text(Workload.rank_checksum, id="rank-checksum"),
        rx.text(Workload.sequence, id="sequence"),
        rx.text(Workload.checksum, id="checksum"),
        rx.text(Workload.work_ns, id="work-ns"),
        rx.text(Workload.work_cpu_ns, id="work-cpu-ns"),
        rx.text(Workload.value_0, id="first-value"),
        rx.text(Workload.value_49, id="last-value"),
        padding="24px",
    )


app = rx.App()
app.add_page(index)
app.add_page(compile_page, route="/compile")
