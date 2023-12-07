"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

from reflex.components import el
from reflex.components.component import Component
from reflex.components.forms.debounce import DebounceInput
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralAccentColor,
    LiteralRadius,
    LiteralSize,
    RadixThemesComponent,
)

LiteralTextFieldSize = Literal["1", "2", "3"]
LiteralTextFieldVariant = Literal["classic", "surface", "soft"]


class TextFieldRoot(el.Div, CommonMarginProps, RadixThemesComponent):
    """Captures user input with an optional slot for buttons and icons."""

    tag = "TextField.Root"

    # Text field size "1" - "3"
    size: Var[LiteralTextFieldSize]

    # Variant of text field: "classic" | "surface" | "soft"
    variant: Var[LiteralTextFieldVariant]

    # Override theme color for text field
    color: Var[LiteralAccentColor]

    # Override theme radius for text field: "none" | "small" | "medium" | "large" | "full"
    radius: Var[LiteralRadius]


class TextFieldInput(el.Input, TextFieldRoot):
    """The input part of a TextField, may be used by itself."""

    tag = "TextField.Input"

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an Input component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The component.
        """
        if (
            isinstance(props.get("value"), Var) and props.get("on_change")
        ) or "debounce_timeout" in props:
            # Currently default to 50ms, which appears to be a good balance
            debounce_timeout = props.pop("debounce_timeout", 50)
            # create a debounced input if the user requests full control to avoid typing jank
            return DebounceInput.create(
                super().create(*children, **props), debounce_timeout=debounce_timeout
            )
        return super().create(*children, **props)

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CHANGE: lambda e0: [e0.target.value],
            EventTriggers.ON_FOCUS: lambda e0: [e0.target.value],
            EventTriggers.ON_BLUR: lambda e0: [e0.target.value],
            EventTriggers.ON_KEY_DOWN: lambda e0: [e0.key],
            EventTriggers.ON_KEY_UP: lambda e0: [e0.key],
        }


class TextFieldSlot(RadixThemesComponent):
    """Contains icons or buttons associated with an Input."""

    tag = "TextField.Slot"

    # Override theme color for text field slot
    color: Var[LiteralAccentColor]

    # Override the gap spacing between slot and input: "1" - "9"
    gap: Var[LiteralSize]


from reflex.style import Style
from reflex.utils import imports


class AccordionComponent(Component):
    """Base class for all @radix-ui/accordion components."""

    library = "@radix-ui/react-accordion"

    as_child: Var[bool]


class AccordionRoot(AccordionComponent):
    """An accordion component."""

    tag = "Root"

    alias = "RadixAccordionRoot"

    style: Style = Style(
        {
            "borderRadius": "6px",
            "width": "300px",
            "backgroundColor": "var(--accent-6)",
            "boxShadow": "0 2px 10px var(--black-a4)",
        }
    )

    value: Var[str]

    default_value: Var[str]

    collapsible: Var[bool]

    disabled: Var[bool]

    dir: Var[str]

    orientation: Var[str]


class AccordionItem(AccordionComponent):
    """An accordion component."""

    tag = "Item"

    alias = "RadixAccordionItem"

    style: Style = Style(
        {
            "overflow": "hidden",
            "marginTop": "1px",
            "&:first-child": {
                "marginTop": 0,
                "borderTopLeftRadius": "4px",
                "borderTopRightRadius": "4px",
            },
            "&:last-child": {
                "borderBottomLeftRadius": "4px",
                "borderBottomRightRadius": "4px",
            },
            "&:focus-within": {
                "position": "relative",
                "zIndex": 1,
                "boxShadow": "0 0 0 2px var(--accent-7)",
            },
        }
    )

    value: Var[str]

    disabled: Var[bool]


class AccordionHeader(AccordionComponent):
    """An accordion component."""

    tag = "Header"

    alias = "RadixAccordionHeader"

    style: Style = Style(
        {
            "display": "flex",
        }
    )


class AccordionTrigger(AccordionComponent):
    """An accordion component."""

    tag = "Trigger"

    alias = "RadixAccordionTrigger"

    style: Style = Style(
        {
            "fontFamily": "inherit",
            "backgroundColor": "transparent",
            "padding": "0 20px",
            "height": "45px",
            "flex": 1,
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "space-between",
            "fontSize": "15px",
            "lineHeight": 1,
            "color": "var(--accent-11)",
            "boxShadow": "0 1px 0 var(--accent-6)",
            "backgroundColor": "white",
            "&:hover": {
                "backgroundColor": "var(--gray-2)",
            },
            "&[data-state='open'] > .AccordionChevron": {
                "transform": "rotate(180deg)",
            },
        }
    )


class AccordionContent(AccordionComponent):
    """An accordion component."""

    tag = "Content"

    alias = "RadixAccordionContent"

    style: Style = Style(
        {
            "overflow": "hidden",
            "fontSize": "15px",
            "color": "var(--accent-11)",
            "backgroundColor": "var(--accent-2)",
            "padding": "15px, 20px",
            "&[data-state='open']": {
                "animation": Var.create(
                    "${slideDown} 500ms cubic-bezier(0.87, 0, 0.13, 1)",
                    _var_is_string=True,
                ),
            },
            "&[data-state='closed']": {
                "animation": Var.create(
                    "${slideUp} 500ms cubic-bezier(0.87, 0, 0.13, 1)",
                    _var_is_string=True,
                ),
            },
        }
    )

    def _get_imports(self):
        return {
            **super()._get_imports(),
            "@emotion/react": [imports.ImportVar(tag="keyframes")],
        }

    def _get_custom_code(self) -> str:
        return """
const slideDown = keyframes`
from {
  height: 0;
}
to {
  height: var(--radix-accordion-content-height);
}
`
const slideUp = keyframes`
from {
  height: var(--radix-accordion-content-height);
}
to {
  height: 0;
}
`
"""


class ChevronDownIcon(Component):
    library = "@radix-ui/react-icons"

    tag = "ChevronDownIcon"

    style: Style = Style(
        {
            "color": "var(--accent-10)",
            "transition": "transform 300ms cubic-bezier(0.87, 0, 0.13, 1)",
        }
    )
