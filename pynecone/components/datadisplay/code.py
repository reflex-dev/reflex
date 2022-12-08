"""A code component."""

from typing import Dict

from pynecone import utils
from pynecone.components.component import Component, ImportDict
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.style import Style
from pynecone.var import Var

# Path to the prism styles.
PRISM_STYLES_PATH = "/styles/code/prism"


class CodeBlock(Component):
    """A code block."""

    library = "react-syntax-highlighter"

    tag = "Prism"

    # The theme to use ("light" or "dark").
    theme: Var[str]

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

    def _get_imports(self) -> ImportDict:
        imports = super()._get_imports()
        if self.theme is not None:
            imports = utils.merge_imports(
                imports, {PRISM_STYLES_PATH: {self.theme.name}}
            )
        return imports

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
        custom_style = props.pop("custom_style", {})

        # Transfer style props to the custom style prop.
        for key, value in props.items():
            if key not in cls.get_fields():
                custom_style[key] = value

        # Create the component.
        return super().create(
            *children,
            **props,
            custom_style=Style(custom_style),
        )

    def _add_style(self, style):
        self.custom_style = self.custom_style or {}
        self.custom_style.update(style)  # type: ignore

    def _render(self):
        out = super()._render()
        if self.theme is not None:
            out.add_props(
                style=Var.create(self.theme.name, is_local=False)
            ).remove_props("theme")
        return out


class Code(ChakraComponent):
    """Used to display inline code."""

    tag = "Code"
