from reflex.utils import imports
from reflex.vars import ImportVar, Var

from ...component import Component


class RadixThemesComponent(Component):
    library = "@radix-ui/themes@^2.0.0"

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
        return {
            "/utils/theme.js": {ImportVar(tag="radix_theme", is_default=False)},
            "/utils/context.js": {
                ImportVar(tag="isDevMode", is_default=False),
            },
            self.library: {
                ImportVar(tag="Theme", is_default=False),
                ImportVar(tag="ThemePanel", is_default=False),
            },
        }

    def _get_custom_code(self) -> str | None:
        return (
            """
import '@radix-ui/themes/styles.css';

function %s({children}) {
    return (
        <Theme {...radix_theme}>
          {children}
          {isDevMode ? <ThemePanel defaultOpen={false} /> : null}
        </Theme>
    )
}"""
            % self.alias
        )

    def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
        return {
            (45, "RadixThemesColorModeProvider"): RadixThemesColorModeProvider.create(),
        }


class RadixThemesColorModeProvider(Component):
    tag = "RadixThemesColorModeProvider"

    def _get_imports(self) -> imports.ImportDict:
        return {
            "react": {
                ImportVar(tag="useState", is_default=False),
                ImportVar(tag="useEffect", is_default=False),
            },
            "/utils/context.js": {
                ImportVar(tag="ColorModeContext", is_default=False),
            },
            "next-themes@^0.2.0": {
                ImportVar(tag="useTheme", is_default=False),
            },
        }

    def _get_custom_code(self) -> str | None:
        return (
            """
function %s({ children }) {
  const {theme, setTheme} = useTheme()
  const [colorMode, setColorMode] = useState("light")

  useEffect(() => setColorMode(theme), [theme])

  const toggleColorMode = () => {
    setTheme(theme === "light" ? "dark" : "light")
  }
  return (
    <ColorModeContext.Provider value={[ colorMode, toggleColorMode ]}>
      {children}
    </ColorModeContext.Provider>
  )
}"""
            % self.tag
        )
