"""A range slider component."""
from __future__ import annotations

from typing import Any, List, Optional, Union

from reflex.components.chakra import ChakraComponent, LiteralChakraDirection
from reflex.components.component import Component
from reflex.constants import EventTriggers
from reflex.utils import format
from reflex.vars import Var


class RangeSlider(ChakraComponent):
    """The RangeSlider is a multi thumb slider used to select a range of related values. A common use-case of this component is a price range picker that allows a user to set the minimum and maximum price."""

    tag = "RangeSlider"

    # State var to bind the the input.
    value: Var[List[int]]

    # The default values.
    default_value: Var[List[int]]

    # The writing mode ("ltr" | "rtl")
    direction: Var[LiteralChakraDirection]

    # If false, the slider handle will not capture focus when value changes.
    focus_thumb_on_change: Var[bool]

    # If true, the slider will be disabled
    is_disabled: Var[bool]

    # If true, the slider will be in `read-only` state.
    is_read_only: Var[bool]

    # If true, the value will be incremented or decremented in reverse.
    is_reversed: Var[bool]

    # The minimum value of the slider.
    min_: Var[int]

    # The maximum value of the slider.
    max_: Var[int]

    # The minimum distance between slider thumbs. Useful for preventing the thumbs from being too close together.
    min_steps_between_thumbs: Var[int]

    # The name of the form field
    name: Var[str]

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CHANGE: lambda e0: [e0],
            EventTriggers.ON_CHANGE_END: lambda e0: [e0],
            EventTriggers.ON_CHANGE_START: lambda e0: [e0],
        }

    def get_ref(self):
        """Get the ref of the component.

        Returns:
            The ref of the component.
        """
        return None

    def _get_ref_hook(self) -> Optional[str]:
        """Override the base _get_ref_hook to handle array refs.

        Returns:
            The overrided hooks.
        """
        if self.id:
            ref = format.format_array_ref(self.id, None)
            if ref:
                return (
                    f"const {ref} = Array.from({{length:2}}, () => useRef(null)); "
                    f"{str(Var.create_safe(ref).as_ref())} = {ref}"
                )
            return super()._get_ref_hook()

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a RangeSlider component.

        If no children are provided, a default RangeSlider will be created.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The RangeSlider component.
        """
        if len(children) == 0:
            _id = props.get("id", None)
            if _id:
                children = [
                    RangeSliderTrack.create(
                        RangeSliderFilledTrack.create(),
                    ),
                    RangeSliderThumb.create(index=0, id=_id),
                    RangeSliderThumb.create(index=1, id=_id),
                ]
            else:
                children = [
                    RangeSliderTrack.create(
                        RangeSliderFilledTrack.create(),
                    ),
                    RangeSliderThumb.create(index=0),
                    RangeSliderThumb.create(index=1),
                ]
        return super().create(*children, **props)


class RangeSliderTrack(ChakraComponent):
    """A range slider track."""

    tag = "RangeSliderTrack"


class RangeSliderFilledTrack(ChakraComponent):
    """A filled range slider track."""

    tag = "RangeSliderFilledTrack"


class RangeSliderThumb(ChakraComponent):
    """A range slider thumb."""

    tag = "RangeSliderThumb"

    # The position of the thumb.
    index: Var[int]

    def _get_ref_hook(self) -> Optional[str]:
        # hook is None because RangeSlider is handling it.
        return None

    def get_ref(self):
        """Get an array ref for the range slider thumb.

        Returns:
            The array ref.
        """
        if self.id:
            return format.format_array_ref(self.id, self.index)
