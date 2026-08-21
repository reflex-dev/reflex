"""A progress bar built from divs and Tailwind classes."""

from __future__ import annotations

from typing import ClassVar

from reflex_base.components.component import field
from reflex_base.vars.base import Var

from reflex_components_core.el.elements.typography import Div
from reflex_components_core.ui.base import UIComponent

PROGRESS_CLASS_NAME = "relative h-2 w-full overflow-hidden rounded-full bg-primary/20"

PROGRESS_INDICATOR_CLASS_NAME = "size-full flex-1 bg-primary transition-transform"


class Progress(Div, UIComponent):
    """A themable progress bar."""

    _slot: ClassVar[str | None] = "progress"

    value: Var[int | float] = field(doc="Current progress value.")

    max: Var[int | float] = field(doc="Maximum progress value. Defaults to 100.")

    @classmethod
    def create(cls, *children, **props):
        """Create a progress bar.

        Args:
            *children: Unused; progress bars render their own indicator.
            **props: The props of the component.

        Returns:
            The progress component.
        """
        value = props.pop("value", 0)
        max_value = props.pop("max", 100)
        percent = (Var.create(value) / max_value) * 100
        props.setdefault("role", "progressbar")
        props.setdefault("aria_valuemin", 0)
        props.setdefault("aria_valuemax", max_value)
        props.setdefault("aria_valuenow", value)
        cls._apply_class_name(PROGRESS_CLASS_NAME, props)
        indicator = Div.create(
            data_slot="progress-indicator",
            class_name=PROGRESS_INDICATOR_CLASS_NAME,
            style={"transform": f"translateX(-{100 - percent}%)"},
        )
        return super().create(indicator, **props)

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "value",
            "max",
        ]


progress = Progress.create
