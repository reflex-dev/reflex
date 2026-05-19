"""Integration tests for auto-memoization edge cases.

These exercise components whose memoization needs special care:

- Snapshot boundaries (``recursive=False``) such as ``AccordionTrigger`` whose
  state-dependent logic lives in a descendant. Without the snapshot wrapper
  the cond's state read leaks into the page module and the trigger fails to
  update on state transitions.
- HTML elements with constrained content models (``<title>``, ``<meta>``,
  ``<style>``, ``<script>``). Independent memoization of a stateful ``Bare``
  child renders ``jsx("title", {}, jsx(Bare_xxx, {}))`` — React stringifies
  the component child as ``[object Object]`` (or refuses to render at all
  for void elements). Snapshot-wrapping keeps the Bare a text interpolation
  inside the parent's body.
- Third-party components whose ``children`` prop asserts a string type
  (``react-markdown``). Same failure mode as constrained HTML elements:
  without snapshot-wrapping, ``rx.markdown(State.var)`` compiles to
  ``jsx(ReactMarkdown, {...}, jsx(Bare_xxx, {}))``, which raises
  "Unexpected value [object Object] for children prop, expected string"
  at render time.

Test design notes:
- The page title is supplied via ``app.add_page(..., title=MemoState.title_marker)``
  so the dynamic value flows through the standard React Router metadata path
  and shows up in ``document.title``.
- Style content is matched on a unique marker substring rather than common
  selectors like ``body`` (which conflicts with Emotion/Sonner stylesheets).
- ``<textarea>``'s runtime value semantics belong to React (children are
  initial-value-only); the no-Bare-component-child invariant is verified by
  the unit tests instead.
"""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def MemoEdgeCasesApp():
    """App exercising memoization edge cases."""
    import reflex as rx

    class MemoState(rx.State):
        is_open: bool = False
        title_marker: str = "memo-title-home"
        css_marker: str = "memo-css-light"
        counter: int = 0
        markdown_source: str = "Initial **memo-md-home** text"

        @rx.event
        def toggle_open(self):
            self.is_open = not self.is_open

        @rx.event
        def set_title_about(self):
            self.title_marker = "memo-title-about"

        @rx.event
        def set_css_dark(self):
            self.css_marker = "memo-css-dark"

        @rx.event
        def bump(self):
            self.counter = self.counter + 1

        @rx.event
        def set_markdown_alt(self):
            self.markdown_source = "Updated **memo-md-away** text"

    def index():
        return rx.box(
            rx.el.style("body { --memo-marker: " + MemoState.css_marker + "; }"),
            rx.box(
                rx.button("toggle", on_click=MemoState.toggle_open, id="toggle"),
                rx.button("title", on_click=MemoState.set_title_about, id="set-title"),
                rx.button("css", on_click=MemoState.set_css_dark, id="set-css"),
                rx.button("bump", on_click=MemoState.bump, id="bump"),
                rx.button("md", on_click=MemoState.set_markdown_alt, id="set-markdown"),
            ),
            rx.accordion.root(
                rx.accordion.item(
                    header=rx.accordion.header(
                        rx.accordion.trigger(
                            rx.cond(
                                MemoState.is_open,
                                rx.text("Hide", id="trigger-hide"),
                                rx.text("Show", id="trigger-show"),
                            ),
                            id="accordion-trigger",
                        ),
                    ),
                    content=rx.accordion.content(rx.text("body")),
                    value="item-1",
                ),
            ),
            rx.text(MemoState.counter, id="counter"),
            # Mirrors the bug-report repro: a static-source markdown next to
            # a Var-source markdown inside the same parent. Pre-fix, the
            # Var-source sibling crashed react-markdown with
            # "Unexpected value [object Object] for children prop".
            rx.vstack(
                rx.markdown("This *is* **working**", id="md-static"),
                rx.markdown(MemoState.markdown_source, id="md-host"),
                id="md-section",
            ),
        )

    app = rx.App()
    app.add_page(index, title=MemoState.title_marker)


@pytest.fixture(scope="module")
def memo_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Run the memoization edge-cases app under an AppHarness.

    Args:
        tmp_path_factory: Pytest fixture for creating temporary directories.

    Yields:
        The running harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("memo_edge_cases"),
        app_source=MemoEdgeCasesApp,
    ) as harness:
        yield harness


def test_accordion_trigger_with_stateful_cond_updates(
    memo_app: AppHarness, page: Page
) -> None:
    """AccordionTrigger holding a stateful cond updates on state changes.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)

    expect(page.locator("#trigger-show")).to_have_text("Show")
    expect(page.locator("#trigger-hide")).to_have_count(0)

    page.click("#toggle")
    expect(page.locator("#trigger-hide")).to_have_text("Hide")
    expect(page.locator("#trigger-show")).to_have_count(0)

    # Bumping an unrelated counter must not desync the trigger render.
    page.click("#bump")
    expect(page.locator("#counter")).to_have_text("1")
    expect(page.locator("#trigger-hide")).to_have_text("Hide")

    page.click("#toggle")
    expect(page.locator("#trigger-show")).to_have_text("Show")


def _document_contains_style(page: Page, marker: str) -> bool:
    """Whether any ``<style>`` element's text content contains ``marker``.

    ``<style>`` content is not "visible" text, so the Locator ``has_text``
    filter skips it. Inspect text content via JS instead.

    Args:
        page: Playwright page.
        marker: Substring to look for in style element text content.

    Returns:
        True if any ``<style>`` element's textContent contains the marker.
    """
    return page.evaluate(
        """(marker) => {
            const els = document.querySelectorAll('style');
            return Array.from(els).some(el => (el.textContent || '').includes(marker));
        }""",
        marker,
    )


def test_page_title_updates_with_state(memo_app: AppHarness, page: Page) -> None:
    """The page title (passed to ``add_page(title=...)``) tracks state.

    Verifying via ``document.title`` proves the state value flows through the
    standard page-metadata path and lands as the title's text node, not as a
    stringified JSX component child.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)
    page.wait_for_selector("#trigger-show")

    expect(page).to_have_title("memo-title-home")

    page.click("#set-title")
    expect(page).to_have_title("memo-title-about")


def test_style_element_renders_stateful_css_as_text(
    memo_app: AppHarness, page: Page
) -> None:
    """``rx.el.style(state_var)`` writes the state value as the stylesheet text.

    Uses a unique marker substring so the test does not collide with Emotion
    or Sonner stylesheets that also live in the document.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)
    page.wait_for_selector("#trigger-show")

    assert _document_contains_style(page, "memo-css-light")
    assert not _document_contains_style(page, "memo-css-dark")

    page.click("#set-css")
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('style'))
            .some(el => (el.textContent || '').includes('memo-css-dark'))""",
        timeout=5000,
    )
    assert _document_contains_style(page, "memo-css-dark")
    assert not _document_contains_style(page, "memo-css-light")


def test_markdown_with_state_var_renders_and_updates(
    memo_app: AppHarness, page: Page
) -> None:
    """``rx.markdown(State.var)`` renders the Var as a string and tracks state.

    Mirrors the bug-report repro: static-source markdown sibling next to a
    Var-source markdown. Pre-fix, the Var-source markdown crashed
    react-markdown and prevented the whole subtree from rendering.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)

    static = page.locator("#md-static")
    expect(static.locator("em")).to_have_text("is")
    expect(static.locator("strong")).to_have_text("working")

    host = page.locator("#md-host")
    expect(host.locator("strong")).to_have_text("memo-md-home")
    expect(host).not_to_contain_text("[object Object]")

    page.click("#set-markdown")

    expect(host.locator("strong")).to_have_text("memo-md-away")
    expect(host).not_to_contain_text("[object Object]")
    expect(static.locator("strong")).to_have_text("working")
