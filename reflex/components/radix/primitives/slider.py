"""Radix slider components."""

from typing import Any, Dict, Literal, Optional

from reflex.components.component import Component
from reflex.components.tags.tag import Tag
from reflex.vars import Var
from reflex.utils import format, imports

LiteralSliderOrientation = Literal["horizontal", "vertical"]
LiteralSliderDir = Literal["ltr", "rtl"]


class SliderComponent(Component):
    """Base class for all @radix-ui/react-slider components."""

    library = "@radix-ui/react-slider@^1.1.2"

    as_child: Var[bool]

    def _render(self) -> Tag:
        return (
            super()
            ._render()
            .add_props(
                **{
                    "class_name": format.to_title_case(self.tag or ""),
                }
            )
        )


class SliderRoot(SliderComponent):
    """The Slider component comtaining all slider parts."""

    tag = "Root"
    alias = "RadixSliderRoot"

    default_value: Var[list[int]] = [50]

    value: Var[int]

    name: Var[str]

    disabled: Var[bool]

    orientation: Var[LiteralSliderOrientation]

    inverted: Var[bool]

    min: Var[int] = 0

    max: Var[int] = 100

    step: Var[int] = 1

    min_steps_between_thumbs: Var[int] = 0

    def get_event_triggers(self) -> Dict[str, Any]:
        return {
            **super().get_event_triggers(),
            "on_value_change": lambda e0: [e0.target.value],
            "on_value_commit": lambda e0: [e0.target.value],
        }

    @classmethod
    def create(cls, *children, **props) -> Component:
        if not children:
            children = [
                "Label",
                SliderTrack.create(SliderRange.create()),
                SliderThumb.create(),
            ]
        return super().create(*children, **props)


class SliderTrack(SliderComponent):
    tag = "Track"
    alias = "RadixSliderTrack"


class SliderRange(SliderComponent):
    tag = "Range"
    alias = "RadixSliderRange"


class SliderThumb(SliderComponent):
    tag = "Thumb"
    alias = "RadixSliderThumb"


slider = SliderRoot.create
slider_track = SliderTrack.create
slider_range = SliderRange.create
slider_thumb = SliderThumb.create


# def slider(min: Optional[int] = 0, max: Optional[int] = 100, **props) -> Component:
#     return slider(
#         slider_track(slider_range()),
#         slider_thumb(),
#         min=min,
#         max=max,
#         **props,
#     )
