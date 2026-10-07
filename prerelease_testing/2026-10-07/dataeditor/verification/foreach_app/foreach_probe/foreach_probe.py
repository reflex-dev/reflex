"""Compare an ordinary state-bound grid with the same grid inside foreach."""

import importlib.metadata
import os
from pathlib import Path

import reflex as rx

EXPECTED_ENV = Path(os.environ["SB"]) / "envs" / os.environ["QA_ENV"]
assert Path(rx.__file__).is_relative_to(EXPECTED_ENV), rx.__file__

COLUMNS = [{"title": "Name", "type": "str", "width": 160}]


class State(rx.State):
    """Provide two groups with distinguishable row values."""

    groups: list[list[list[str]]] = [[["first-a"], ["first-b"]], [["second-a"]]]


def grid(rows: rx.Var[list[list[str]]]) -> rx.Component:
    """Build the editor used by both control and reproduction.

    Args:
        rows: State or foreach rows for this editor.

    Returns:
        A fixed-size grid wrapper.
    """
    return rx.box(
        rx.data_editor(columns=COLUMNS, data=rows, width="240px", height="160px"),
        class_name="probe-grid",
        width="240px",
        height="160px",
    )


@rx.memo
def memo_grid(rows: rx.Var[list[list[str]]]) -> rx.Component:
    """Put the editor's data in a memo component's argument scope.

    Args:
        rows: Foreach rows for this editor.

    Returns:
        The same grid, with a memo component boundary.
    """
    return grid(rows)


def shell(title: str, child: rx.Component) -> rx.Component:
    """Wrap each scenario with version information and navigation.

    Args:
        title: The scenario name.
        child: The grid scenario.

    Returns:
        A complete page.
    """
    return rx.vstack(
        rx.heading(title, id="scenario"),
        rx.text(
            f"reflex={importlib.metadata.version('reflex')} "
            f"dataeditor={importlib.metadata.version('reflex-components-dataeditor')}",
            id="versions",
        ),
        rx.hstack(
            rx.link("Control", href="/"),
            rx.link("Foreach", href="/foreach"),
            rx.link("Memo foreach", href="/memo"),
        ),
        child,
        padding="20px",
    )


def index() -> rx.Component:
    """Render a grid using state data outside foreach.

    Returns:
        The positive-control page.
    """
    return shell("Control", grid(State.groups[0]))


def foreach_page() -> rx.Component:
    """Render the minimal foreach reproduction.

    Returns:
        Two editors whose data comes from the foreach argument.
    """
    return shell("Foreach", rx.hstack(rx.foreach(State.groups, grid)))


def memo_page() -> rx.Component:
    """Render the same foreach through a memo component boundary.

    Returns:
        A control for callback argument scoping.
    """
    return shell(
        "Memo foreach", rx.hstack(rx.foreach(State.groups, lambda rows: memo_grid(rows=rows)))
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(foreach_page, route="/foreach")
app.add_page(memo_page, route="/memo")
