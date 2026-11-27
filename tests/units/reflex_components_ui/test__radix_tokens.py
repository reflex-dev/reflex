"""Tests for the generated list of the StyleX modules of reflex-components-ui.

That the list is what its generator produces is checked by the javascript
package (``npm run generate:check``). These tests check that it describes the
javascript the package ships.
"""

import re

from reflex_components_radix.plugin import RADIX_THEMES_PACKAGE
from reflex_components_ui import _radix_tokens as tokens
from reflex_components_ui.constants import JS_SRC

GRAYS = ("gray", "mauve", "olive", "sage", "sand", "slate")

ACCENTS = (
    "amber",
    "blue",
    "bronze",
    "brown",
    "crimson",
    "cyan",
    "gold",
    "grass",
    "gray",
    "green",
    "indigo",
    "iris",
    "jade",
    "lime",
    "mint",
    "orange",
    "pink",
    "plum",
    "purple",
    "red",
    "ruby",
    "sky",
    "teal",
    "tomato",
    "violet",
    "yellow",
)

SCALE_STEPS = (
    *(str(step) for step in range(1, 13)),
    *(f"a{step}" for step in range(1, 13)),
    "contrast",
    "surface",
    "indicator",
    "track",
)


def _exports(module: str) -> list[str]:
    """Read the names a generated javascript module exports.

    Args:
        module: The module, relative to the javascript source.

    Returns:
        The exported names, in the order the module defines them.
    """
    return re.findall(
        r"^export const (\w+) = ", (JS_SRC / module).read_text(), re.MULTILINE
    )


def test_generated_from_the_radix_themes_reflex_installs():
    """The version in the list is the one the Radix components install."""
    assert f"@radix-ui/themes@{tokens.RADIX_THEMES_VERSION}" == RADIX_THEMES_PACKAGE


def test_var_groups_are_the_exports_of_their_modules():
    """Every group is exported by the module it names, and no export is left out."""
    by_module: dict[str, list[str]] = {}
    for name, (module, _) in tokens.VAR_GROUPS.items():
        by_module.setdefault(module, []).append(name)
    generated = sorted(
        path.relative_to(JS_SRC).as_posix()
        for directory in ("colors", "tokens")
        for path in (JS_SRC / directory).iterdir()
    )
    assert sorted(by_module) == generated
    assert {module: _exports(module) for module in by_module} == by_module


def test_color_scales_have_the_radix_steps():
    """A scale has twelve steps, twelve alpha steps and four functional colors."""
    scales = {
        name: variables
        for name, (module, variables) in tokens.VAR_GROUPS.items()
        if module.startswith("colors/")
    }
    colors = sorted({*ACCENTS, *GRAYS} - {"gray"})
    assert sorted(scales) == sorted([*colors, "black", "white"])
    for name in colors:
        assert sorted(scales[name]) == sorted(
            f"--{name}-{step}" for step in SCALE_STEPS
        )
    for name in ("black", "white"):
        assert scales[name] == tuple(f"--{name}-a{step}" for step in range(1, 13))


def test_themed_groups_keep_the_radix_names():
    """The variables a theme sets are the ones Radix components read."""
    assert sorted(tokens.VAR_GROUPS["accent"][1]) == sorted(
        f"--accent-{step}" for step in SCALE_STEPS
    )
    assert sorted(tokens.VAR_GROUPS["gray"][1]) == sorted(
        f"--gray-{step}" for step in SCALE_STEPS
    )
    assert tokens.VAR_GROUPS["scaling"] == ("tokens/scaling.stylex.js", ("--scaling",))
    assert tokens.VAR_GROUPS["radiusFactor"] == (
        "tokens/radius.stylex.js",
        ("--radius-factor", "--radius-full", "--radius-thumb"),
    )
    assert tokens.VAR_GROUPS["space"] == (
        "tokens/space.stylex.js",
        tuple(f"--space-{step}" for step in range(1, 10)),
    )


def test_a_variable_belongs_to_one_group():
    """A custom property can be looked up without knowing its group."""
    names = [name for _, variables in tokens.VAR_GROUPS.values() for name in variables]
    assert len(names) == len(set(names)) == 1070


def test_themes_are_the_exports_of_their_modules():
    """Every value of every theme prop has a theme, in the module the list names."""
    assert {
        name: (f"themes/accent/{name}.js", f"accent{name.capitalize()}")
        for name in ACCENTS
    } == tokens.ACCENT_THEMES
    assert {
        name: (f"themes/gray/{name}.js", f"gray{name.capitalize()}") for name in GRAYS
    } == tokens.GRAY_THEMES
    assert {
        name: ("themes/radius.js", f"radius{name.capitalize()}")
        for name in ("full", "large", "medium", "none", "small")
    } == tokens.RADIUS_THEMES
    assert {
        f"{percent}%": ("themes/scaling.js", f"scaling{percent}")
        for percent in (100, 105, 110, 90, 95)
    } == tokens.SCALING_THEMES
    assert tokens.PANEL_BACKGROUND_THEMES == {
        "solid": ("themes/panel.js", "panelSolid"),
        "translucent": ("themes/panel.js", "panelTranslucent"),
    }
    assert tokens.SCOPE_THEMES == (
        ("themes/scope.js", "spaceScope"),
        ("themes/scope.js", "radiusScope"),
        ("themes/scope.js", "typographyScope"),
        ("themes/scope.js", "shadowScope"),
        ("themes/scope.js", "colorScope"),
    )
    assert tokens.FOCUS_THEME == ("themes/focus.js", "focusScope")
    assert tokens.THEME_STYLES == (
        "themes/theme.js",
        "theme",
        ("light", "dark", "background", "root"),
    )
    by_module: dict[str, list[str]] = {}
    for module, name in (
        *tokens.ACCENT_THEMES.values(),
        *tokens.GRAY_THEMES.values(),
        *tokens.RADIUS_THEMES.values(),
        *tokens.SCALING_THEMES.values(),
        *tokens.PANEL_BACKGROUND_THEMES.values(),
        *tokens.SCOPE_THEMES,
        tokens.FOCUS_THEME,
        tokens.THEME_STYLES[:2],
    ):
        by_module.setdefault(module, []).append(name)
    generated = sorted(
        path.relative_to(JS_SRC).as_posix()
        for path in (JS_SRC / "themes").rglob("*.js")
    )
    assert sorted(by_module) == generated
    assert {module: _exports(module) for module in by_module} == by_module


def test_defaults_are_the_props_of_a_radix_theme():
    """A theme that is given nothing is the default Radix theme."""
    assert tokens.DEFAULTS == {
        "accent_color": "indigo",
        "gray_color": "auto",
        "radius": "medium",
        "scaling": "100%",
        "panel_background": "translucent",
    }


def test_every_accent_has_a_matching_gray():
    """The gray that ``auto`` stands for is a gray theme."""
    assert tuple(tokens.MATCHING_GRAY) == ACCENTS
    assert set(tokens.MATCHING_GRAY.values()) == set(GRAYS)
    assert {
        accent: tokens.MATCHING_GRAY[accent]
        for accent in ("gray", "indigo", "tomato", "jade", "grass", "amber")
    } == {
        "gray": "gray",
        "indigo": "slate",
        "tomato": "mauve",
        "jade": "sage",
        "grass": "olive",
        "amber": "sand",
    }
