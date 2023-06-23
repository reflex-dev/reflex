"""A code component."""

from typing import Dict

from reflex.components.component import Component
from reflex.components.forms import Button
from reflex.components.layout import Box
from reflex.components.libs.chakra import ChakraComponent
from reflex.components.media import Icon
from reflex.event import set_clipboard
from reflex.style import Style
from reflex.utils import imports
from reflex.vars import ImportVar, Var

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

    def _get_imports(self) -> imports.ImportDict:
        merged_imports = super()._get_imports()
        if self.theme is not None:
            merged_imports = imports.merge_imports(
                merged_imports, {PRISM_STYLES_PATH: {ImportVar(tag=self.theme.name)}}
            )
        return merged_imports

    @classmethod
    def create(cls, *children, can_copy=False, copy_button=None, **props):
        """Create a text component.

        Args:
            *children: The children of the component.
            can_copy: Whether a copy button should appears.
            copy_button: A custom copy button to override the default one.
            **props: The props to pass to the component.

        Returns:
            The text component.
        """
        # This component handles style in a special prop.
        custom_style = props.pop("custom_style", {})

        if can_copy:
            code = children[0]
            copy_button = (
                copy_button
                if copy_button is not None
                else Button.create(
                    Icon.create(tag="copy"),
                    on_click=set_clipboard(code),
                    style={"position": "absolute", "top": "0.5em", "right": "0"},
                )
            )
            custom_style.update({"padding": "1em 3.2em 1em 1em"})
        else:
            copy_button = None

        # Transfer style props to the custom style prop.
        for key, value in props.items():
            if key not in cls.get_fields():
                custom_style[key] = value

        # Create the component.
        code_block = super().create(
            *children,
            **props,
            custom_style=Style(custom_style),
        )

        if copy_button:
            return Box.create(code_block, copy_button, position="relative")
        else:
            return code_block

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
