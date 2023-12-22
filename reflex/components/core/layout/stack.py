"""Stack components."""


from typing import Literal

from reflex.components.component import Component
from reflex.components.el.elements.typography import Div
from reflex.vars import Var


class Stack(Div):
    """A stack component."""

    # The direction of the stack.
    justify: Var[Literal["start", "center", "end"]]

    # The alignment of the stack.
    align: Var[Literal["start", "center", "end", "stretch"]]

    # The spacing between each stack item.
    spacing: Var[str]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a new instance of the component.

        Args:
            *children: The children of the stack.
            **props: The properties of the stack.

        Returns:
            The stack component.
        """
        style = props.setdefault("style", {})
        align = props.pop("align", "center")
        spacing = props.pop("spacing", "0.5rem")
        justify = props.pop("justify", "flex-start")
        style.update(
            {
                "display": "flex",
                "alignItems": align,
                "justifyContent": justify,
                "gap": spacing,
            }
        )
        return super().create(*children, **props)


class VStack(Stack):
    """A vertical stack component."""

    def _apply_theme(self, theme: Component | None):
        self.style.update({"flex_direction": "column"})


class HStack(Stack):
    """A horizontal stack component."""

    def _apply_theme(self, theme: Component | None):
        self.style.update({"flex_direction": "row"})


# class Stack(rdxt.Flex):
#     """A stack component."""

# direction: Var[Literal["horizontal", "vertical"]]

# align: Var[str] = "center"

# justify: Var[str] = "center"

# The spacing between the children.
# spacing: Var[str] = "2px"

# def _apply_theme(self, theme: Component | None):
#     self.style = Style(
#         {
#             "display": "flex",
#             "flex_direction": rx.cond(
#                 f"{self.direction}" == "vertical", "column", "row"
#             ),
#             "justify": f"{self.justify}",
#             "gap": self.spacing,
#             "align": f"{self.align}",
#             **self.style,
#         }
#     )


# class HStack(Stack):
#     """An horizontal stack component."""

#     @classmethod
#     def create(cls, *children, **props):
#         """Create a new instance of the component."""
#         return super().create(*children, direction="horizontal", **props)


# class VStack(Stack):
#     """A vertical stack component."""

#     @classmethod
#     def create(cls, *children, **props):
#         """Create a new instance of the component."""
#         return super().create(*children, direction="vertical", **props)

hstack = HStack.create
vstack = VStack.create
