"""The declaration of a component's parity matrix, and its cells.

A full cross product of what the components vary by (variant, size, 32 colors,
contrast, radius, appearance, state, viewport) is far too large to render, so a
matrix says which dimensions cross and which are swept one at a time from a
base cell.
"""

from __future__ import annotations

import dataclasses
import itertools
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

# Dimensions the runner provides rather than the component: they are not props.
APPEARANCE = "appearance"
STATE = "state"
VIEWPORT = "viewport"
ENVIRONMENT = (APPEARANCE, STATE, VIEWPORT)

LIGHT = "light"
DARK = "dark"
REST = "rest"
# States driven through the browser: the pointer and the keyboard.
HOVER = "hover"
FOCUS_VISIBLE = "focus-visible"
ACTIVE = "active"

# The width of the page unless a matrix sweeps the viewport.
DEFAULT_VIEWPORT = 1280

ENVIRONMENT_BASE: Mapping[str, Any] = {
    APPEARANCE: LIGHT,
    STATE: REST,
    VIEWPORT: DEFAULT_VIEWPORT,
}

# What the computed-style diff reads unless a matrix says otherwise: the
# longhands a component's look is made of.
DEFAULT_PROPERTIES: tuple[str, ...] = (
    "display",
    "position",
    "box-sizing",
    "width",
    "height",
    "min-width",
    "min-height",
    "max-width",
    "max-height",
    "margin-top",
    "margin-right",
    "margin-bottom",
    "margin-left",
    "padding-top",
    "padding-right",
    "padding-bottom",
    "padding-left",
    "border-top-width",
    "border-right-width",
    "border-bottom-width",
    "border-left-width",
    "border-top-style",
    "border-right-style",
    "border-bottom-style",
    "border-left-style",
    "border-top-color",
    "border-right-color",
    "border-bottom-color",
    "border-left-color",
    "border-top-left-radius",
    "border-top-right-radius",
    "border-bottom-right-radius",
    "border-bottom-left-radius",
    "background-color",
    "background-image",
    "box-shadow",
    "color",
    "opacity",
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "line-height",
    "letter-spacing",
    "text-align",
    "text-decoration-line",
    "text-transform",
    "white-space",
    "vertical-align",
    "flex-direction",
    "flex-wrap",
    "flex-grow",
    "flex-shrink",
    "flex-basis",
    "align-items",
    "justify-content",
    "row-gap",
    "column-gap",
    "overflow-x",
    "overflow-y",
    "outline-style",
    "outline-width",
    "outline-color",
    "outline-offset",
    "cursor",
    "pointer-events",
    "user-select",
    "transform",
    "filter",
    "visibility",
)

_UNSAFE = re.compile(r"[^a-z0-9]+")


def label(value: object) -> str:
    """Name a dimension value in a cell id.

    Args:
        value: The value of a dimension.

    Returns:
        The value in lowercase, anything but letters and digits as a dash.
    """
    return _UNSAFE.sub("-", str(value).lower()).strip("-")


@dataclasses.dataclass(frozen=True)
class Cell:
    """One point of a matrix: a set of props under one environment.

    Attributes:
        props_id: The props that differ from the base cell, or ``base``. Cells
            that share it share one rendered element.
        props: The props the component is created with.
        appearance: The color scheme of the page.
        state: The interactive state the element is put in.
        viewport: The width of the page, in CSS pixels.
    """

    props_id: str
    props: Mapping[str, Any]
    appearance: str
    state: str
    viewport: int

    @property
    def id(self) -> str:
        """Name the cell within its component.

        Returns:
            The props id, then each environment value that is not the default.
        """
        parts = [self.props_id]
        if self.appearance != LIGHT:
            parts.append(self.appearance)
        if self.state != REST:
            parts.append(self.state)
        if self.viewport != DEFAULT_VIEWPORT:
            parts.append(str(self.viewport))
        return "@".join(parts)


Selector = str | tuple[str, str]


@dataclasses.dataclass(frozen=True)
class Matrix:
    """The cells of a component whose look is compared between the two systems.

    A dimension is a prop name, or one of ``appearance``, ``state`` and
    ``viewport``, which the runner provides. Its values are a sequence, or a
    mapping from a label to a value that has no short name of its own, such as
    a responsive value.

    Attributes:
        component: The name both namespaces know the component by: ``rx.box``
            and ``rx.ui.box`` are ``box``.
        render: Create the component from a namespace (``rx`` or ``rx.ui``) and
            the props of a cell. The default calls the component with the
            props.
        base: The value of each dimension in the base cell, and props every
            cell is created with.
        cross: Dimensions whose every combination is a cell.
        sweep: Dimensions varied one at a time, the others at their base.
        groups: Further cross products, each over its own dimensions.
        stage: The width and height, in CSS pixels, of the fixed frame a cell
            is rendered in.
        margin: How far beyond the element a screenshot reaches, for outlines
            and shadows.
        crop: ``element`` compares the element and its margin, ``stage`` the
            whole frame, for what is drawn outside the element, such as a
            popup.
        target: The CSS selector, below the frame, of the element whose
            computed style is read: one string, or one per system. The default
            is the first element of the frame that renders.
        parts: Inner elements whose computed style is compared too, by name.
        properties: The computed properties compared.
        threshold: How far a pixel's color may be off, from 0 to 1, before the
            pixel counts as differing.
        tolerance: The fraction of a cell's pixels that may differ.
        states: Drivers of states the runner does not know, such as ``open``.
    """

    component: str
    render: Callable[[Any, Mapping[str, Any]], Any] | None = None
    base: Mapping[str, Any] = dataclasses.field(default_factory=dict)
    cross: Mapping[str, Sequence[Any] | Mapping[str, Any]] = dataclasses.field(
        default_factory=dict
    )
    sweep: Mapping[str, Sequence[Any] | Mapping[str, Any]] = dataclasses.field(
        default_factory=dict
    )
    groups: Sequence[Mapping[str, Sequence[Any] | Mapping[str, Any]]] = ()
    stage: tuple[int, int] = (240, 120)
    margin: int = 8
    crop: str = "element"
    target: Selector | None = None
    parts: Mapping[str, Selector] = dataclasses.field(default_factory=dict)
    properties: tuple[str, ...] = DEFAULT_PROPERTIES
    threshold: float = 0.01
    tolerance: float = 0.005
    states: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def create(self, namespace: Any, props: Mapping[str, Any]) -> Any:
        """Create the component of one system for a cell.

        Args:
            namespace: ``rx`` or ``rx.ui``.
            props: The props of the cell.

        Returns:
            The component.
        """
        if self.render is not None:
            return self.render(namespace, props)
        return getattr(namespace, self.component)(**props)

    def cells(self) -> list[Cell]:
        """Expand the declaration.

        Returns:
            The base cell, then the cells of ``cross``, ``sweep`` and
            ``groups`` in the order declared, each combination once.
        """
        base_labels = {
            **{name: label(value) for name, value in ENVIRONMENT_BASE.items()},
            **{name: label(value) for name, value in self.base.items()},
        }
        base_values = {**ENVIRONMENT_BASE, **self.base}
        groups = [
            {},
            self.cross,
            *({name: values} for name, values in self.sweep.items()),
            *self.groups,
        ]
        cells: dict[str, Cell] = {}
        for group in groups:
            dimensions = [
                [
                    (name, value_label, value)
                    for value_label, value in (
                        values.items()
                        if isinstance(values, Mapping)
                        else ((label(value), value) for value in values)
                    )
                ]
                for name, values in group.items()
            ]
            for combination in itertools.product(*dimensions):
                values = dict(base_values)
                changed: dict[str, str] = {}
                for name, value_label, value in combination:
                    values[name] = value
                    if base_labels.get(name) != value_label:
                        changed[name] = value_label
                props_id = (
                    "_".join(
                        f"{label(name)}-{changed[name]}"
                        for name in sorted(changed)
                        if name not in ENVIRONMENT
                    )
                    or "base"
                )
                cell = Cell(
                    props_id=props_id,
                    props={
                        name: value
                        for name, value in values.items()
                        if name not in ENVIRONMENT
                    },
                    appearance=values[APPEARANCE],
                    state=values[STATE],
                    viewport=values[VIEWPORT],
                )
                cells.setdefault(cell.id, cell)
        return list(cells.values())

    def rendered(self) -> dict[str, Mapping[str, Any]]:
        """Get the elements a page of the matrix renders.

        Returns:
            The props of each distinct element, by props id.
        """
        rendered: dict[str, Mapping[str, Any]] = {}
        for cell in self.cells():
            rendered.setdefault(cell.props_id, cell.props)
        return rendered
