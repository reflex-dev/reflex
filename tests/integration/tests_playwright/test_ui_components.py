"""The rx.ui components in a real app, in dev and prod.

One app is shared by every test of the components: add a page or an element to
``UIComponentsApp`` rather than a new app. It is built twice, on its own and
beside Radix Themes: the stylesheet of Radix Themes is unlayered and defines
every color scale on the root element, so only the app without it shows what
the rx.ui stylesheet does alone.
"""

import functools
import hashlib
import json
import re
import shutil
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Browser, Page, Route, expect
from reflex_components_ui import _radix_tokens
from reflex_components_ui.constants import JS_SRC

from reflex.testing import AppHarness, AppHarnessProd, chdir
from reflex.utils import build

# What the box sets on its own, then the `style` and `class_name` of each box
# of the index page: its padding shows which stylesheet won.
BOX_STYLES = {
    # The box against the browser's defaults.
    "plain": {"display": "block", "box-sizing": "border-box", "padding": "0px"},
    # A `style` beats the resets of Reflex and Tailwind, which zero the padding.
    "styled": {"display": "block", "box-sizing": "border-box", "padding": "4px"},
    # A Tailwind utility beats the `style` of the box.
    "utility": {"display": "block", "box-sizing": "border-box", "padding": "32px"},
    # An unlayered stylesheet beats both.
    "unlayered": {"display": "block", "box-sizing": "border-box", "padding": "2px"},
}

# A style of the literal page as it is compiled, and what the caching test
# changes it to.
LITERAL_STYLE = '"paddingTop": "6px"'
CHANGED_STYLE = '"paddingTop": "7px"'

# The elements of the styled page below the first breakpoint, before any event.
STYLED = {
    # A width bound to state.
    "var": {"width": "100px"},
    "hover": {"color": "rgb(0, 0, 0)"},
    "responsive": {"margin-top": "2px"},
    # A variant bound to state: the base, and what its value changes.
    "tone": {
        "color": "rgb(0, 0, 255)",
        "background-color": "rgb(0, 128, 0)",
        "padding": "1px",
    },
    # The same variant with a value known at compile time.
    "loud": {
        "color": "rgb(255, 255, 255)",
        "background-color": "rgb(255, 0, 0)",
        "padding": "1px",
    },
}

# What differs from STYLED at and above the first breakpoint.
STYLED_WIDE = {**STYLED, "responsive": {"margin-top": "6px"}}

# What differs from STYLED once the state has changed.
STYLED_CHANGED = {
    **STYLED,
    "var": {"width": "200px"},
    "tone": {
        "color": "rgb(255, 255, 255)",
        "background-color": "rgb(255, 0, 0)",
        "padding": "1px",
    },
}

# The declarations of the styled page: one for each distinct style, with the
# constant that holds its class names. The hundred rows share the last.
STYLED_PAGE_DECLARATIONS = [
    (
        'const sx_e5e3dab07a = stylex.create({ s: {"boxSizing": "border-box", '
        '"display": "block", "color": {"default": "rgb(0, 0, 0)", ":hover": '
        '"rgb(255, 0, 0)"}} });'
    ),
    "const sx_e5e3dab07a_c = stylex.props(sx_e5e3dab07a.s).className;",
    (
        'const sx_4c7f040d01 = stylex.create({ s: {"boxSizing": "border-box", '
        '"display": "block", "marginTop": {"default": "2px", "@media screen and '
        '(min-width: 30em)": "6px"}} });'
    ),
    "const sx_4c7f040d01_c = stylex.props(sx_4c7f040d01.s).className;",
    (
        'const sx_9cbecd042a = stylex.create({ s: {"color": "rgb(255, 255, 255)", '
        '"paddingTop": "1px", "paddingRight": "1px", "paddingBottom": "1px", '
        '"paddingLeft": "1px", "backgroundColor": "rgb(255, 0, 0)"} });'
    ),
    "const sx_9cbecd042a_c = stylex.props(sx_9cbecd042a.s).className;",
    (
        'const sx_e9f4c4c063 = stylex.create({ s: {"boxSizing": "border-box", '
        '"display": "block", "paddingTop": "3px", "paddingRight": "3px", '
        '"paddingBottom": "3px", "paddingLeft": "3px", "opacity": {":hover": 0.5}} });'
    ),
    "const sx_e9f4c4c063_c = stylex.props(sx_e9f4c4c063.s).className;",
]

# The declarations of its elements that read state, which the compiler moves
# into a module of their own: a custom property for the width, and the class
# names of each value of the variant.
STYLED_MEMO_DECLARATIONS = [
    (
        'const sx_723c142d42 = stylex.create({ s: {"boxSizing": "border-box", '
        '"display": "block", "width": "var(--v0)"} });'
    ),
    "const sx_723c142d42_c = stylex.props(sx_723c142d42.s).className;",
    (
        'const sx_5f1012736b = stylex.create({ s: {"paddingTop": "1px", '
        '"paddingRight": "1px", "paddingBottom": "1px", "paddingLeft": "1px"}, a0_0: '
        '{"color": "rgb(0, 0, 255)", "backgroundColor": "rgb(0, 128, 0)"}, a0_1: '
        '{"color": "rgb(255, 255, 255)", "backgroundColor": "rgb(255, 0, 0)"}, a0: '
        '{"color": "rgb(0, 0, 255)"} });'
    ),
    "const sx_5f1012736b_c = stylex.props(sx_5f1012736b.s).className;",
    (
        "const sx_5f1012736b_0 = { __proto__: null, "
        '"calm": stylex.props(sx_5f1012736b.a0_0).className, '
        '"loud": stylex.props(sx_5f1012736b.a0_1).className };'
    ),
    "const sx_5f1012736b_0d = stylex.props(sx_5f1012736b.a0).className;",
]


# The colors the theme pages are read through, as Radix Themes defines them.
INDIGO_11 = {"light": "rgb(58, 91, 199)", "dark": "rgb(158, 177, 255)"}
RED_11 = {"light": "rgb(206, 44, 49)", "dark": "rgb(255, 149, 146)"}
SLATE_2 = {"light": "rgb(249, 249, 251)", "dark": "rgb(24, 25, 27)"}

# The scripts of the token sweep of the javascript package, which read every
# custom property through a property of its type and hold the exceptions.
SWEEP_HARNESS = JS_SRC.parent / "tests" / "harness"
SWEEP_SCRIPTS = "/__reflex_ui_sweep__/"


def UIComponentsApp(radix: bool = False):
    """An app with a page for each thing the rx.ui tests look at.

    Args:
        radix: Whether the app also has Radix Themes and its components.
    """
    import json
    from pathlib import Path
    from typing import Any, ClassVar, Literal

    from reflex_components_ui import _radix_tokens
    from reflex_components_ui.base import UIComponent
    from reflex_components_ui.style import ComponentStyles

    import reflex as rx

    tokens = rx.ui.tokens

    class StyleState(rx.State):
        """What the styles of the styled page are bound to."""

        width: rx.Field[str] = rx.field("100px")
        tone: rx.Field[str] = rx.field("calm")

        @rx.event
        def change(self):
            """Change every value a style is bound to."""
            self.width = "200px"
            self.tone = "loud"

    class Tone(UIComponent):
        """An element whose look a prop selects."""

        styles: ClassVar[ComponentStyles] = {
            "base": {"color": "rgb(0, 0, 255)", "padding": "1px"},
            "variants": {
                "tone": {
                    "calm": {"background_color": "rgb(0, 128, 0)"},
                    "loud": {
                        "background_color": "rgb(255, 0, 0)",
                        "color": "rgb(255, 255, 255)",
                    },
                },
            },
        }

        # Which look the element has.
        tone: rx.Var[Literal["calm", "loud"]]

    class Chip(UIComponent):
        """An element with a color of its own."""

        styles: ClassVar[ComponentStyles] = {
            "base": {
                "background_color": tokens.accent[9],
                "outline_color": tokens.focus[8],
            },
        }

        # The accent color of the element.
        color_scheme: rx.Var[str]

    def index():
        return rx.el.main(
            rx.ui.box("plain", id="plain"),
            rx.ui.box("styled", id="styled", style={"padding": "4px"}),
            rx.ui.box(
                "utility", id="utility", style={"padding": "4px"}, class_name="p-8"
            ),
            rx.ui.box(
                "unlayered",
                id="unlayered",
                style={"padding": "4px"},
                class_name="p-8 unlayered",
            ),
        )

    def literal():
        return rx.ui.box("literal", id="literal", style={"padding": "6px"})

    def probe(name: str):
        # Each style reads a token through a property that takes its value.
        return rx.ui.box(
            name,
            id=name,
            style={
                "color": tokens.accent[11],
                "background_color": tokens.gray[2],
                "border_top_left_radius": tokens.radius[3],
                "padding_top": tokens.space[4],
                "font_size": tokens.font_size[2],
            },
        )

    def theme():
        return rx.el.main(
            probe("root-probe"),
            rx.ui.theme(
                probe("nested-probe"),
                rx.el.div(
                    probe("popover-probe"),
                    id="popover",
                    custom_attrs={"popover": "auto"},
                ),
                accent_color="red",
                radius="full",
                scaling="110%",
                appearance="dark",
                id="nested",
            ),
            probe("after-probe"),
            Chip.create("theme", id="chip-theme"),
            Chip.create("red", id="chip-red", color_scheme="red"),
            Chip.create("gray", id="chip-gray", color_scheme="gray"),
            rx.el.button("toggle", id="toggle", on_click=rx.toggle_color_mode),
        )

    # The themes the sweep compares with Radix Themes: every accent with the
    # gray that matches it and every gray, in both appearances, then every
    # radius, scaling and panel background. Each sets every option, as a
    # nested theme of Radix Themes inherits from the Radix theme of the app
    # and one of rx.ui from the rx.ui one. A gray is given an appearance
    # because Radix Themes has no rule for the plain gray: without the class
    # of an appearance, its nested theme keeps the gray around it.
    defaults = {
        "accent_color": "indigo",
        "gray_color": "auto",
        "radius": "medium",
        "scaling": "100%",
        "panel_background": "translucent",
    }
    variations = [
        {"accent_color": accent, "appearance": appearance}
        for accent in _radix_tokens.ACCENT_THEMES
        for appearance in ("light", "dark")
    ]
    variations += [
        {"gray_color": gray, "appearance": appearance}
        for gray in _radix_tokens.GRAY_THEMES
        for appearance in ("light", "dark")
    ]
    variations += [{"radius": radius} for radius in _radix_tokens.RADIUS_THEMES]
    variations += [{"scaling": scaling} for scaling in _radix_tokens.SCALING_THEMES]
    variations += [
        {"panel_background": panel} for panel in _radix_tokens.PANEL_BACKGROUND_THEMES
    ]
    configs: list[dict[str, Any]] = [
        {**defaults, **variation} for variation in variations
    ]

    def sweep():
        themes = []
        for index, config in enumerate(configs):
            label = {"data-sweep": json.dumps(config)}
            themes.append(rx.ui.theme(id=f"ui-{index}", custom_attrs=label, **config))
            if radix:
                # Reflex keeps the appearance of an `rx.theme` for the color
                # mode of the app. Radix Themes selects on the class, and gives
                # a theme with an appearance its background.
                options: dict[str, Any] = {
                    k: v for k, v in config.items() if k != "appearance"
                }
                if "appearance" in config:
                    options.update(class_name=config["appearance"], has_background=True)
                themes.append(
                    rx.theme(id=f"radix-{index}", custom_attrs=label, **options)
                )
        # The tokens no theme defines are on a page through what uses them.
        uses = rx.ui.box(cursor=tokens.cursor.button, color=tokens.white.a[1])
        return rx.el.main(*themes, uses)

    def buttons():
        return rx.fragment(
            rx.button("accent"),
            rx.button("green", color_scheme="green", variant="soft"),
        )

    def mixed():
        return rx.el.main(
            rx.button("radix", id="radix-button"),
            probe("ui-box"),
            # Beside Radix Themes a theme with an appearance names its gray:
            # the Radix stylesheet sets the plain gray wherever the class of
            # an appearance is.
            rx.ui.theme(
                buttons(),
                accent_color="red",
                gray_color="slate",
                appearance="dark",
                id="ui-dark",
            ),
            rx.theme(
                buttons(),
                accent_color="red",
                gray_color="slate",
                class_name="dark",
                has_background=True,
                id="radix-dark",
            ),
        )

    def styled():
        return rx.el.main(
            rx.ui.box("var", id="var", width=StyleState.width),
            rx.ui.box(
                "hover",
                id="hover",
                style={"color": "rgb(0, 0, 0)", "_hover": {"color": "rgb(255, 0, 0)"}},
            ),
            rx.ui.box("responsive", id="responsive", margin_top=["2px", "6px"]),
            Tone.create("tone", id="tone", tone=StyleState.tone),
            Tone.create("loud", id="loud", tone="loud"),
            rx.el.button("change", id="change", on_click=StyleState.change),
            *[
                rx.ui.box(
                    f"row {index}",
                    class_name="row",
                    style={"padding": "3px", "_hover": {"opacity": 0.5}},
                )
                for index in range(100)
            ],
        )

    assets = Path.cwd() / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "unlayered.css").write_text(".unlayered { padding: 2px }")

    app = rx.App(stylesheets=["unlayered.css"])
    app.add_page(index)
    app.add_page(literal, route="/literal")
    app.add_page(styled, route="/styled")
    app.add_page(theme, route="/theme")
    app.add_page(sweep, route="/sweep")
    if radix:
        app.add_page(mixed, route="/mixed")

        class ThemeState(rx.State):
            accent: str = "red"
            appearance: str = "inherit"

            @rx.event
            def change(self):
                self.accent = "green"
                self.appearance = "dark"

        def bound():
            return rx.el.main(
                rx.ui.theme(
                    probe("bound-probe"),
                    accent_color=ThemeState.accent,  # pyright: ignore [reportArgumentType]
                    gray_color="slate",
                    appearance=ThemeState.appearance,  # pyright: ignore [reportArgumentType]
                    id="bound",
                ),
                Chip.create("bound", id="chip-bound", color_scheme=ThemeState.accent),
                rx.el.button("change", id="change", on_click=ThemeState.change),
            )

        app.add_page(bound, route="/bound")

    config = rx.config.get_config()
    config.plugins = [
        rx.plugins.UIPlugin(theme=rx.ui.Theme(accent_color="indigo", radius="large")),
        rx.plugins.TailwindV4Plugin(),
    ]
    if radix:
        # Its own theme is blue: the theme of rx.ui is the one a page follows.
        config.plugins.append(rx.plugins.RadixThemesPlugin())


def _run(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
    radix: bool,
) -> Generator[AppHarness, None, None]:
    """Run the shared app in dev or prod.

    Args:
        app_harness_env: AppHarness (dev) or AppHarnessProd (prod).
        tmp_path_factory: pytest fixture for creating temporary directories.
        radix: Whether the app also has Radix Themes.

    Yields:
        The running harness.
    """
    name = f"ui_{'mixed' if radix else 'components'}_{app_harness_env.__name__.lower()}"
    with app_harness_env.create(
        root=tmp_path_factory.mktemp(name),
        app_name=name,
        app_source=functools.partial(UIComponentsApp, radix=radix),
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.fixture(scope="module")
def ui_app(
    app_harness_env: type[AppHarness], tmp_path_factory: pytest.TempPathFactory
) -> Generator[AppHarness, None, None]:
    """Run the shared app in dev or prod.

    Args:
        app_harness_env: AppHarness (dev) or AppHarnessProd (prod).
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        The running harness.
    """
    yield from _run(app_harness_env, tmp_path_factory, radix=False)


@pytest.fixture(scope="module")
def mixed_app(
    app_harness_env: type[AppHarness], tmp_path_factory: pytest.TempPathFactory
) -> Generator[AppHarness, None, None]:
    """Run the shared app beside Radix Themes, in dev or prod.

    Args:
        app_harness_env: AppHarness (dev) or AppHarnessProd (prod).
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        The running harness.
    """
    yield from _run(app_harness_env, tmp_path_factory, radix=True)


@pytest.fixture
def prod_app(ui_app: AppHarness) -> AppHarness:
    """Skip a test of the production build when the app runs in dev.

    Args:
        ui_app: The running harness.

    Returns:
        The harness, running a production build.
    """
    if not isinstance(ui_app, AppHarnessProd):
        pytest.skip("only a production build is prerendered and bundled")
    return ui_app


def _computed_styles(
    page: Page, elements: dict[str, dict[str, str]]
) -> dict[str, dict[str, str]]:
    """Read the computed style of elements of the page.

    Args:
        page: A page of the app.
        elements: The properties to read, as the keys of a dict, by element id.

    Returns:
        The properties as the browser computed them, by element id.
    """
    return page.evaluate(
        """(elements) => Object.fromEntries(
            Object.entries(elements).map(([id, properties]) => {
                const style = getComputedStyle(document.getElementById(id));
                return [
                    id,
                    Object.fromEntries(
                        Object.keys(properties).map((name) => [
                            name,
                            style.getPropertyValue(name),
                        ]),
                    ),
                ];
            }),
        )""",
        elements,
    )


def test_box_is_styled_in_cascade_order(ui_app: AppHarness, page: Page):
    """The box is a styled div, between the resets and the utilities."""
    assert ui_app.frontend_url is not None
    page.goto(ui_app.frontend_url)
    # In dev the styles of a page arrive once its module was compiled.
    expect(page.locator("#styled")).to_have_css("padding", "4px")
    assert _computed_styles(page, BOX_STYLES) == BOX_STYLES
    assert page.locator("#plain").evaluate("(box) => box.tagName") == "DIV"


def test_first_paint_is_styled_without_javascript(
    prod_app: AppHarness, browser: Browser
):
    """The prerendered page links the styles and carries the class names."""
    assert prod_app.frontend_url is not None
    context = browser.new_context(java_script_enabled=False)
    try:
        page = context.new_page()
        page.goto(prod_app.frontend_url)
        # Evaluating in the page still works: only its own scripts are off.
        assert _computed_styles(page, BOX_STYLES) == BOX_STYLES
    finally:
        context.close()


def _client_files(harness: AppHarness) -> dict[str, bytes]:
    """Read what the production build serves to the browser.

    Args:
        harness: A harness running a production build.

    Returns:
        The content of every file, by path. The compressed copies are left
        out: each is derived from a file that is included.
    """
    client = harness.app_path / ".web" / "build" / "client"
    return {
        path.relative_to(client).as_posix(): path.read_bytes()
        for path in sorted(client.rglob("*"))
        if path.is_file() and path.suffix != ".gz"
    }


def _styled_url(harness: AppHarness) -> str:
    """Get the address of the styled page.

    Args:
        harness: The running harness.

    Returns:
        The address.
    """
    assert harness.frontend_url is not None
    return harness.frontend_url.rstrip("/") + "/styled/"


def test_styles_follow_the_viewport_the_state_and_the_pointer(
    ui_app: AppHarness, page: Page
):
    """Every kind of style applies where and when it should."""
    page.set_viewport_size({"width": 400, "height": 600})
    page.goto(_styled_url(ui_app))
    # In dev the styles of a page arrive once its module was compiled.
    expect(page.locator("#tone")).to_have_css("padding", "1px")
    assert _computed_styles(page, STYLED) == STYLED

    page.set_viewport_size({"width": 1280, "height": 600})
    expect(page.locator("#responsive")).to_have_css("margin-top", "6px")
    assert _computed_styles(page, STYLED) == STYLED_WIDE

    page.set_viewport_size({"width": 400, "height": 600})
    page.locator("#hover").hover()
    expect(page.locator("#hover")).to_have_css("color", "rgb(255, 0, 0)")

    # The value bound to state is a custom property of the element.
    variable = "(box) => box.style.getPropertyValue('--v0')"
    assert page.locator("#var").evaluate(variable) == "100px"
    page.locator("#change").click()
    expect(page.locator("#var")).to_have_css("width", "200px")
    assert _computed_styles(page, STYLED) == STYLED_CHANGED
    assert page.locator("#var").evaluate(variable) == "200px"


def test_equal_styles_share_one_declaration(ui_app: AppHarness, page: Page):
    """A hundred rows with one style declare it once and carry the same classes."""
    web = ui_app.app_path / ".web"

    def declarations(path: Path) -> list[str]:
        return re.findall(r"^const sx_\w+ = .*$", path.read_text(), re.MULTILINE)

    (route,) = (web / "app" / "routes").glob("*styled*.jsx")
    assert declarations(route) == STYLED_PAGE_DECLARATIONS
    name = ui_app.app_name
    assert declarations(web / "app_components" / name / f"{name}.jsx") == (
        STYLED_MEMO_DECLARATIONS
    )

    page.goto(_styled_url(ui_app))
    rows = page.locator(".row")
    expect(rows).to_have_count(100)
    class_names = set(rows.evaluate_all("(rows) => rows.map((row) => row.className)"))
    assert len(class_names) == 1
    (class_name,) = class_names
    # Its own class, then display, box-sizing, the four sides of the padding and
    # the opacity. While developing, StyleX names the declaration ahead of them.
    assert re.fullmatch(r"row (\w+__sx_e9f4c4c063\.s )?x\w+( x\w+){6}", class_name), (
        class_name
    )
    expect(rows.first).to_have_css("padding", "3px")


def _scripts(harness: AppHarness) -> dict[str, str]:
    """Read the scripts the production build serves to the browser.

    Args:
        harness: A harness running a production build.

    Returns:
        The source of every script, by path.
    """
    return {
        name: content.decode()
        for name, content in _client_files(harness).items()
        if name.endswith(".js")
    }


def test_literal_page_folds_to_class_names(prod_app: AppHarness, page: Page):
    """StyleX leaves a class name string in the page, and none of itself."""
    assert prod_app.frontend_url is not None
    page.goto(prod_app.frontend_url.rstrip("/") + "/literal/")
    box = page.locator("#literal")
    expect(box).to_have_css("padding", "6px")
    class_name = box.get_attribute("class")
    assert class_name is not None
    # Six atomic classes: display, box-sizing and the four sides of the padding.
    assert re.fullmatch(r"x\w+( x\w+){5}", class_name), class_name

    scripts = _scripts(prod_app)
    literal_chunks = [name for name in scripts if name.startswith("assets/_literal_")]
    assert len(literal_chunks) == 1, sorted(scripts)
    # The chunk of the page holds the folded string once, and nothing else
    # that names a class.
    assert re.findall(r"className:`([^`]*)`", scripts[literal_chunks[0]]) == [
        class_name
    ]


def test_no_page_ships_the_stylex_runtime(prod_app: AppHarness):
    """Styles bound to state are compiled away too.

    A value bound to state is a custom property, and a variant bound to state
    indexes a table of folded class names, so no script holds a call into
    StyleX: neither the literal page nor the styled one, whose element holds
    the table.
    """
    scripts = _scripts(prod_app)
    # No script holds the StyleX runtime, whose name minifying leaves alone.
    assert [
        name for name, code in scripts.items() if re.search(r"stylex|styleq", code)
    ] == []
    # A compiled style is only kept where a theme reads it: a theme is
    # declared in a module of its own, so its classes are joined when the
    # page loads. The pages without a theme of their own hold none.
    assert [
        name
        for name, code in scripts.items()
        if name.startswith(("assets/_literal_", "assets/_styled_", "assets/_index"))
        and "$$css" in code
    ] == []
    # The table of the variant, in the chunk that renders the element: the
    # class names of each value. The element is in the module of the
    # components the app keeps apart from their pages, which two pages load.
    tables = [
        (name.split("-")[0], table)
        for name, code in scripts.items()
        for table in re.findall(r"\{__proto__:null,calm:.*?,loud:.*?\}[^}]*\}", code)
    ]
    ((chunk, table),) = tables
    assert chunk == f"assets/{prod_app.app_name}"
    assert re.fullmatch(
        r"\{__proto__:null,calm:\{className:`x\w+ x\w+`\}\.className,"
        r"loud:\{className:`x\w+ x\w+`\}\.className\}",
        table,
    ), table


def test_no_script_ships_emotion(prod_app: AppHarness, page: Page):
    """An app built from rx.ui has no ``css`` prop, so nothing imports Emotion.

    Neither do the parts every app with state gets from Reflex itself: the
    connection indicator and the error boundary are styled by a stylesheet
    React keeps in the document head.
    """
    scripts = _scripts(prod_app)
    assert [
        name
        for name, code in scripts.items()
        if re.search(r"emotion", name + code, re.IGNORECASE)
    ] == []

    page.goto(_styled_url(prod_app))
    expect(page.locator("#var")).to_have_css("width", "100px")
    assert page.locator(".rx-connection-pulser").evaluate(
        """(pulser) => {
            const style = getComputedStyle(pulser);
            return [style.position, style.height];
        }"""
    ) == ["fixed", "0px"]
    assert page.locator("style[data-emotion]").count() == 0


def _digests(files: dict[str, bytes]) -> dict[str, str]:
    """Reduce files to what tells two versions of one apart.

    Args:
        files: The content of every file, by path.

    Returns:
        The digest of every file, by path.
    """
    return {
        name: hashlib.sha256(content).hexdigest() for name, content in files.items()
    }


def _rebuild_literal_page(harness: AppHarness, old: str, new: str) -> dict[str, str]:
    """Change a style of the compiled literal page and build again.

    Args:
        harness: A harness running a production build.
        old: The style as the page declares it.
        new: The style to declare instead.

    Returns:
        The digest of every file of the new build, by path.
    """
    routes = harness.app_path / ".web" / "app" / "routes"
    (page,) = routes.glob("*literal*.jsx")
    source = page.read_text()
    assert source.count(old) == 1, source
    page.write_text(source.replace(old, new))
    with chdir(harness.app_path):
        build.build()
    return _digests(_client_files(harness))


def test_changed_style_renames_every_changed_file(prod_app: AppHarness, tmp_path: Path):
    """A browser never keeps a stale file under the name of a new one.

    StyleX renames the stylesheet after the chunks were named, and writes the
    new name into the chunk that links it.
    """
    static = prod_app.app_path / ".web" / "build" / "client"
    # Outside the web directory: a build removes its output, and Tailwind
    # reads class names from every file beside it.
    kept = tmp_path / "client"
    shutil.copytree(static, kept)
    before = _digests(_client_files(prod_app))
    try:
        after = _rebuild_literal_page(prod_app, LITERAL_STYLE, CHANGED_STYLE)
        restored = _rebuild_literal_page(prod_app, CHANGED_STYLE, LITERAL_STYLE)
    finally:
        # The other tests of the module read the build the harness serves.
        shutil.rmtree(static)
        shutil.move(kept, static)

    def named(digests: dict[str, str]) -> dict[str, str]:
        # A document is addressed by its route and is not cached by its name.
        return {
            name: digest
            for name, digest in digests.items()
            if not name.endswith(".html")
        }

    before, after, restored = named(before), named(after), named(restored)
    changed_in_place = sorted(
        name for name, digest in after.items() if before.get(name, digest) != digest
    )
    assert changed_in_place == []
    renamed = sorted(Path(name).name.split("-")[0] for name in after.keys() - before)
    assert renamed == [
        "__reflex_global_styles",
        "_literal_._index",
        "manifest",
        "root",
    ]
    # The same styles build the same files: a name is a function of content.
    assert restored == before


# What each probe of the theme page reads, and through which token.
PROBE_PROPERTIES = (
    "color",
    "background-color",
    "border-top-left-radius",
    "padding-top",
    "font-size",
)

# The probes under the theme of the app, indigo and large, in each color mode.
APP_PROBE = {
    mode: {
        "color": INDIGO_11[mode],
        "background-color": SLATE_2[mode],
        "border-top-left-radius": "9px",
        "padding-top": "16px",
        "font-size": "14px",
    }
    for mode in ("light", "dark")
}

# The probes under the nested theme: red, full, 110% and always dark.
NESTED_PROBE = {
    "color": RED_11["dark"],
    # The gray is the one around the theme, as an accent does not set it.
    "background-color": SLATE_2["dark"],
    "border-top-left-radius": "9.9px",
    "padding-top": "17.6px",
    "font-size": "15.4px",
}


def _probes(page: Page) -> dict[str, dict[str, str]]:
    """Read the probes of the theme page.

    Args:
        page: A page showing the theme page of the app.

    Returns:
        The properties in PROBE_PROPERTIES as the browser computed them, by
        probe id.
    """
    return page.evaluate(
        """(properties) => Object.fromEntries(
            [...document.querySelectorAll('[id$="-probe"]')].map((probe) => {
                const style = getComputedStyle(probe);
                return [
                    probe.id,
                    Object.fromEntries(
                        properties.map((name) => [name, style.getPropertyValue(name)]),
                    ),
                ];
            }),
        )""",
        list(PROBE_PROPERTIES),
    )


def _goto_theme_page(harness: AppHarness, page: Page) -> None:
    """Show the theme page, styled.

    Args:
        harness: The running harness.
        page: The page to navigate.
    """
    assert harness.frontend_url is not None
    page.goto(harness.frontend_url.rstrip("/") + "/theme/")
    # In dev the styles of a page arrive once its module was compiled.
    expect(page.locator("#nested-probe")).to_have_css("font-size", "15.4px")


def test_nested_theme_overrides_its_subtree_only(ui_app: AppHarness, page: Page):
    """The theme of the plugin is around the page, and a nested one inside it."""
    _goto_theme_page(ui_app, page)
    page.locator("#popover").evaluate("(popover) => popover.showPopover()")
    assert _probes(page) == {
        "root-probe": APP_PROBE["light"],
        "nested-probe": NESTED_PROBE,
        # The browser renders a popover in the top layer, outside the theme
        # element: it inherits from where it is declared all the same.
        "popover-probe": NESTED_PROBE,
        "after-probe": APP_PROBE["light"],
    }
    themes = page.evaluate(
        """() => [...document.querySelectorAll(".reflex-ui-theme")].map((theme) => {
            const style = getComputedStyle(theme);
            const parent = theme.parentElement;
            return [
                theme.id,
                style.colorScheme,
                style.backgroundColor,
                style.minHeight,
                parent.classList.contains("dark"),
                getComputedStyle(parent).display,
            ];
        })"""
    )
    # Text selected inside a theme has the color of its focus ring.
    selection = page.evaluate(
        """() => ["root-probe", "nested-probe"].map((id) => {
            const probe = document.getElementById(id);
            const reference = probe.appendChild(document.createElement("i"));
            reference.style.color = "var(--focus-a5)";
            return [
                getComputedStyle(probe, "::selection").backgroundColor,
                getComputedStyle(reference).color,
            ];
        })"""
    )
    # Indigo a5 of the light scale, and red a5 of the dark one.
    assert selection == [
        ["rgba(0, 68, 255, 0.176)", "rgba(0, 68, 255, 0.176)"],
        ["rgba(255, 32, 71, 0.337)", "rgba(255, 32, 71, 0.337)"],
    ]
    viewport = page.viewport_size
    assert viewport is not None
    assert themes == [
        # The background of a light theme is white, and of a dark one its
        # darkest gray: slate here. Only the theme of the app fills the page.
        ["", "light", "rgb(255, 255, 255)", f"{viewport['height']}px", False, "block"],
        # The class of an appearance is on an element without a box.
        ["nested", "dark", "rgb(17, 17, 19)", "0px", True, "contents"],
    ]


def test_color_mode_toggle_flips_the_palette(ui_app: AppHarness, page: Page):
    """A color is one value for both modes, chosen by the class of the page."""
    _goto_theme_page(ui_app, page)
    html = page.locator("html")
    expect(html).to_have_class("light")
    assert _probes(page)["root-probe"] == APP_PROBE["light"]
    page.locator("#toggle").click()
    expect(html).to_have_class("dark")
    assert _probes(page) == {
        "root-probe": APP_PROBE["dark"],
        # A theme with an appearance of its own keeps it.
        "nested-probe": NESTED_PROBE,
        "popover-probe": NESTED_PROBE,
        "after-probe": APP_PROBE["dark"],
    }
    page.locator("#toggle").click()
    expect(html).to_have_class("light")
    assert _probes(page)["root-probe"] == APP_PROBE["light"]


def test_prerendered_theme_page_is_themed_without_javascript(
    prod_app: AppHarness, browser: Browser
):
    """The theme is class names in the document, and needs no script."""
    assert prod_app.frontend_url is not None
    context = browser.new_context(java_script_enabled=False)
    try:
        page = context.new_page()
        page.goto(prod_app.frontend_url.rstrip("/") + "/theme/")
        # Nothing has set the class of a color mode: the page is light.
        assert page.locator("html").get_attribute("class") is None
        assert _probes(page) == {
            "root-probe": APP_PROBE["light"],
            "nested-probe": NESTED_PROBE,
            "popover-probe": NESTED_PROBE,
            "after-probe": APP_PROBE["light"],
        }
    finally:
        context.close()


# The themes of the sweep page, as the app builds them.
SWEEP_DEFAULTS = {
    "accent_color": "indigo",
    "gray_color": "auto",
    "radius": "medium",
    "scaling": "100%",
    "panel_background": "translucent",
}
SWEEP_CONFIGS: list[dict[str, str]] = [
    {**SWEEP_DEFAULTS, **variation}
    for variation in (
        *(
            {"accent_color": accent, "appearance": appearance}
            for accent in _radix_tokens.ACCENT_THEMES
            for appearance in ("light", "dark")
        ),
        *(
            {"gray_color": gray, "appearance": appearance}
            for gray in _radix_tokens.GRAY_THEMES
            for appearance in ("light", "dark")
        ),
        *({"radius": radius} for radius in _radix_tokens.RADIUS_THEMES),
        *({"scaling": scaling} for scaling in _radix_tokens.SCALING_THEMES),
        *(
            {"panel_background": panel}
            for panel in _radix_tokens.PANEL_BACKGROUND_THEMES
        ),
    )
]

# Every custom property Radix Themes defines: the modules add two of their
# own, through which a theme switches the background of its panels.
SWEEP_NAMES = [
    name
    for _, names in _radix_tokens.VAR_GROUPS.values()
    for name in names
    if name not in ("--panel-solid", "--color-panel-if-solid")
]

READ_SWEEP = """async ([scripts, names, prefix]) => {
    const { labels, mount, read } = await import(scripts + "probe.js");
    const container = document.createElement("div");
    const probes = mount(container, names);
    const themes = [...document.querySelectorAll(`[data-sweep][id^="${prefix}-"]`)];
    return {
        labels: labels(names),
        themes: themes.map((theme) => {
            theme.append(container);
            return [theme.id, theme.dataset.sweep, read(probes, theme)];
        }),
    };
}"""


def _serve_sweep_script(route: Route) -> None:
    """Answer a request for a script of the token sweep with the file.

    Args:
        route: The intercepted request.
    """
    name = route.request.url.rsplit("/", 1)[1]
    route.fulfill(path=SWEEP_HARNESS / name, content_type="text/javascript")


def _read_sweep(harness: AppHarness, page: Page, prefix: str) -> dict[str, Any]:
    """Read every custom property under every theme of the sweep page.

    Args:
        harness: The running harness.
        page: The page to navigate.
        prefix: What the ids of the themes to read start with: ``ui`` for the
            ones of rx.ui, ``radix`` for the ones of Radix Themes.

    Returns:
        The names of the values, and the id, the options and the values of
        each theme.
    """
    assert harness.frontend_url is not None
    page.route(f"**{SWEEP_SCRIPTS}*", _serve_sweep_script)
    page.goto(harness.frontend_url.rstrip("/") + "/sweep/")
    # In dev the styles of a page arrive once its module was compiled.
    expect(page.locator("#ui-0")).to_have_css("overflow-wrap", "break-word")
    return page.evaluate(READ_SWEEP, [SWEEP_SCRIPTS, SWEEP_NAMES, prefix])


def _sweep_differences(
    reference: dict[str, Any], ours: dict[str, Any]
) -> list[tuple[str, str, str, str]]:
    """List where two readings of the sweep page differ.

    Args:
        reference: The reading under the themes of Radix Themes.
        ours: A reading under the themes of rx.ui.

    Returns:
        The options, the name of the value, the value under Radix Themes and
        the value under rx.ui, for each difference.
    """
    return [
        (config, label, expected, value)
        for (_, config, expected_values), (_, _, values) in zip(
            reference["themes"], ours["themes"], strict=True
        )
        for label, expected, value in zip(
            reference["labels"], expected_values, values, strict=True
        )
        if expected != value
    ]


def test_tokens_resolve_as_under_radix_themes(
    ui_app: AppHarness, mixed_app: AppHarness, page: Page
):
    """Every custom property has the value Radix Themes gives it.

    The same themes are read under ``rx.theme`` and under ``rx.ui.theme`` on
    one page, and under ``rx.ui.theme`` in the app without Radix Themes. What
    may differ is listed with its reason in the exceptions of the javascript
    package, which the script that reads the values applies.
    """
    radix = _read_sweep(mixed_app, page, "radix")
    mixed = _read_sweep(mixed_app, page, "ui")
    alone = _read_sweep(ui_app, page, "ui")

    configs = [json.dumps(config) for config in SWEEP_CONFIGS]
    assert len(configs) == 76
    for reading, prefix in ((radix, "radix"), (mixed, "ui"), (alone, "ui")):
        assert [theme[:2] for theme in reading["themes"]] == [
            [f"{prefix}-{index}", config] for index, config in enumerate(configs)
        ]
    assert len(radix["labels"]) == 1068 + 11
    # A value neither side defines would compare equal: Radix defines them all.
    assert [
        (config, label, value)
        for _, config, values in radix["themes"]
        for label, value in zip(radix["labels"], values, strict=True)
        if value.startswith("INVALID")
    ] == []
    assert _sweep_differences(radix, mixed) == []
    assert _sweep_differences(radix, alone) == []


def test_radix_components_follow_the_rx_ui_theme(mixed_app: AppHarness, page: Page):
    """On a page with both, a Radix button and an rx.ui box show one palette."""
    assert mixed_app.frontend_url is not None
    page.goto(mixed_app.frontend_url.rstrip("/") + "/mixed/")
    expect(page.locator("#ui-box")).to_have_css("color", INDIGO_11["light"])
    accents = page.evaluate(
        """() => ["radix-button", "ui-box"].map((id) =>
            getComputedStyle(document.getElementById(id)).getPropertyValue("--accent-9"),
        )"""
    )
    # Indigo, the accent of the rx.ui theme, and not the blue of the Radix one.
    assert accents == ["#3e63dd", "#3e63dd"]
    expect(page.locator("#radix-button")).to_have_css(
        "background-color", "rgb(62, 99, 221)"
    )

    # A nested rx.ui theme is to the Radix components inside it what a nested
    # Radix theme is: its accent, and the dark scale of a color of their own.
    def read(theme: str) -> list[list[str]]:
        return page.locator(f"#{theme}").evaluate(
            """(theme) => [theme, ...theme.querySelectorAll("button")].map((element) => {
                const style = getComputedStyle(element);
                return [style.backgroundColor, style.color];
            })"""
        )

    in_ui_theme = read("ui-dark")
    assert in_ui_theme == [
        # The theme itself, its red button and its soft green button: slate 1
        # and 12, red 9, then green a3 and a11, all of the dark scales.
        ["rgb(17, 17, 19)", "rgb(237, 238, 240)"],
        ["rgb(229, 72, 77)", "rgb(255, 255, 255)"],
        ["rgba(34, 255, 153, 0.118)", "rgba(70, 254, 165, 0.83)"],
    ]
    assert in_ui_theme == read("radix-dark")


def test_theme_bound_to_state_follows_it(mixed_app: AppHarness, page: Page):
    """Every accent is on the page, and the browser applies the one in state."""
    assert mixed_app.frontend_url is not None
    page.goto(mixed_app.frontend_url.rstrip("/") + "/bound/")
    probe = page.locator("#bound-probe")
    expect(probe).to_have_css("color", RED_11["light"])

    def read() -> list[str]:
        return page.locator("#bound").evaluate(
            """(theme) => [
                getComputedStyle(theme.querySelector("#bound-probe")).backgroundColor,
                getComputedStyle(theme).colorScheme,
                getComputedStyle(theme).backgroundColor,
                [...theme.parentElement.classList].filter((name) =>
                    ["inherit", "light", "dark"].includes(name),
                ).join(" "),
                getComputedStyle(theme.parentElement).display,
            ]"""
        )

    # The appearance of the page, and no background of its own.
    assert read() == [
        SLATE_2["light"],
        "light",
        "rgba(0, 0, 0, 0)",
        "inherit",
        "contents",
    ]
    # A component with a color bound to the same state: red 9.
    chip = page.locator("#chip-bound")
    expect(chip).to_have_css("background-color", "rgb(229, 72, 77)")
    page.locator("#change").click()
    expect(probe).to_have_css("color", "rgb(61, 214, 140)")
    # Green 9, and step 8 of the focus ring that follows it.
    expect(chip).to_have_css("background-color", "rgb(48, 164, 108)")
    expect(chip).to_have_css("outline-color", "rgb(91, 185, 139)")
    assert read() == [SLATE_2["dark"], "dark", "rgb(17, 17, 19)", "dark", "contents"]


def test_color_scheme_is_the_accent_of_one_element(ui_app: AppHarness, page: Page):
    """A component with a color follows it, and the focus ring with it."""
    _goto_theme_page(ui_app, page)
    # Step 9 of the accent, then step 8 of the focus ring. The theme is
    # indigo, and its gray is slate: a gray component keeps the indigo focus.
    assert page.evaluate(
        """() => Object.fromEntries(
            [...document.querySelectorAll('[id^="chip-"]')].map((chip) => {
                const style = getComputedStyle(chip);
                return [chip.id, [style.backgroundColor, style.outlineColor]];
            }),
        )"""
    ) == {
        "chip-theme": ["rgb(62, 99, 221)", "rgb(141, 164, 239)"],
        "chip-red": ["rgb(229, 72, 77)", "rgb(235, 142, 144)"],
        "chip-gray": ["rgb(139, 141, 152)", "rgb(141, 164, 239)"],
    }
