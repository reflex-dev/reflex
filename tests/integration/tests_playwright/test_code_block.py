"""Integration tests for the code block component."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

PRIMARY_CODE = "def add(x, y):\n    return x + y"
LONG_LINE_CODE = (
    "message = 'this line is intentionally long so wrap_long_lines changes "
    "the rendered whitespace behavior'"
)
DEFAULT_COPY_CODE = "print('copied from default button')"
CUSTOM_COPY_CODE = "print('copied from custom button')"


def CodeBlockApp():
    """App exercising code block rendering options."""
    import reflex as rx

    primary_code = "def add(x, y):\n    return x + y"
    long_line_code = (
        "message = 'this line is intentionally long so wrap_long_lines changes "
        "the rendered whitespace behavior'"
    )
    default_copy_code = "print('copied from default button')"
    custom_copy_code = "print('copied from custom button')"

    def index():
        return rx.vstack(
            rx.box(
                rx.code_block(
                    primary_code,
                    language="python",
                    theme=rx.code_block.themes.one_light,
                    show_line_numbers=True,
                    starting_line_number=41,
                    custom_style={
                        "background_color": "rgb(17, 34, 51)",
                        "border_radius": "6px",
                        "padding": "12px",
                    },
                    code_tag_props={
                        "data-testid": "primary-code-tag",
                        "data-code-prop": "tag-prop",
                    },
                ),
                id="primary-code-block",
            ),
            rx.box(
                rx.code_block(
                    long_line_code,
                    language="python",
                    wrap_long_lines=True,
                ),
                id="wrapped-code-block",
                width="220px",
            ),
            rx.box(
                rx.code_block(
                    "const answer = 42;",
                    language="javascript",
                    theme=rx.code_block.themes.one_dark,
                ),
                id="theme-code-block",
            ),
            rx.box(
                rx.code_block(default_copy_code, language="python", can_copy=True),
                id="default-copy-block",
            ),
            rx.box(
                rx.code_block(
                    custom_copy_code,
                    language="python",
                    can_copy=True,
                    copy_button=rx.button(
                        "Copy custom",
                        id="custom-copy",
                        on_click=rx.set_clipboard(custom_copy_code),
                    ),
                ),
                id="custom-copy-block",
            ),
            align_items="stretch",
            spacing="4",
            width="480px",
        )

    app = rx.App(enable_state=False)
    app.add_page(index)


@pytest.fixture(scope="module")
def code_block_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start the code block test app.

    Args:
        tmp_path_factory: Pytest tmp path factory.

    Yields:
        The running app harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("code_block_app"),
        app_source=CodeBlockApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def _goto_code_block_app(code_block_app: AppHarness, page: Page) -> None:
    """Navigate to the code block test app.

    Args:
        code_block_app: Running code block app harness.
        page: Playwright page.
    """
    assert code_block_app.frontend_url is not None
    page.goto(code_block_app.frontend_url)
    expect(page.locator("#primary-code-block pre")).to_be_visible()


def test_code_block_renders_code_language_line_numbers_and_code_tag_props(
    code_block_app: AppHarness, page: Page
) -> None:
    """The primary code block renders code text and structural props.

    Args:
        code_block_app: Running code block app harness.
        page: Playwright page.
    """
    _goto_code_block_app(code_block_app, page)

    code_tag = page.get_by_test_id("primary-code-tag")
    expect(code_tag).to_contain_text("def add")
    expect(code_tag).to_contain_text("return x + y")
    expect(code_tag).to_have_attribute("data-code-prop", "tag-prop")

    assert code_tag.evaluate(
        """el => Array.from(el.querySelectorAll('span'))
            .some(span => span.textContent === 'def')"""
    )

    line_numbers = page.locator("#primary-code-block .linenumber")
    expect(line_numbers).to_have_count(2)
    assert line_numbers.all_inner_texts() == ["41", "42"]


def test_code_block_applies_custom_style_and_theme(
    code_block_app: AppHarness, page: Page
) -> None:
    """Code block styles from custom_style and theme reach the DOM.

    Args:
        code_block_app: Running code block app harness.
        page: Playwright page.
    """
    _goto_code_block_app(code_block_app, page)

    primary = page.locator("#primary-code-block pre")
    expect(primary).to_have_css("background-color", "rgb(17, 34, 51)")
    expect(primary).to_have_css("border-radius", "6px")

    themed = page.locator("#theme-code-block pre")
    expect(themed).to_have_css("background-color", "rgb(40, 44, 52)")


def test_code_block_wraps_long_lines(code_block_app: AppHarness, page: Page) -> None:
    """wrap_long_lines changes rendered whitespace behavior.

    Args:
        code_block_app: Running code block app harness.
        page: Playwright page.
    """
    _goto_code_block_app(code_block_app, page)

    wrapped = page.locator("#wrapped-code-block")
    expect(wrapped.locator("code")).to_contain_text("this line is intentionally long")
    assert wrapped.locator("pre").evaluate("el => el.scrollWidth <= el.clientWidth + 1")


def test_code_block_default_copy_button(code_block_app: AppHarness, page: Page) -> None:
    """The built-in copy button writes the code text to the clipboard.

    Args:
        code_block_app: Running code block app harness.
        page: Playwright page.
    """
    assert code_block_app.frontend_url is not None
    page.context.grant_permissions(
        ["clipboard-read", "clipboard-write"], origin=code_block_app.frontend_url
    )
    _goto_code_block_app(code_block_app, page)

    page.evaluate("navigator.clipboard.writeText('')")
    page.locator("#default-copy-block button").click()
    page.wait_for_function(
        "expected => navigator.clipboard.readText().then(text => text === expected)",
        arg=DEFAULT_COPY_CODE,
    )


def test_code_block_custom_copy_button(code_block_app: AppHarness, page: Page) -> None:
    """A custom copy button replaces the default and can run its own event.

    Args:
        code_block_app: Running code block app harness.
        page: Playwright page.
    """
    assert code_block_app.frontend_url is not None
    page.context.grant_permissions(
        ["clipboard-read", "clipboard-write"], origin=code_block_app.frontend_url
    )
    _goto_code_block_app(code_block_app, page)

    custom_block = page.locator("#custom-copy-block")
    expect(custom_block.get_by_role("button")).to_have_text("Copy custom")
    expect(custom_block.locator("svg.lucide-copy")).to_have_count(0)

    page.evaluate("navigator.clipboard.writeText('')")
    page.locator("#custom-copy").click()
    page.wait_for_function(
        "expected => navigator.clipboard.readText().then(text => text === expected)",
        arg=CUSTOM_COPY_CODE,
    )
