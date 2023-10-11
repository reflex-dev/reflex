"""Components that are based on Chakra-UI."""
from __future__ import annotations

from typing import List

from reflex.components.component import Component
from reflex.utils import imports
from reflex.vars import ImportVar, Var


class ChakraComponent(Component):
    """A component that wraps a Chakra component."""

    library = "@chakra-ui/react@2.6.1"
    lib_dependencies: List[str] = [
        "@chakra-ui/system@2.5.7",
        "framer-motion@10.16.4",
    ]

    def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
        return {
            **super()._get_app_wrap_components(),
            (60, "ChakraProvider"): ChakraProvider.create(),
        }


class Global(Component):
    """The emotion/react Global styling component."""

    library = "@emotion/react@11.11.0"
    lib_dependencies: List[str] = [
        "@emotion/styled@11.11.0",
    ]

    tag = "Global"

    styles: Var[str]


class ChakraProvider(ChakraComponent):
    """Top level Chakra provider must be included in any app using chakra components."""

    tag = "ChakraProvider"

    theme: Var[str]

    @classmethod
    def create(cls) -> Component:
        """Create a new ChakraProvider component.

        Returns:
            A new ChakraProvider component.
        """
        return super().create(
            Global.create(styles=Var.create("GlobalStyles", is_local=False)),
            theme=Var.create("extendTheme(theme)", is_local=False),
        )

    def _get_imports(self) -> imports.ImportDict:
        imports = super()._get_imports()
        imports.setdefault(self.__fields__["library"].default, set()).add(
            ImportVar(tag="extendTheme", is_default=False),
        )
        imports.setdefault("/utils/theme.js", set()).add(
            ImportVar(tag="theme", is_default=False),
        )
        imports.setdefault(Global.__fields__["library"].default, set()).add(
            ImportVar(tag="css", is_default=False),
        )
        return imports

    def _get_custom_code(self) -> str | None:
        return """
import '/styles/styles.css'

const GlobalStyles = css`
  /* Hide the blue border around Chakra components. */
  .js-focus-visible :focus:not([data-focus-visible-added]) {
    outline: none;
    box-shadow: none;
  }
`;
"""

    def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
        return {
            (50, "ChakraColorModeProvider"): ChakraColorModeProvider.create(),
        }


class ChakraColorModeProvider(Component):
    """Next-themes integration for chakra colorModeProvider."""

    library = "/components/reflex/chakra_color_mode_provider.js"
    tag = "ChakraColorModeProvider"
    is_default = True
