"""Tests for reflex_components_ui.themes."""

import dataclasses
from typing import Any, get_args

import pytest
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar
from reflex_components_ui import _radix_tokens, themes
from reflex_components_ui.themes import (
    Theme,
    ThemeError,
    ThemeStyles,
    app_theme_styles,
    color_scheme_styles,
    theme_styles,
)

import reflex as rx

SCOPES = ("spaceScope", "radiusScope", "typographyScope", "shadowScope", "colorScope")
SCOPE_IMPORTS = (
    ("themes/scope.js", "colorScope", None),
    ("themes/scope.js", "radiusScope", None),
    ("themes/scope.js", "shadowScope", None),
    ("themes/scope.js", "spaceScope", None),
    ("themes/scope.js", "typographyScope", None),
)
FOCUS_IMPORT = ("themes/focus.js", "focusScope", None)
STYLES_IMPORT = ("themes/theme.js", "theme", "reflexUITheme")

ACCENT_VALUES = (
    '"tomato", "red", "ruby", "crimson", "pink", "plum", "purple", "violet", '
    '"iris", "indigo", "blue", "cyan", "teal", "jade", "green", "grass", '
    '"brown", "orange", "sky", "mint", "lime", "yellow", "amber", "gold", '
    '"bronze", "gray"'
)

ACCENT_MAP = (
    "const reflexUIAccents = { "
    + ", ".join(
        f'"{name}": accent{name.capitalize()}'
        for name in sorted(_radix_tokens.ACCENT_THEMES)
    )
    + " };"
)
ACCENT_IMPORTS = tuple(
    (f"themes/accent/{name}.js", f"accent{name.capitalize()}", None)
    for name in sorted(_radix_tokens.ACCENT_THEMES)
)
GRAY_IMPORTS = tuple(
    (f"themes/gray/{name}.js", f"gray{name.capitalize()}", None)
    for name in sorted(_radix_tokens.GRAY_THEMES)
)


class ThemeState(rx.State):
    """State whose fields are bound to theme options."""

    accent: str = "red"
    gray: str = "sand"
    radius: str = "full"
    scaling: str = "90%"
    panel: str = "solid"
    appearance: str = "dark"
    background: bool = True


def test_literal_types_are_the_generated_themes():
    """A type checker accepts exactly the values a StyleX theme exists for."""
    assert sorted(get_args(themes.LiteralAccentColor)) == sorted(
        _radix_tokens.ACCENT_THEMES
    )
    assert sorted(get_args(themes.LiteralGrayColor)) == sorted([
        "auto",
        *_radix_tokens.GRAY_THEMES,
    ])
    assert sorted(get_args(themes.LiteralRadius)) == sorted(_radix_tokens.RADIUS_THEMES)
    assert sorted(get_args(themes.LiteralScaling)) == sorted(
        _radix_tokens.SCALING_THEMES
    )
    assert sorted(get_args(themes.LiteralPanelBackground)) == sorted(
        _radix_tokens.PANEL_BACKGROUND_THEMES
    )
    module, export, styles = _radix_tokens.THEME_STYLES
    assert (module, export) == STYLES_IMPORT[:2]
    assert sorted(styles) == sorted([
        "root",
        "background",
        *(set(get_args(themes.LiteralAppearance)) - {"inherit"}),
    ])
    assert themes.OPTIONS == {
        "accent_color": get_args(themes.LiteralAccentColor),
        "gray_color": get_args(themes.LiteralGrayColor),
        "radius": get_args(themes.LiteralRadius),
        "scaling": get_args(themes.LiteralScaling),
        "appearance": ("inherit", "light", "dark"),
        "panel_background": get_args(themes.LiteralPanelBackground),
    }


def test_theme_defaults_are_the_ones_of_radix_but_for_the_accent():
    """Reflex has always made blue the accent, where Radix Themes has indigo."""
    assert dataclasses.asdict(Theme()) == {
        **_radix_tokens.DEFAULTS,
        "accent_color": "blue",
        "appearance": "inherit",
        "has_background": True,
    }
    assert _radix_tokens.DEFAULTS["accent_color"] == "indigo"


def test_theme_is_a_frozen_value():
    theme = Theme(accent_color="indigo", radius="large")
    assert theme == Theme(radius="large", accent_color="indigo")
    assert hash(theme) == hash(Theme(radius="large", accent_color="indigo"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        theme.radius = "small"  # pyright: ignore [reportAttributeAccessIssue]


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (
            {"accent_color": "indgo"},
            'rx.ui.Theme: unknown accent_color "indgo". Did you mean "indigo"? '
            f"The values are {ACCENT_VALUES}.",
        ),
        (
            {"accent_color": "mauve"},
            f'rx.ui.Theme: unknown accent_color "mauve". The values are {ACCENT_VALUES}.',
        ),
        (
            {"gray_color": "slat"},
            'rx.ui.Theme: unknown gray_color "slat". Did you mean "slate"? The '
            'values are "auto", "gray", "mauve", "slate", "sage", "olive", "sand".',
        ),
        (
            {"radius": "big"},
            'rx.ui.Theme: unknown radius "big". The values are "none", "small", '
            '"medium", "large", "full".',
        ),
        (
            {"scaling": 100},
            "rx.ui.Theme: unknown scaling 100. The values are "
            '"90%", "95%", "100%", "105%", "110%".',
        ),
        (
            {"scaling": "100"},
            'rx.ui.Theme: unknown scaling "100". Did you mean "100%"? The values '
            'are "90%", "95%", "100%", "105%", "110%".',
        ),
        (
            {"appearance": "system"},
            'rx.ui.Theme: unknown appearance "system". The values are '
            '"inherit", "light", "dark".',
        ),
        (
            {"panel_background": None},
            "rx.ui.Theme: unknown panel_background None. The values are "
            '"solid", "translucent".',
        ),
        (
            {"has_background": "yes"},
            "rx.ui.Theme: has_background must be True or False, not 'yes'.",
        ),
        (
            {"accent_color": ThemeState.accent},
            "rx.ui.Theme: accent_color is bound to state, but the theme of an "
            "app is compiled ahead of time. Give it one of its values, or bind "
            "the option of an rx.ui.theme(...) around the page.",
        ),
    ],
)
def test_theme_refuses_a_value_an_option_does_not_take(
    options: dict[str, Any], message: str
):
    """A mistake in rxconfig.py stops the app there, and says what to write.

    Args:
        options: The options of the theme.
        message: The whole error message.
    """
    with pytest.raises(ThemeError) as error:
        Theme(**options)
    assert str(error.value) == message


def test_app_theme_sets_every_option():
    """The element around an app depends on nothing outside it."""
    assert app_theme_styles(
        Theme(accent_color="indigo", radius="large")
    ) == ThemeStyles(
        refs=(
            *SCOPES,
            "focusScope",
            "accentIndigo",
            "graySlate",
            "radiusLarge",
            "scaling100",
            "panelTranslucent",
            "reflexUITheme.root",
            "reflexUITheme.background",
        ),
        imports=(
            ("themes/accent/indigo.js", "accentIndigo", None),
            FOCUS_IMPORT,
            ("themes/gray/slate.js", "graySlate", None),
            ("themes/panel.js", "panelTranslucent", None),
            ("themes/radius.js", "radiusLarge", None),
            ("themes/scaling.js", "scaling100", None),
            *SCOPE_IMPORTS,
            STYLES_IMPORT,
        ),
        class_name="reflex-ui-theme",
    )
    assert app_theme_styles(
        Theme(
            accent_color="gray",
            gray_color="olive",
            radius="none",
            scaling="110%",
            appearance="dark",
            panel_background="solid",
            has_background=False,
        )
    ) == ThemeStyles(
        refs=(
            *SCOPES,
            "focusScope",
            "accentGray",
            "grayOlive",
            "radiusNone",
            "scaling110",
            "panelSolid",
            "reflexUITheme.root",
            "reflexUITheme.dark",
        ),
        imports=(
            ("themes/accent/gray.js", "accentGray", None),
            FOCUS_IMPORT,
            ("themes/gray/olive.js", "grayOlive", None),
            ("themes/panel.js", "panelSolid", None),
            ("themes/radius.js", "radiusNone", None),
            ("themes/scaling.js", "scaling110", None),
            *SCOPE_IMPORTS,
            STYLES_IMPORT,
        ),
        class_name="reflex-ui-theme dark",
    )


def test_every_accent_has_the_gray_that_matches_it():
    """``auto`` is resolved when the app is compiled."""
    for accent, gray in _radix_tokens.MATCHING_GRAY.items():
        styles = app_theme_styles(Theme(accent_color=accent))  # pyright: ignore [reportArgumentType]
        assert styles.refs[6:8] == (
            f"accent{accent.capitalize()}",
            f"gray{gray.capitalize()}",
        )
        assert styles.imports[:3] == (
            (f"themes/accent/{accent}.js", f"accent{accent.capitalize()}", None),
            FOCUS_IMPORT,
            (f"themes/gray/{gray}.js", f"gray{gray.capitalize()}", None),
        )


def _nested(
    refs: tuple[str, ...],
    imports: tuple[tuple[str, str, str | None], ...],
    class_name: str = "reflex-ui-theme",
) -> ThemeStyles:
    """Build what a nested theme is expected to need.

    Args:
        refs: The arguments after the scopes, the focus and before the root style.
        imports: The imports beside the ones every theme element has.
        class_name: The class names of the element.

    Returns:
        The expected styles.
    """
    after = tuple(ref for ref in refs if ref.startswith("reflexUITheme"))
    before = refs[: len(refs) - len(after)]
    return ThemeStyles(
        refs=(*SCOPES, "focusScope", *before, "reflexUITheme.root", *after),
        imports=tuple(sorted([*imports, FOCUS_IMPORT, *SCOPE_IMPORTS, STYLES_IMPORT])),
        class_name=class_name,
    )


RED = ("themes/accent/red.js", "accentRed", None)
MAUVE = ("themes/gray/mauve.js", "grayMauve", None)
OLIVE = ("themes/gray/olive.js", "grayOlive", None)
GRAY_ACCENT = ("themes/accent/gray.js", "accentGray", None)


@pytest.mark.parametrize(
    ("options", "app_theme", "expected"),
    [
        # Nothing set: the element only declares again what reads the theme.
        ({}, Theme(), _nested((), ())),
        # Under the automatic gray of the app, the gray follows the accent.
        (
            {"accent_color": "red"},
            Theme(),
            _nested(("accentRed", "grayMauve"), (RED, MAUVE)),
        ),
        (
            {"accent_color": "red"},
            Theme(gray_color="sand"),
            _nested(("accentRed",), (RED,)),
        ),
        (
            {"accent_color": "red", "gray_color": "olive"},
            Theme(),
            _nested(("accentRed", "grayOlive"), (RED, OLIVE)),
        ),
        (
            {"accent_color": "red", "gray_color": "auto"},
            Theme(gray_color="sand"),
            _nested(("accentRed", "grayMauve"), (RED, MAUVE)),
        ),
        # A gray alone, and the gray that matches the accent of the app.
        ({"gray_color": "olive"}, Theme(), _nested(("grayOlive",), (OLIVE,))),
        (
            {"gray_color": "auto"},
            Theme(accent_color="red"),
            _nested(("grayMauve",), (MAUVE,)),
        ),
        # Under the gray accent, the accent is named again to follow the gray.
        (
            {"gray_color": "olive"},
            Theme(accent_color="gray"),
            _nested(("accentGray", "grayOlive"), (GRAY_ACCENT, OLIVE)),
        ),
        (
            {"radius": "full", "scaling": "90%", "panel_background": "solid"},
            Theme(),
            _nested(
                ("radiusFull", "scaling90", "panelSolid"),
                (
                    ("themes/radius.js", "radiusFull", None),
                    ("themes/scaling.js", "scaling90", None),
                    ("themes/panel.js", "panelSolid", None),
                ),
            ),
        ),
        # An appearance paints the background unless it is told not to.
        (
            {"appearance": "dark"},
            Theme(),
            _nested(
                ("reflexUITheme.background", "reflexUITheme.dark"),
                (),
                "reflex-ui-theme dark",
            ),
        ),
        (
            {"appearance": "light", "has_background": False},
            Theme(),
            _nested(("reflexUITheme.light",), (), "reflex-ui-theme light"),
        ),
        ({"appearance": "inherit"}, Theme(), _nested((), ())),
        (
            {"has_background": True},
            Theme(),
            _nested(("reflexUITheme.background",), ()),
        ),
        # A Var that holds a constant is the constant.
        (
            {
                "accent_color": LiteralVar.create("red"),
                "appearance": LiteralVar.create("dark"),
                "has_background": LiteralVar.create(False),
            },
            Theme(),
            _nested(
                ("accentRed", "grayMauve", "reflexUITheme.dark"),
                (RED, MAUVE),
                "reflex-ui-theme dark",
            ),
        ),
    ],
)
def test_nested_theme_sets_what_it_is_given(
    options: dict[str, Any], app_theme: Theme, expected: ThemeStyles
):
    """A literal option imports the one StyleX theme it names.

    Args:
        options: The options of the nested theme.
        app_theme: The theme of the app.
        expected: What the element needs.
    """
    assert theme_styles("rx.ui.theme", **options, app_theme=app_theme) == expected


def test_accent_bound_to_state_imports_every_accent():
    """The page chooses among all of them, and the gray that matches each."""
    accent = str(ThemeState.accent)
    styles = theme_styles(
        "rx.ui.theme", accent_color=ThemeState.accent, app_theme=Theme()
    )
    assert styles.refs == (
        *SCOPES,
        "focusScope",
        f"reflexUIAccents[{accent}]",
        f"reflexUIMatchingGrays[{accent}]",
        "reflexUITheme.root",
    )
    assert styles.imports == tuple(
        sorted([
            *ACCENT_IMPORTS,
            *GRAY_IMPORTS,
            FOCUS_IMPORT,
            *SCOPE_IMPORTS,
            STYLES_IMPORT,
        ])
    )
    assert styles.declarations == (
        ACCENT_MAP,
        "const reflexUIMatchingGrays = { "
        + ", ".join(
            f'"{name}": gray{gray.capitalize()}'
            for name, gray in sorted(_radix_tokens.MATCHING_GRAY.items())
        )
        + " };",
    )
    assert styles.class_name == "reflex-ui-theme"
    assert styles.var_data == ThemeState.accent._get_all_var_data()

    # With a gray of its own, only the accents are imported.
    styles = theme_styles(
        "rx.ui.theme",
        accent_color=ThemeState.accent,
        gray_color="sand",
        app_theme=Theme(),
    )
    assert styles.refs == (
        *SCOPES,
        "focusScope",
        f"reflexUIAccents[{accent}]",
        "graySand",
        "reflexUITheme.root",
    )
    assert styles.imports == tuple(
        sorted([
            *ACCENT_IMPORTS,
            ("themes/gray/sand.js", "graySand", None),
            FOCUS_IMPORT,
            *SCOPE_IMPORTS,
            STYLES_IMPORT,
        ])
    )
    assert styles.declarations == (ACCENT_MAP,)


def test_every_option_can_be_bound_to_state():
    state = ThemeState
    styles = theme_styles(
        "rx.ui.theme",
        gray_color=state.gray,
        radius=state.radius,
        scaling=state.scaling,
        panel_background=state.panel,
        appearance=state.appearance,
        has_background=state.background,
        app_theme=Theme(),
    )
    appearance = str(state.appearance)
    assert styles.refs == (
        *SCOPES,
        "focusScope",
        f"reflexUIGrays[{state.gray!s}]",
        f"reflexUIRadii[{state.radius!s}]",
        f"reflexUIScalings[{state.scaling!s}]",
        f"reflexUIPanels[{state.panel!s}]",
        "reflexUITheme.root",
        f"({state.background!s}) && reflexUITheme.background",
        f"reflexUITheme[{appearance}]",
        f'({appearance}) !== "inherit" && {{ $$css: true, appearance: {appearance} }}',
    )
    assert styles.declarations == (
        'const reflexUIGrays = { "gray": grayGray, "mauve": grayMauve, '
        '"olive": grayOlive, "sage": graySage, "sand": graySand, '
        '"slate": graySlate };',
        'const reflexUIRadii = { "full": radiusFull, "large": radiusLarge, '
        '"medium": radiusMedium, "none": radiusNone, "small": radiusSmall };',
        'const reflexUIScalings = { "100%": scaling100, "105%": scaling105, '
        '"110%": scaling110, "90%": scaling90, "95%": scaling95 };',
        'const reflexUIPanels = { "solid": panelSolid, '
        '"translucent": panelTranslucent };',
    )
    assert styles.imports == tuple(
        sorted([
            *GRAY_IMPORTS,
            FOCUS_IMPORT,
            *(
                ("themes/panel.js", name, None)
                for name in ("panelSolid", "panelTranslucent")
            ),
            *(
                ("themes/radius.js", f"radius{name}", None)
                for name in ("Full", "Large", "Medium", "None", "Small")
            ),
            *(
                ("themes/scaling.js", f"scaling{name}", None)
                for name in ("100", "105", "110", "90", "95")
            ),
            *SCOPE_IMPORTS,
            STYLES_IMPORT,
        ])
    )
    assert styles.var_data == rx.vars.VarData.merge(
        state.gray._get_all_var_data(),
        state.radius._get_all_var_data(),
        state.scaling._get_all_var_data(),
        state.panel._get_all_var_data(),
        state.appearance._get_all_var_data(),
        state.background._get_all_var_data(),
    )

    # An appearance bound to state paints the background when it is one.
    styles = theme_styles("rx.ui.theme", appearance=state.appearance, app_theme=Theme())
    assert styles.refs == (
        *SCOPES,
        "focusScope",
        "reflexUITheme.root",
        f'({appearance}) !== "inherit" && reflexUITheme.background',
        f"reflexUITheme[{appearance}]",
        f'({appearance}) !== "inherit" && {{ $$css: true, appearance: {appearance} }}',
    )


@pytest.mark.parametrize(
    ("options", "app_theme", "message"),
    [
        (
            {"accent_color": "rubby"},
            Theme(),
            'rx.ui.theme: unknown accent_color "rubby". Did you mean "ruby"? '
            f"The values are {ACCENT_VALUES}.",
        ),
        (
            {"gray_color": "blue"},
            Theme(),
            'rx.ui.theme: unknown gray_color "blue". The values are "auto", '
            '"gray", "mauve", "slate", "sage", "olive", "sand".',
        ),
        (
            {"radius": "round"},
            Theme(),
            'rx.ui.theme: unknown radius "round". The values are "none", '
            '"small", "medium", "large", "full".',
        ),
        (
            {"appearance": "night"},
            Theme(),
            'rx.ui.theme: unknown appearance "night". Did you mean "light"? The values are '
            '"inherit", "light", "dark".',
        ),
        (
            {"has_background": 1},
            Theme(),
            "rx.ui.theme: has_background must be True or False, not 1.",
        ),
        (
            {"gray_color": "auto"},
            None,
            'rx.ui.theme: gray_color "auto" is the gray that matches an accent '
            "color. Give accent_color too, or name the gray.",
        ),
    ],
)
def test_nested_theme_refuses_a_value_an_option_does_not_take(
    options: dict[str, Any], app_theme: Theme | None, message: str
):
    """The error names the component and lists what the option takes.

    Args:
        options: The options of the nested theme.
        app_theme: The theme of the app.
        message: The whole error message.
    """
    with pytest.raises(ThemeError) as error:
        theme_styles("rx.ui.theme", **options, app_theme=app_theme)
    assert str(error.value) == message


def test_color_scheme_is_an_accent_on_one_element():
    """A component with a color imports its accent, and the focus that follows."""
    assert color_scheme_styles("rx.ui.button", "red") == ThemeStyles(
        refs=("accentRed", "focusScope"), imports=(RED, FOCUS_IMPORT)
    )
    assert color_scheme_styles("rx.ui.button", LiteralVar.create("red")) == ThemeStyles(
        refs=("accentRed", "focusScope"), imports=(RED, FOCUS_IMPORT)
    )
    # A gray component keeps the focus colors of the theme, as in Radix Themes.
    assert color_scheme_styles("rx.ui.button", "gray") == ThemeStyles(
        refs=("accentGray",), imports=(GRAY_ACCENT,)
    )
    accent = str(ThemeState.accent)
    assert color_scheme_styles("rx.ui.button", ThemeState.accent) == ThemeStyles(
        refs=(f"reflexUIAccents[{accent}]", f'({accent}) !== "gray" && focusScope'),
        imports=(*ACCENT_IMPORTS, FOCUS_IMPORT),
        declarations=(ACCENT_MAP,),
        var_data=ThemeState.accent._get_all_var_data(),
    )
    with pytest.raises(ThemeError) as error:
        color_scheme_styles("rx.ui.button", "slate")
    assert str(error.value) == (
        f'rx.ui.button: unknown color_scheme "slate". The values are {ACCENT_VALUES}.'
    )


def test_import_dict_names_the_modules_as_an_app_imports_them():
    assert color_scheme_styles("rx.ui.button", "red").import_dict() == {
        "$/reflex-ui/themes/accent/red.js": [ImportVar(tag="accentRed")],
        "$/reflex-ui/themes/focus.js": [ImportVar(tag="focusScope")],
    }
    assert theme_styles("rx.ui.theme", app_theme=Theme()).import_dict() == {
        "$/reflex-ui/themes/focus.js": [ImportVar(tag="focusScope")],
        "$/reflex-ui/themes/scope.js": [
            ImportVar(tag="colorScope"),
            ImportVar(tag="radiusScope"),
            ImportVar(tag="shadowScope"),
            ImportVar(tag="spaceScope"),
            ImportVar(tag="typographyScope"),
        ],
        "$/reflex-ui/themes/theme.js": [ImportVar(tag="theme", alias="reflexUITheme")],
    }
