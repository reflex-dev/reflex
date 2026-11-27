"""The options of a theme, and the StyleX themes each of them applies.

A theme element is a plain element that carries the class of a StyleX theme
for each option it sets. The themes are generated modules of the javascript
package, listed in ``_radix_tokens``: an element imports the ones it names,
and the build emits the CSS of nothing else.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import operator
from collections.abc import Mapping, Sequence
from typing import Any, Literal, get_args

from reflex_base.utils.exceptions import ReflexError
from reflex_base.utils.imports import ImportDict, ImportVar
from reflex_base.vars.base import LiteralVar, Var

from reflex_components_ui import _radix_tokens
from reflex_components_ui.constants import WEB_DIR
from reflex_components_ui.style.lower import suggest

LiteralAccentColor = Literal[
    "tomato",
    "red",
    "ruby",
    "crimson",
    "pink",
    "plum",
    "purple",
    "violet",
    "iris",
    "indigo",
    "blue",
    "cyan",
    "teal",
    "jade",
    "green",
    "grass",
    "brown",
    "orange",
    "sky",
    "mint",
    "lime",
    "yellow",
    "amber",
    "gold",
    "bronze",
    "gray",
]
LiteralGrayColor = Literal["auto", "gray", "mauve", "slate", "sage", "olive", "sand"]
LiteralRadius = Literal["none", "small", "medium", "large", "full"]
LiteralScaling = Literal["90%", "95%", "100%", "105%", "110%"]
LiteralAppearance = Literal["inherit", "light", "dark"]
LiteralPanelBackground = Literal["solid", "translucent"]

# The values of each option, in the order an error message lists them.
OPTIONS: dict[str, tuple[str, ...]] = {
    "accent_color": get_args(LiteralAccentColor),
    "gray_color": get_args(LiteralGrayColor),
    "radius": get_args(LiteralRadius),
    "scaling": get_args(LiteralScaling),
    "appearance": get_args(LiteralAppearance),
    "panel_background": get_args(LiteralPanelBackground),
}

# The class of every theme element, which the base stylesheet selects on.
THEME_CLASS = "reflex-ui-theme"

# The name the styles of a theme element are imported under: `theme` is what
# an app with Radix Themes imports its own theme as.
_THEME_STYLES = "reflexUITheme"

# The module-level maps an option bound to state is looked up in.
_ACCENT_MAP = "reflexUIAccents"
_GRAY_MAP = "reflexUIGrays"
_MATCHING_GRAY_MAP = "reflexUIMatchingGrays"
_RADIUS_MAP = "reflexUIRadii"
_SCALING_MAP = "reflexUIScalings"
_PANEL_MAP = "reflexUIPanels"
_COLOR_SCHEME_MAP = "reflexUIColorSchemes"
_ELEMENT_RADIUS_MAP = "reflexUIElementRadii"

# What joins the class names of compiled styles, and its local name.
_CLASS_NAME = ("class-name.js", "className")
_CLASS_NAME_ALIAS = "reflexUIClassName"

# What the name of a constant holding joined class names starts with.
_CONSTANT = "reflexUIClasses"


# The theme that declares the steps of the radius scale again.
_RADIUS_SCOPE = next(
    scope for scope in _radix_tokens.SCOPE_THEMES if scope[1] == "radiusScope"
)


class ThemeError(ReflexError, ValueError):
    """A theme option that cannot be applied."""


def _check(name: str, option: str, value: object, accepts: str | None = None) -> None:
    """Fail on a value an option does not take.

    Args:
        name: What the option was given to, which starts the error message.
        option: The option.
        value: Its value.
        accepts: The option whose values it takes, when it is another one.

    Raises:
        ThemeError: If the value is not one of the option's.
    """
    values = OPTIONS[accepts or option]
    if value.__class__ is str and value in values:
        return
    if isinstance(value, Var):
        msg = (
            f"{name}: {option} is bound to state, but the theme of an app is "
            "compiled ahead of time. Give it one of its values, or bind the "
            "option of an rx.ui.theme(...) around the page."
        )
        raise ThemeError(msg)
    shown = f'"{value}"' if isinstance(value, str) else repr(value)
    suggestion = suggest(value, values) if isinstance(value, str) else ""
    choices = ", ".join([f'"{choice}"' for choice in values])
    msg = f"{name}: unknown {option} {shown}.{suggestion} The values are {choices}."
    raise ThemeError(msg)


def _check_flag(name: str, option: str, value: object) -> None:
    """Fail on a value that is not a boolean.

    Args:
        name: What the option was given to, which starts the error message.
        option: The option.
        value: Its value.

    Raises:
        ThemeError: If the value is not True or False.
    """
    if value.__class__ is not bool:
        msg = f"{name}: {option} must be True or False, not {value!r}."
        raise ThemeError(msg)


@dataclasses.dataclass(frozen=True)
class Theme:
    """The look of the rx.ui components across an app.

    Attributes:
        accent_color: The color of the components that stand out.
        gray_color: The gray of text, borders and surfaces. ``"auto"`` is the
            gray that matches the accent color.
        radius: How round corners are.
        scaling: The size of everything, relative to the default.
        appearance: ``"light"`` or ``"dark"`` to keep one whatever the color
            mode of the app, ``"inherit"`` to follow it.
        panel_background: Whether panels such as cards are see-through.
        has_background: Whether the theme paints the background of the page.
    """

    accent_color: LiteralAccentColor = "blue"
    gray_color: LiteralGrayColor = "auto"
    radius: LiteralRadius = "medium"
    scaling: LiteralScaling = "100%"
    appearance: LiteralAppearance = "inherit"
    panel_background: LiteralPanelBackground = "translucent"
    has_background: bool = True

    def __post_init__(self):
        """Check every option, so that a mistake stops the app where it is made.

        Raises:
            ThemeError: If an option has a value it does not take.
        """
        for option in OPTIONS:
            _check("rx.ui.Theme", option, getattr(self, option))
        _check_flag("rx.ui.Theme", "has_background", self.has_background)


@dataclasses.dataclass(frozen=True, slots=True)
class ThemeStyles:
    """What an element needs to carry a theme.

    Attributes:
        classes: The expression of the class names of the theme.
        imports: The module, the export and the local name of everything the
            expression and the declarations name.
        declarations: The module-level statements the expression relies on.
        vars: The Vars the expression reads, for the state they subscribe to.
    """

    classes: str
    imports: tuple[tuple[str, str, str | None], ...]
    declarations: tuple[str, ...] = ()
    vars: tuple[Var, ...] = ()

    def import_dict(self) -> ImportDict:
        """Get the imports in the form a component returns them.

        Returns:
            The exports to import from each module of the javascript package.
        """
        modules: dict[str, list[ImportVar]] = {}
        for module, export, alias in self.imports:
            modules.setdefault(f"$/{WEB_DIR}/{module}", []).append(
                ImportVar(tag=export, alias=alias)
            )
        return dict(modules)


class _Builder:
    """Collects the themes of one element.

    Attributes:
        name: What the options were given to, which starts an error message.
        refs: The compiled styles of the element so far, the last one winning.
        imports: What the styles and the declarations name.
        declarations: The module-level statements the styles rely on.
        vars: The Vars the styles read.
    """

    __slots__ = ("declarations", "imports", "name", "refs", "vars")

    def __init__(self, name: str):
        """Start with nothing.

        Args:
            name: What the options were given to.
        """
        self.name = name
        self.refs: list[str] = []
        self.imports: set[tuple[str, str, str | None]] = set()
        self.declarations: list[str] = []
        self.vars: list[Var] = []

    def add(self, theme: tuple[str, str], alias: str | None = None) -> str:
        """Import a StyleX theme.

        Args:
            theme: The module and the export.
            alias: The local name, when it is not the export.

        Returns:
            The local name.
        """
        self.imports.add((*theme, alias))
        return alias or theme[1]

    def bound(self, value: Var) -> str:
        """Read an option from state.

        Args:
            value: The Var the option is bound to.

        Returns:
            The expression of its value.
        """
        self.vars.append(value)
        return str(value)

    def lookup(
        self, map_name: str, themes: Mapping[str, tuple[str, str]], value: Var
    ) -> str:
        """Choose among every theme of an option where the page runs.

        Args:
            map_name: The name of the module-level map of the themes.
            themes: The theme of each value: every one of them is imported.
            value: The Var that holds the value.

        Returns:
            The expression of the chosen theme.
        """
        entries = ", ".join([
            f"{json.dumps(key)}: {self.add(theme)}" for key, theme in themes.items()
        ])
        self.declarations.append(
            f"const {map_name} = {{ __proto__: null, {entries} }};"
        )
        return f"{map_name}[{self.bound(value)}]"

    def pick(
        self,
        option: str,
        value: Any,
        themes: Mapping[str, tuple[str, str]],
        map_name: str,
    ) -> None:
        """Apply the theme of one option.

        Args:
            option: The option.
            value: Its value: None when it is inherited, or a Var.
            themes: The theme of each value.
            map_name: The name of the map a Var is looked up in.
        """
        if value is None:
            return
        if isinstance(value, Var):
            self.refs.append(self.lookup(map_name, themes, value))
        else:
            _check(self.name, option, value)
            self.refs.append(self.add(themes[value]))

    def call(self, refs: Sequence[str]) -> str:
        """Write the call that joins the class names of compiled styles.

        Args:
            refs: The compiled styles, the last one winning a property.

        Returns:
            The expression of their class names.
        """
        return f"{self.add(_CLASS_NAME, _CLASS_NAME_ALIAS)}({', '.join(refs)})"

    def finish(self, classes: str) -> ThemeStyles:
        """Wrap up what was collected.

        The class names of themes that are all known when the app is compiled
        are joined once, when the module loads, and not at every render.

        Args:
            classes: The expression of the class names of the element.

        Returns:
            What the element needs.
        """
        declarations = self.declarations
        if not self.vars:
            digest = hashlib.sha256(classes.encode()).hexdigest()[:10]
            name = f"{_CONSTANT}_{digest}"
            declarations = [*declarations, f"const {name} = {classes};"]
            classes = name
        return ThemeStyles(
            classes=classes,
            imports=tuple(sorted(self.imports, key=operator.itemgetter(0, 1))),
            declarations=tuple(declarations),
            vars=tuple(self.vars),
        )


def literal_option(value: Any) -> Any:
    """Read a Var that holds a constant as the constant.

    Args:
        value: The value of an option.

    Returns:
        The constant, or the value as given.
    """
    if isinstance(value, LiteralVar) and value._get_all_var_data() is None:
        return value._var_value
    return value


def theme_styles(
    name: str,
    *,
    accent_color: Any = None,
    gray_color: Any = None,
    radius: Any = None,
    scaling: Any = None,
    appearance: Any = None,
    panel_background: Any = None,
    has_background: Any = None,
    app_theme: Theme | None = None,
    style: str | None = None,
) -> ThemeStyles:
    """Work out the StyleX themes of a theme element.

    An option that is None is inherited: the element sets nothing for it.
    A literal option imports the one theme it names. An option bound to state
    imports every theme it could name and chooses among them where the page
    runs.

    An accent color without a gray color keeps the gray around the element,
    as in Radix Themes. The cascade does not tell an element what it inherits,
    so two things are resolved against the theme of the app, which is what a
    theme inherits unless another one stands between them:

    - ``gray_color="auto"`` without an accent color is the gray that matches
      the accent of the app.
    - A gray color without an accent color names the gray accent again when
      the accent of the app is gray: that accent is the gray of the element
      it was declared on.

    Args:
        name: What the options were given to, which starts an error message.
        accent_color: The accent color.
        gray_color: The gray color.
        radius: The radius.
        scaling: The scaling.
        appearance: The appearance.
        panel_background: The panel background.
        has_background: Whether the element paints the background of the
            theme. None paints it when the element sets an appearance.
        app_theme: The theme of the app.
        style: The compiled style of the element itself, which wins over
            what a theme element sets, such as its text color.

    Returns:
        What the element needs to carry the theme.

    Raises:
        ThemeError: If an option has a value it does not take.
    """
    tokens = _radix_tokens
    builder = _Builder(name)
    accent_color = literal_option(accent_color)
    gray_color = literal_option(gray_color)
    appearance = literal_option(appearance)
    has_background = literal_option(has_background)

    for scope in tokens.SCOPE_THEMES:
        builder.refs.append(builder.add(scope))
    builder.refs.append(builder.add(tokens.FOCUS_THEME))

    if gray_color is not None and not isinstance(gray_color, Var):
        _check(name, "gray_color", gray_color)
    if accent_color is None:
        if gray_color is not None and app_theme and app_theme.accent_color == "gray":
            accent_color = "gray"
    elif not isinstance(accent_color, Var):
        _check(name, "accent_color", accent_color)

    builder.pick("accent_color", accent_color, tokens.ACCENT_THEMES, _ACCENT_MAP)
    if gray_color.__class__ is str and gray_color == "auto":
        matching = tokens.MATCHING_GRAY
        if isinstance(accent_color, Var):
            builder.refs.append(
                builder.lookup(
                    _MATCHING_GRAY_MAP,
                    {
                        accent: tokens.GRAY_THEMES[gray]
                        for accent, gray in matching.items()
                    },
                    accent_color,
                )
            )
        else:
            if accent_color is None:
                if app_theme is None:
                    msg = (
                        f'{name}: gray_color "auto" is the gray that matches an '
                        "accent color. Give accent_color too, or name the gray."
                    )
                    raise ThemeError(msg)
                accent_color = app_theme.accent_color
            builder.refs.append(builder.add(tokens.GRAY_THEMES[matching[accent_color]]))
    else:
        builder.pick("gray_color", gray_color, tokens.GRAY_THEMES, _GRAY_MAP)
    builder.pick("radius", radius, tokens.RADIUS_THEMES, _RADIUS_MAP)
    builder.pick("scaling", scaling, tokens.SCALING_THEMES, _SCALING_MAP)
    builder.pick(
        "panel_background",
        panel_background,
        tokens.PANEL_BACKGROUND_THEMES,
        _PANEL_MAP,
    )

    module, export, _ = tokens.THEME_STYLES
    styles = builder.add((module, export), _THEME_STYLES)
    builder.refs.append(f"{styles}.root")
    background = f"{styles}.background"
    if isinstance(appearance, Var):
        bound = builder.bound(appearance)
        own_appearance = f'({bound}) !== "inherit"'
        appearance_ref = f"{styles}[{bound}]"
    else:
        if appearance is not None:
            _check(name, "appearance", appearance)
        own_appearance = appearance is not None and appearance != "inherit"
        appearance_ref = f"{styles}.{appearance}" if own_appearance else None
    if isinstance(has_background, Var):
        builder.refs.append(f"({builder.bound(has_background)}) && {background}")
    elif has_background is None:
        # As in Radix Themes, a theme with an appearance of its own paints its
        # background unless it is told not to.
        if own_appearance.__class__ is str:
            builder.refs.append(f"{own_appearance} && {background}")
        elif own_appearance:
            builder.refs.append(background)
    else:
        _check_flag(name, "has_background", has_background)
        if has_background:
            builder.refs.append(background)
    if appearance_ref is not None:
        builder.refs.append(appearance_ref)
    if style is not None:
        builder.refs.append(style)
    return builder.finish(f'"{THEME_CLASS} " + {builder.call(builder.refs)}')


def app_theme_styles(theme: Theme, style: str | None = None) -> ThemeStyles:
    """Work out the StyleX themes of the element that wraps an app.

    Args:
        theme: The theme of the app.
        style: The compiled style of the element itself.

    Returns:
        What the element needs: every option is set, so that nothing depends
        on what is around the app.
    """
    return theme_styles("rx.ui.Theme", **dataclasses.asdict(theme), style=style)


def color_scheme_styles(name: str, color_scheme: Any) -> ThemeStyles:
    """Work out the StyleX themes of a component with a color of its own.

    The accent, and the focus colors that follow it. A gray component keeps
    the focus colors of the theme, as it does in Radix Themes. A color bound
    to state imports every accent: their class names are joined once, in a
    table the element indexes.

    Args:
        name: The display name of the component, which starts an error message.
        color_scheme: The accent color of the component, or a Var holding it.

    Returns:
        What the element needs.

    Raises:
        ThemeError: If the color is not an accent color.
    """
    tokens = _radix_tokens
    builder = _Builder(name)
    color_scheme = literal_option(color_scheme)

    def themes(accent: str) -> list[str]:
        """Import the themes of one accent.

        Args:
            accent: The accent color.

        Returns:
            The compiled styles of the accent.
        """
        refs = [builder.add(tokens.ACCENT_THEMES[accent])]
        if accent != "gray":
            refs.append(builder.add(tokens.FOCUS_THEME))
        return refs

    if isinstance(color_scheme, Var):
        entries = ", ".join([
            f"{json.dumps(accent)}: {builder.call(themes(accent))}"
            for accent in tokens.ACCENT_THEMES
        ])
        builder.declarations.append(
            f"const {_COLOR_SCHEME_MAP} = {{ __proto__: null, {entries} }};"
        )
        return builder.finish(f"{_COLOR_SCHEME_MAP}[{builder.bound(color_scheme)}]")
    _check(name, "color_scheme", color_scheme, "accent_color")
    return builder.finish(builder.call(themes(color_scheme)))


def radius_styles(name: str, radius: Any) -> ThemeStyles:
    """Work out the StyleX themes of a component with a radius of its own.

    The radius, and the steps of the radius scale, which read it on the
    element they are declared on. A radius bound to state imports the five
    of them: their class names are joined once, in a table the element
    indexes.

    Args:
        name: The display name of the component, which starts an error message.
        radius: The radius of the component, or a Var holding it.

    Returns:
        What the element needs.

    Raises:
        ThemeError: If the radius is not one a theme takes.
    """
    tokens = _radix_tokens
    builder = _Builder(name)
    radius = literal_option(radius)
    scope = builder.add(_RADIUS_SCOPE)
    if isinstance(radius, Var):
        entries = ", ".join([
            f"{json.dumps(value)}: {builder.call([scope, builder.add(theme)])}"
            for value, theme in tokens.RADIUS_THEMES.items()
        ])
        builder.declarations.append(
            f"const {_ELEMENT_RADIUS_MAP} = {{ __proto__: null, {entries} }};"
        )
        return builder.finish(f"{_ELEMENT_RADIUS_MAP}[{builder.bound(radius)}]")
    _check(name, "radius", radius)
    return builder.finish(
        builder.call([scope, builder.add(tokens.RADIUS_THEMES[radius])])
    )
