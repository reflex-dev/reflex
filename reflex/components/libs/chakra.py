"""Components that are based on Chakra-UI."""
from __future__ import annotations

from functools import lru_cache
from typing import List, Literal

from reflex.components.component import Component
from reflex.utils import imports
from reflex.vars import Var


class ChakraComponent(Component):
    """A component that wraps a Chakra component."""

    library = "@chakra-ui/react@2.6.1"
    lib_dependencies: List[str] = [
        "@chakra-ui/system@2.5.7",
        "focus-visible@5.2.0",
        "framer-motion@10.16.4",
    ]

    @staticmethod
    @lru_cache(maxsize=None)
    def _get_app_wrap_components() -> dict[tuple[int, str], Component]:
        return {
            (60, "ChakraProvider"): chakra_provider,
        }

    def get_imports(self) -> imports.ImportDict:
        """Chakra requires focus-visible and imported into each page.

        This allows the GlobalStyle defined by the ChakraProvider to hide the blue border.

        Returns:
            The imports for the component.
        """
        return imports.merge_imports(
            super().get_imports(),
            {
                "": {
                    imports.ImportVar(
                        tag="focus-visible/dist/focus-visible", install=False
                    )
                }
            },
        )

    def _get_style(self) -> dict:
        """Get the style for the component.

        Returns:
            The dictionary of the component style as value and the style notation as key.
        """
        return {"sx": self.style}

    @classmethod
    @lru_cache(maxsize=None)
    def _get_dependencies_imports(cls) -> imports.ImportDict:
        """Get the imports from lib_dependencies for installing.

        Returns:
            The dependencies imports of the component.
        """
        return {
            dep: [imports.ImportVar(tag=None, render=False)]
            for dep in [
                "@chakra-ui/system@2.5.7",
                "focus-visible@5.2.0",
                "framer-motion@10.16.4",
            ]
        }


class Global(Component):
    """The emotion/react Global styling component."""

    library = "@emotion/react@^11.11.0"
    lib_dependencies: List[str] = [
        "@emotion/styled@^11.11.0",
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
            Global.create(styles=Var.create("GlobalStyles", _var_is_local=False)),
            theme=Var.create("extendTheme(theme)", _var_is_local=False),
        )

    def _get_imports(self) -> imports.ImportDict:
        _imports = super()._get_imports()
        _imports.setdefault(self.__fields__["library"].default, []).append(
            imports.ImportVar(tag="extendTheme", is_default=False),
        )
        _imports.setdefault("/utils/theme.js", []).append(
            imports.ImportVar(tag="theme", is_default=True),
        )
        _imports.setdefault(Global.__fields__["library"].default, []).append(
            imports.ImportVar(tag="css", is_default=False),
        )
        return _imports

    def _get_custom_code(self) -> str | None:
        return """
const GlobalStyles = css`
  /* Hide the blue border around Chakra components. */
  .js-focus-visible :focus:not([data-focus-visible-added]) {
    outline: none;
    box-shadow: none;
  }
`;
"""

    @staticmethod
    @lru_cache(maxsize=None)
    def _get_app_wrap_components() -> dict[tuple[int, str], Component]:
        return {
            (50, "ChakraColorModeProvider"): chakra_color_mode_provider,
        }


chakra_provider = ChakraProvider.create()


class ChakraColorModeProvider(Component):
    """Next-themes integration for chakra colorModeProvider."""

    library = "/components/reflex/chakra_color_mode_provider.js"
    tag = "ChakraColorModeProvider"
    is_default = True


chakra_color_mode_provider = ChakraColorModeProvider.create()


LiteralColorScheme = Literal[
    "none",
    "gray",
    "red",
    "orange",
    "yellow",
    "green",
    "teal",
    "blue",
    "cyan",
    "purple",
    "pink",
    "whiteAlpha",
    "blackAlpha",
    "linkedin",
    "facebook",
    "messenger",
    "whatsapp",
    "twitter",
    "telegram",
]


LiteralVariant = Literal["solid", "subtle", "outline"]
LiteralDividerVariant = Literal["solid", "dashed"]
LiteralTheme = Literal["light", "dark"]


LiteralTagColorScheme = Literal[
    "gray",
    "red",
    "orange",
    "yellow",
    "green",
    "teal",
    "blue",
    "cyan",
    "purple",
    "pink",
]
LiteralTagAlign = Literal["center", "end", "start"]
LiteralTabsVariant = Literal[
    "line",
    "enclosed",
    "enclosed-colored",
    "soft-rounded",
    "solid-rounded",
    "unstyled",
]

LiteralStatus = Literal["success", "info", "warning", "error"]
LiteralAlertVariant = Literal["subtle", "left-accent", "top-accent", "solid"]
LiteralButtonVariant = Literal["ghost", "outline", "solid", "link", "unstyled"]
LiteralSpinnerPlacement = Literal["start", "end"]
LiteralLanguage = Literal[
    "en",
    "da",
    "de",
    "es",
    "fr",
    "ja",
    "ko",
    "pt_br",
    "ru",
    "zh_cn",
    "ro",
    "pl",
    "ckb",
    "lv",
    "se",
    "ua",
    "he",
    "it",
]
LiteralInputVariant = Literal["outline", "filled", "flushed", "unstyled"]
LiteralInputNumberMode = [
    "text",
    "search",
    "none",
    "tel",
    "url",
    "email",
    "numeric",
    "decimal",
]
LiteralChakraDirection = Literal["ltr", "rtl"]
LiteralCardVariant = Literal["outline", "filled", "elevated", "unstyled"]
LiteralStackDirection = Literal["row", "column"]
LiteralImageLoading = Literal["eager", "lazy"]
LiteralTagSize = Literal["sm", "md", "lg"]
LiteralSpinnerSize = Literal[Literal[LiteralTagSize], "xs", "xl"]
LiteralAvatarSize = Literal[Literal[LiteralTagSize], "xl", "xs", "2xl", "full", "2xs"]
LiteralButtonSize = Literal["sm", "md", "lg", "xs"]
# Applies to AlertDialog and Modal
LiteralAlertDialogSize = Literal[
    "sm", "md", "lg", "xs", "2xl", "full", "3xl", "4xl", "5xl", "6xl"
]
LiteralDrawerSize = Literal[Literal[LiteralSpinnerSize], "xl", "full"]

LiteralMenuStrategy = Literal["fixed", "absolute"]
LiteralMenuOption = Literal["checkbox", "radio"]
LiteralPopOverTrigger = Literal["click", "hover"]

LiteralHeadingSize = Literal["lg", "md", "sm", "xs", "xl", "2xl", "3xl", "4xl"]
