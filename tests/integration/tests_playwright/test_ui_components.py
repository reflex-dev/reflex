"""The rx.ui components in a real app, in dev and prod.

One app is shared by every test of the components: add a page or an element to
``UIComponentsApp`` rather than a new app.
"""

import hashlib
import re
import shutil
from collections.abc import Generator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect

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


def UIComponentsApp():
    """An app with a page for each thing the rx.ui tests look at."""
    from pathlib import Path
    from typing import ClassVar, Literal

    from reflex_components_ui.base import UIComponent
    from reflex_components_ui.style import ComponentStyles

    import reflex as rx

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

    config = rx.config.get_config()
    config.plugins = [rx.plugins.UIPlugin(), rx.plugins.TailwindV4Plugin()]


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
    name = f"ui_components_{app_harness_env.__name__.lower()}"
    with app_harness_env.create(
        root=tmp_path_factory.mktemp(name),
        app_name=name,
        app_source=UIComponentsApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


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
    StyleX or a style object it reads at runtime: neither the literal page nor
    the styled one, whose chunk holds the table.
    """
    scripts = _scripts(prod_app)
    assert [
        name for name, code in scripts.items() if re.search(r"stylex|\$\$css", code)
    ] == []
    styled_chunks = [name for name in scripts if name.startswith("assets/_styled_")]
    assert len(styled_chunks) == 1, sorted(scripts)
    # The table of the variant, in the chunk that renders the element: the
    # class names of each value.
    (table,) = re.findall(
        r"\{__proto__:null,calm:.*?,loud:.*?\}[^}]*\}", scripts[styled_chunks[0]]
    )
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
