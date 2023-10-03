from reflex.utils import imports
from reflex.vars import ImportVar, Var

from ...component import Component


class RadixThemesComponent(Component):
    library = "@radix-ui/themes"

    color: Var[str]

    variant: Var[str]

    @classmethod
    def create(cls, *children, **props) -> Component:
        component = super().create(*children, **props)
        component.alias = "RadixThemes" + component.tag
        return component

    def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
        return {
            **super()._get_app_wrap_components(),
            (20, "Theme"): Theme.create(),
        }


class Theme(RadixThemesComponent):
    tag = "Theme"

    def _get_imports(self) -> imports.ImportDict:
        imports = {
            **super()._get_imports(),
            "/utils/theme.js": {ImportVar(tag="radix_theme", is_default=False)},
            "/utils/context.js": {
                ImportVar(tag="isDevMode", is_default=False),
                ImportVar(tag="ColorModeContext", is_default=False),
            },
            self.library: {
                ImportVar(tag="Theme", is_default=False),
                ImportVar(tag="ThemePanel", is_default=False),
            },
            "react": {ImportVar(tag="useContext", is_default=False)},
        }
        imports.setdefault(self.library, set()).add(
            ImportVar(tag="ThemePanel", is_default=False)
        )
        return imports

    def _get_custom_code(self) -> str | None:
        return """
import '@radix-ui/themes/styles.css';

function RadixThemesTheme({children}) {
    const [colorMode, toggleColorMode] = useContext(ColorModeContext);

    return (
        <Theme appearance={colorMode} {...radix_theme}>
          {children}
          {isDevMode ? <ThemePanel defaultOpen={false} /> : null}
        </Theme>
    )
}"""

    def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
        return {
            (45, "RadixThemesColorModeProvider"): RadixThemesColorModeProvider.create(),
        }


class RadixThemesColorModeProvider(Component):
    tag = "RadixThemesColorModeProvider"

    def _get_imports(self) -> imports.ImportDict:
        return {
            "react": {ImportVar(tag="useState", is_default=False)},
            "/utils/context.js": {
                ImportVar(tag="ColorModeContext", is_default=False),
            },
        }

    def _get_custom_code(self) -> str | None:
        return """
function RadixThemesColorModeProvider({ children }) {
  let defaultMode = "light"
  if (typeof window !== "undefined") {
    defaultMode = window.localStorage.getItem("chakra-ui-color-mode")
  }
  const [colorMode, setColorMode] = useState(defaultMode)

  const toggleColorMode = () => {
    setColorMode((prevMode) => {
        const newMode = (prevMode === "light" ? "dark" : "light")
        if (typeof window !== "undefined") {
            window.localStorage.setItem("chakra-ui-color-mode", newMode)
        }
        return newMode
    })
  }
  return (
    <ColorModeContext.Provider value={[ colorMode, toggleColorMode ]}>
      {children}
    </ColorModeContext.Provider>
  )
}"""
