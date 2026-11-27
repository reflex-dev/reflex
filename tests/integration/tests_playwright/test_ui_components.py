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
LITERAL_STYLE = '"padding": "6px"'
CHANGED_STYLE = '"padding": "7px"'


def UIComponentsApp():
    """An app with a page for each thing the rx.ui tests look at."""
    from pathlib import Path

    import reflex as rx

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

    assets = Path.cwd() / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "unlayered.css").write_text(".unlayered { padding: 2px }")

    app = rx.App(stylesheets=["unlayered.css"], enable_state=False)
    app.add_page(index)
    app.add_page(literal, route="/literal")

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


def _computed_styles(page: Page) -> dict[str, dict[str, str]]:
    """Read the computed style of every box of the index page.

    Args:
        page: A page showing the index of the app.

    Returns:
        The properties in BOX_STYLES as the browser computed them, by box id.
    """
    return page.evaluate(
        """(boxes) => Object.fromEntries(
            Object.entries(boxes).map(([id, properties]) => {
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
        BOX_STYLES,
    )


def test_box_is_styled_in_cascade_order(ui_app: AppHarness, page: Page):
    """The box is a styled div, between the resets and the utilities."""
    assert ui_app.frontend_url is not None
    page.goto(ui_app.frontend_url)
    # In dev the styles of a page arrive once its module was compiled.
    expect(page.locator("#styled")).to_have_css("padding", "4px")
    assert _computed_styles(page) == BOX_STYLES
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
        assert _computed_styles(page) == BOX_STYLES
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


def test_literal_page_folds_to_class_names(prod_app: AppHarness, page: Page):
    """StyleX leaves a class name string in the page, and none of itself."""
    assert prod_app.frontend_url is not None
    page.goto(prod_app.frontend_url.rstrip("/") + "/literal/")
    box = page.locator("#literal")
    expect(box).to_have_css("padding", "6px")
    class_name = box.get_attribute("class")
    assert class_name is not None
    # Three atomic classes: display, box-sizing and padding.
    assert re.fullmatch(r"x\w+ x\w+ x\w+", class_name), class_name

    scripts = {
        name: content.decode()
        for name, content in _client_files(prod_app).items()
        if name.endswith(".js")
    }
    literal_chunks = [name for name in scripts if name.startswith("assets/_literal_")]
    assert len(literal_chunks) == 1, sorted(scripts)
    # Every class name the chunk of the page sets is the folded string.
    assert re.findall(r"className:`([^`]*)`", scripts[literal_chunks[0]]) == [
        class_name
    ]
    # No script holds a call into StyleX or a style object it reads at runtime.
    assert [
        name for name, code in scripts.items() if re.search(r"stylex|\$\$css", code)
    ] == []


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
