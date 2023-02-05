"""Container to stack elements with spacing."""

from typing import List, Optional, Union
from pynecone.components.component import Component

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Accordion(ChakraComponent):
    """The wrapper that uses cloneElement to pass props to AccordionItem children."""

    tag = "Accordion"

    # If true, multiple accordion items can be expanded at once.
    allow_multiple: Var[bool]

    # If true, any expanded accordion item can be collapsed again.
    allow_toggle: Var[bool] = True  # type: ignore

    # The initial index(es) of the expanded accordion item(s).
    default_index: Var[Optional[List[int]]]

    # The index(es) of the expanded accordion item
    index: Var[Union[int, List[int]]]

    # If true, height animation and transitions will be disabled.
    reduce_motion: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an accordion component.

        Args:
            children: The children of the component.
            props: The properties of the component.

        Returns:
            The accordion component
        """
        if not children:
            accordions = []
            items = props.pop("items", [])
            icon_position = props.pop("accordion_icon", "right")
            for label, panel in items:
                if icon_position == "right":
                    button = AccordionButton.create(label, AccordionIcon.create())
                elif icon_position == "left":
                    button = AccordionButton.create(AccordionIcon.create(), label)
                else:
                    button = AccordionButton.create(label)

                item = AccordionItem.create(
                    button,
                    AccordionPanel.create(panel),
                )
                accordions.append(item)
                children = accordions
        return super().create(*children, **props)


class AccordionItem(ChakraComponent):
    """A single accordion item."""

    tag = "AccordionItem"

    # A unique id for the accordion item.
    id_: Var[str]

    # If true, the accordion item will be disabled.
    is_disabled: Var[bool]

    # If true, the accordion item will be focusable.
    is_focusable: Var[bool]


class AccordionButton(ChakraComponent):
    """The button that toggles the expand/collapse state of the accordion item. This button must be wrapped in an element with role heading."""

    tag = "AccordionButton"


class AccordionPanel(ChakraComponent):
    """The container for the details to be revealed."""

    tag = "AccordionPanel"


class AccordionIcon(ChakraComponent):
    """A chevron-down icon that rotates based on the expanded/collapsed state."""

    tag = "AccordionIcon"
