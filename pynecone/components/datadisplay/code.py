"""A code component."""

from typing import Dict

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class CodeBlock(Component):
    """A code block."""

    library = "react-syntax-highlighter"

    tag = "Prism"

    # The language to use.
    language: Var[str]

    # If this is enabled line numbers will be shown next to the code block.
    show_line_numbers: Var[bool]

    # The starting line number to use.
    starting_line_number: Var[int]

    # Whether to wrap long lines.
    wrap_long_lines: Var[bool]

    # A custom style for the code block.
    custom_style: Var[Dict[str, str]]

    # Props passed down to the code tag.
    code_tag_props: Var[Dict[str, str]]

    @classmethod
    def create(cls, *children, **props):
        """Create a text component.

        Args:
            *children: The children of the component.
            **props: The props to pass to the component.

        Returns:
            The text component.
        """
        # This component handles style in a special prop.
        custom_style = props.get("custom_style", {})

        # Transfer style props to the custom style prop.
        for key, value in props.items():
            if key not in cls.get_fields():
                custom_style[key] = value

        # Create the component.
        return super().create(
            *children,
            **props,
        )

    def _add_style(self, style):
        self.custom_style = self.custom_style or {}
        self.custom_style.update(style)  # type: ignore


class Code(ChakraComponent):
    """Used to display inline code."""

    tag = "Code"
