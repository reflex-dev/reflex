"""Exercise reused memo bodies, dependency updates, and imported-module HMR."""

import importlib.metadata
import os
from pathlib import Path

import reflex as rx

assert Path(rx.__file__).is_relative_to(
    Path(os.environ["SB"]) / "envs" / os.environ["QA_ENV"]
), rx.__file__

from .panels import metric_card
from .settings import BUTTON_RADIUS, PHASE
from .state import State


def dashboard(report: bool = False) -> rx.Component:
    """Build one of two routes sharing the same memo component.

    Args:
        report: Whether this is the report route.

    Returns:
        A dashboard with two memo cards and editable state.
    """
    return rx.vstack(
        rx.heading("Release dashboard: ", PHASE, id="phase"),
        rx.text(f"reflex={importlib.metadata.version('reflex')}", id="version"),
        rx.hstack(
            rx.link("Overview", href="/", id="overview-link"),
            rx.link("Report", href="/report", id="report-link"),
        ),
        rx.input(value=State.customer, on_change=State.rename, id="customer-input"),
        rx.hstack(
            rx.box(metric_card(title="Report" if report else "Revenue"), id="card-a"),
            rx.box(
                metric_card(title="Orders", caption="Explicit caption"), id="card-b"
            ),
        ),
        padding="24px",
    )


def index() -> rx.Component:
    """Render the overview route.

    Returns:
        The dashboard overview.
    """
    return dashboard()


def report() -> rx.Component:
    """Render the report route.

    Returns:
        The dashboard report.
    """
    return dashboard(True)


app = rx.App(style={rx.button: {"border_radius": BUTTON_RADIUS}})
app.add_page(index, route="/")
app.add_page(report, route="/report")
