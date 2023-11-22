"""Integration test for markdown component with component_map."""

from __future__ import annotations

from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import DEFAULT_TIMEOUT, AppHarness, WebDriver


def MarkdownApp():
    """App using markdown component with custom component_map."""
    import reflex as rx

    python_code: str = """import reflex as rx

        class State(rx.State):
            '''The app state.'''
            pass"""

    markdown_code: str = f"""```python\n{python_code}\n```"""

    class State(rx.State):
        code_snippet: str = python_code
        md_snippet: str = markdown_code

    def custom_code_block(*children, **props):
        return rx.code_block(*children, theme="atom-dark", **props)

    def custom_code_block_can_copy(*children, **props):
        return rx.code_block(*children, can_copy=True, theme="atom-dark", **props)

    def case_box(child, case_name, **props):
        return rx.box(
            child,
            case_name.replace("-", " "),
            id=case_name,
            margin="1em",
            **props,
        )

    def index() -> rx.Component:
        return rx.flex(
            rx.input(
                id="token", value=State.router.session.client_token, read_only=True
            ),
            case_box(
                rx.markdown(
                    markdown_code,
                    component_map={
                        "codeblock": custom_code_block,
                    },
                ),
                "markdown-custom-code-block",
            ),
            case_box(
                rx.markdown(
                    State.md_snippet,
                    component_map={
                        "codeblock": custom_code_block,
                    },
                ),
                "markdown-custom-code-block-state",
            ),
            case_box(
                rx.markdown(
                    markdown_code,
                    component_map={
                        "codeblock": custom_code_block_can_copy,
                    },
                ),
                "markdown-custom-code-block-can-copy",
            ),
            case_box(
                rx.markdown(
                    State.md_snippet,
                    component_map={
                        "codeblock": custom_code_block_can_copy,
                    },
                ),
                "markdown-custom-code-block-can-copy-state",
            ),
            case_box(
                custom_code_block(python_code, language="python"),
                "custom-code-block",
            ),
            case_box(
                custom_code_block(State.code_snippet, language="python"),
                "custom-code-block-state",
            ),
            case_box(
                custom_code_block_can_copy(python_code, language="python"),
                "custom-code-block-can-copy",
            ),
            case_box(
                custom_code_block_can_copy(State.code_snippet, language="python"),
                "custom-code-block-can-copy-state",
            ),
            flex_wrap="wrap",
        )

    app = rx.App(state=State)
    app.add_page(index)
    app.compile()


@pytest.fixture(scope="session")
def markdown_app(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start MarkdownApp at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp(f"markdown_app"),
        app_source=MarkdownApp,  # type: ignore
    ) as harness:
        yield harness


@pytest.fixture
def driver(markdown_app: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the markdown_app app.

    Args:
        markdown_app: harness for BackgroundTask app

    Yields:
        WebDriver instance.
    """
    assert markdown_app.app_instance is not None, "app is not running"
    driver = markdown_app.frontend()
    try:
        yield driver
    finally:
        driver.quit()


@pytest.fixture()
def token(markdown_app: AppHarness, driver: WebDriver) -> str:
    """Get a function that returns the active token.

    Args:
        markdown_app: harness for MarkdownApp.
        driver: WebDriver instance.

    Returns:
        The token for the connected client
    """
    assert markdown_app.app_instance is not None
    token_input = driver.find_element(By.ID, "token")
    assert token_input

    # wait for the backend connection to send the token
    token = markdown_app.poll_for_value(token_input, timeout=DEFAULT_TIMEOUT * 2)
    assert token is not None

    return token


@pytest.mark.asyncio
async def test_markdown_app(
    markdown_app: AppHarness,
    driver: WebDriver,
    token: str,
):
    """Test that markdown component renders correctly.

    Args:
        markdown_app: harness for MarkdownApp.
        driver: WebDriver instance.
        token: The token for the connected client.
    """
    state = await markdown_app.get_state(token)
    exp_snippet = state.code_snippet.strip()
    n_cases = 8
    markdown_cases = 4  # markdown cases seem to insert an extra <pre> tag

    pre_elements = driver.find_elements(By.TAG_NAME, "pre")
    assert len(pre_elements) == n_cases + markdown_cases
    for pre in pre_elements:
        assert pre.text.strip() == exp_snippet

    # Check that the "can_copy" button actually works.
    n_copy_cases = 4
    copy_buttons = driver.find_elements(By.TAG_NAME, "button")
    assert len(copy_buttons) == n_copy_cases
    driver.execute_script(
        "window.clipboard_data = ''; window.navigator.clipboard.writeText = (text) => window.clipboard_data = text;"
    )
    for copy_button in copy_buttons:
        assert driver.execute_script("return window.clipboard_data") == ""
        copy_button.click()
        assert (
            driver.execute_script("return window.clipboard_data").strip() == exp_snippet
        )
        driver.execute_script("window.clipboard_data = ''")
