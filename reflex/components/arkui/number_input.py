"""NumberInput component for ArkUI."""
from types import SimpleNamespace
from typing import Any, Dict, Literal, Optional

from reflex.components.component import Component
from reflex.components.radix.themes.components.icons import Icon
from reflex.style import Style
from reflex.vars import Var

from .base import BaseArkUIComponent

LiteralDirection = Literal["ltr", "rtl"]


class BaseNumberInput(BaseArkUIComponent):
    """Base component for NumberInput."""

    tag = "NumberInput"


class NumberInputRoot(BaseNumberInput):
    """Root element of NumberInput."""

    alias = "NumberInput.Root"

    allow_mouse_wheel: Var[bool]

    allow_overflow: Var[bool]

    clamp_value_on_blur: Var[bool]

    defaultValue: Var[str]

    dir: Var[LiteralDirection]

    disabled: Var[bool]

    focus_input_on_change: Var[bool]

    form: Var[str]

    format_options: Var[dict[str, str]]

    input_mode: Var[str]

    invalid: Var[bool]

    locale: Var[str]

    max: Var[int]

    min: Var[int]

    name: Var[str]

    pattern: Var[str]

    read_only: Var[bool]

    spin_on_press: Var[bool]

    step: Var[int]

    translations: Var[dict[str, str]]

    value: Var[int]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get event triggers.

        Returns:
            A dictionary of event triggers.
        """
        return super().get_event_triggers() | {
            "on_focus_change": lambda e0: [e0],
            "on_value_change": lambda e0: [e0],
            "on_value_invalid": lambda e0: [e0],
        }

    def _apply_theme(self, theme: Component | None):
        self.style.update(
            {
                "display": "flex",
                "flex_direction": "column",
                "gap": "1.5",
            }
        )


class NumberInputScrubber(BaseNumberInput):
    """Scrubber element of NumberInput."""

    alias = "NumberInput.Scrubber"


class NumberInputLabel(BaseNumberInput):
    """Label element of NumberInput."""

    alias = "NumberInput.Label"


class NumberInputInput(BaseNumberInput):
    """Input element of NumberInput."""

    alias = "NumberInput.Input"

    def _apply_theme(self, theme: Component | None):
        self.style = Style(
            {
                "outline": "none",
                "background": "transparent",
                "width": "full",
                "gridRow": "1",
                **self.style,
            }
        )


class NumberInputControl(BaseNumberInput):
    """Control element of NumberInput."""

    alias = "NumberInput.Control"

    def _apply_theme(self, theme: Component | None):
        self.style = Style(
            {
                # "border_color": "border.default",
                "border_radius": "5",
                "border_width": "1px",
                "display": "grid",
                "divide_x": "1px",
                "grid_template_columns": "1fr 32px",
                "grid_template_rows": "1fr 1fr",
                "overflow": "hidden",
                "transition_duration": "normal",
                "transition_property": "border-color, box-shadow",
                "transition_timing_function": "default",
                "_focus_within": {
                    # "border_color": "colorPalette.default",
                    "box_shadow": "0 0 0 1px var(--colors-color-palette-default)",
                },
                **self.style,
            }
        )


trigger_styles = {
    "align_items": "center",
    "border_color": "black",
    "color": "white",
    "cursor": "pointer",
    "display": "inline-flex",
    "justify_content": "center",
    "transition_duration": "normal",
    "transition_property": "background, border-color, color, box-shadow",
    "transition_timing_function": "default",
    "_hover": {
        "background": "gray.a2",
        "color": "fg.default",
    },
    "_disabled": {
        "color": "fg.disabled",
        "cursor": "not-allowed",
        "_hover": {
            "background": "transparent",
            "color": "fg.disabled",
        },
    },
}


class NumberInputDecrementTrigger(BaseNumberInput):
    """DecrementTrigger element of NumberInput."""

    alias = "NumberInput.DecrementTrigger"

    def _apply_theme(self, theme: Component | None):
        self.style = Style(
            {
                **trigger_styles,
                "border_top_width": "1px",
            }
        )


class NumberInputIncrementTrigger(BaseNumberInput):
    """IncrementTrigger element of NumberInput."""

    alias = "NumberInput.IncrementTrigger"

    def _apply_theme(self, theme: Component | None):
        self.style = Style(
            {
                **trigger_styles,
            }
        )


number_input_root = NumberInputRoot.create
number_input_scrubber = NumberInputScrubber.create
number_input_label = NumberInputLabel.create
number_input_input = NumberInputInput.create
number_input_control = NumberInputControl.create
number_input_decrement_trigger = NumberInputDecrementTrigger.create
number_input_increment_trigger = NumberInputIncrementTrigger.create


class NumberInputNamespace(SimpleNamespace):
    root = number_input_root
    scrubber = number_input_scrubber
    label = number_input_label
    input = number_input_input
    control = number_input_control
    decrement_trigger = number_input_decrement_trigger
    increment_trigger = number_input_increment_trigger


number_input_ns = NumberInputNamespace


def number_input_():
    return number_input_ns.root(
        # number_input_ns.scrubber(),
        # number_input_ns.label("Label"),
        number_input_ns.control(
            number_input_ns.input(),
            number_input_ns.decrement_trigger(
                Icon.create(tag="chevron_down"), as_child=True
            ),
            number_input_ns.increment_trigger(
                Icon.create(tag="chevron_up"), as_child=True
            ),
        ),
    )
