"""AngleSlider demo page."""

import reflex as rx

import reflex_enterprise as rxe

from .common import demo


@demo(
    route="/angle-slider",
    title="Angle Slider",
    description="An angle slider is a component that allows you to select an angle.",
)
def angle_slider_page():
    """Angle slider demo page."""
    return rx.hstack(
        rxe.angle_slider(
            on_change_end=lambda v: rx.toast(f"Selected angle: {v}"),
            marks=[
                {"value": 0, "label": "0"},
                {"value": 45, "label": "45"},
                {"value": 90, "label": "90"},
                {"value": 135, "label": "135"},
                {"value": 180, "label": "180"},
                {"value": 225, "label": "225"},
                {"value": 270, "label": "270"},
                {"value": 315, "label": "315"},
            ],
        ),
        align="center",
        spacing="4",
        margin_top="25px",
    )
