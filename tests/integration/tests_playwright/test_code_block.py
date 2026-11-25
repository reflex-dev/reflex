"""Integration tests for the code block component."""

import re
import time
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

DEFAULT_COPY_CODE = "print('copied from default button')"
CUSTOM_COPY_CODE = "print('copied from custom button')"
URL_COPY_CONTENT = "copied from a fetched URL"


def CodeBlockApp():
    """App exercising code block rendering options."""
    from pathlib import Path

    import reflex as rx
    from reflex import constants
    from reflex.utils.prerequisites import get_web_dir

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
            rx.button(
                "Copy from URL",
                id="url-copy",
                on_click=rx.set_clipboard(url="/hello.txt"),
            ),
            align_items="stretch",
            spacing="4",
            width="480px",
        )

    # Serve the fetch target through the frontend's public directory: the
    # upload StaticFiles mount resolves its relative directory against the
    # harness host process cwd, which is not the app directory, so the
    # backend upload route cannot serve the file under AppHarness.
    public_dir = Path(get_web_dir()) / constants.Dirs.PUBLIC
    public_dir.mkdir(parents=True, exist_ok=True)
    # The app source is serialized into the harness module; keep the literal
    # local, mirroring the copy-code constants above.
    (public_dir / "hello.txt").write_text("copied from a fetched URL")

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

    # PrismAsyncLight loads the language grammar asynchronously, so token
    # spans appear after the initial plain-text render; wait for one.
    expect(code_tag.get_by_text("def", exact=True)).to_be_visible()

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


def test_code_block_set_clipboard_from_url(
    code_block_app: AppHarness, page: Page
) -> None:
    """rx.set_clipboard(url=...) copies fetched text, with zero error reports.

    Grants clipboard-read and clipboard-write (CI headless-shell denies
    trusted-click writes without them), installs error listeners before the
    click, and asserts the section-2 success accounting: clipboard content
    updated, zero tagged console errors, zero window errors, zero unhandled
    rejections. The served Content-Type is captured and asserted against
    the MIME policy (text/* accepted).

    Args:
        code_block_app: Running code block app harness.
        page: Playwright page.
    """
    page.context.grant_permissions(
        ["clipboard-read", "clipboard-write"], origin=code_block_app.frontend_url
    )
    served_types: list[str] = []
    page.on(
        "response",
        lambda response: (
            served_types.append(response.headers.get("content-type", ""))
            if "hello.txt" in response.url
            else None
        ),
    )
    page.add_init_script("""
        window.__clipboardTagCount = 0;
        window.__clipboardWindowErrors = [];
        window.__clipboardUnhandled = [];
        window.addEventListener("error", (e) => {
            window.__clipboardWindowErrors.push(String(e.message));
        });
        window.addEventListener("unhandledrejection", (e) => {
            window.__clipboardUnhandled.push(String(e.reason));
        });
        const originalError = console.error.bind(console);
        console.error = (...args) => {
            if (args[0] === "_set_clipboard_from_url") {
                window.__clipboardTagCount += 1;
            }
            originalError(...args);
        };
    """)
    _goto_code_block_app(code_block_app, page)
    page.evaluate("navigator.clipboard.writeText('')")
    page.click("#url-copy")
    copied = ""
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        copied = page.evaluate("navigator.clipboard.readText()")
        if copied == URL_COPY_CONTENT:
            break
        time.sleep(0.2)
    assert copied == URL_COPY_CONTENT
    assert served_types, "no response captured for hello.txt"
    assert all(
        content_type.split(";")[0].strip().lower().startswith("text/")
        for content_type in served_types
    ), f"unexpected Content-Type for hello.txt: {served_types}"
    assert page.evaluate("window.__clipboardTagCount") == 0
    assert page.evaluate("window.__clipboardWindowErrors") == []
    assert page.evaluate("window.__clipboardUnhandled") == []


SENTINEL_CLIPBOARD_TEXT = "sentinel"

# Shared browser-side observer for the url-copy scenarios: counts tagged
# console.error reports, window errors, and unhandled rejections.
_OBSERVER_INIT_SCRIPT = """
    window.__clipboardTagCount = 0;
    window.__clipboardWindowErrors = [];
    window.__clipboardUnhandled = [];
    window.addEventListener("error", (e) => {
        window.__clipboardWindowErrors.push(String(e.message));
    });
    window.addEventListener("unhandledrejection", (e) => {
        window.__clipboardUnhandled.push(String(e.reason));
    });
    const originalError = console.error.bind(console);
    console.error = (...args) => {
        if (args[0] === "_set_clipboard_from_url") {
            window.__clipboardTagCount += 1;
        }
        originalError(...args);
    };
"""

# Deterministic 404 for ONLY the missing-asset URL; every other URL passes
# through. The dev harness serves 200 text/html for missing assets
# (react-router catch-all), so a real server 404 is not producible here; the
# real-server MIME-refusal case below keeps server-level coverage.
_FETCH_404_INIT_SCRIPT = """
    (() => {
        const originalFetch = window.fetch.bind(window);
        window.fetch = (input, init) => {
            if (String(input).endsWith("/clipboard-missing.txt")) {
                return Promise.resolve(
                    new Response("not found", {status: 404, statusText: "Not Found"})
                );
            }
            return originalFetch(input, init);
        };
    })();
"""

# Async write-rejection mode: the write() call returns a rejected promise,
# flowing through the arrow's write-side catch. The sync-catch branch is a
# different mode and is intentionally not exercised here.
_WRITE_REJECT_INIT_SCRIPT = """
    Object.defineProperty(Clipboard.prototype, "write", {
        value: () => Promise.reject(new Error("mock write denial")),
        configurable: true,
        writable: true,
    });
"""

# Force the writeText fallback path by removing ClipboardItem.
_NO_CLIPBOARD_ITEM_INIT_SCRIPT = """
    delete window.ClipboardItem;
"""

# Frozen whole-value expectations for the normalized backend report strings,
# built from observed samples per the repo's normalize-then-compare-whole
# testing policy; _normalize_report defines the normalized run-dependent
# parts (origin with port, bundle-hash path segments, and source locations
# on stack-frame lines). Message text stays byte-exact.
EXPECTED_REPORT_HTTP_404 = (
    "Error: set_clipboard: HTTP 404\n"
    "Error: set_clipboard: HTTP 404\n"
    "    at <ORIGIN>/app_components/clipboardurlerrorapp/clipboardurlerrorapp.jsx:<LOC>"
)
EXPECTED_REPORT_MIME_REFUSED = (
    "Error: set_clipboard: unsupported content type\n"
    "Error: set_clipboard: unsupported content type\n"
    "    at <ORIGIN>/app_components/clipboardurlerrorapp/clipboardurlerrorapp.jsx:<LOC>"
)
EXPECTED_REPORT_WRITE_DENIAL = (
    "Error: mock write denial\n"
    "Error: mock write denial\n"
    "    at Clipboard.value \\[as write] (<anonymous>:<LOC>)\n"
    "    at <ORIGIN>/app_components/clipboardurlerrorapp/clipboardurlerrorapp.jsx:<LOC>\n"
    "    at Object.function (<ORIGIN>/app_components/clipboardurlerrorapp/clipboardurlerrorapp.jsx:<LOC>)\n"
    "    at applyEvent (<ORIGIN>/utils/state.js:<LOC>)\n"
    "    at processEvent (<ORIGIN>/utils/state.js:<LOC>)\n"
    "    at queueEvents (<ORIGIN>/utils/state.js:<LOC>)\n"
    "    at <ORIGIN>/utils/state.js:<LOC>\n"
    "    at invokeTarget (<ORIGIN>/utils/state.js:<LOC>)\n"
    "    at applyEventActions (<ORIGIN>/utils/state.js:<LOC>)\n"
    "    at Object.addEvents (<ORIGIN>/utils/state.js:<LOC>)"
)


def ClipboardUrlErrorApp():
    """Stateful app exercising set_clipboard(url=...) failure reporting.

    A second app in this file is a justified deviation from the
    extend-existing-apps guidance: backend exception forwarding is a state
    event (handle_frontend_exception), so it requires a stateful app, and
    CodeBlockApp is enable_state=False.
    """
    from pathlib import Path

    import reflex as rx
    from reflex import constants
    from reflex.utils.prerequisites import get_web_dir

    class ClipboardUrlState(rx.State):
        """State for the clipboard url error app."""

        counter: int = 0

        @rx.event
        def bump(self):
            """Increment the counter for the observable round-trip barrier."""
            self.counter += 1

    def index():
        return rx.vstack(
            rx.text(ClipboardUrlState.counter, id="counter"),
            rx.input(
                value=ClipboardUrlState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.button("bump", on_click=ClipboardUrlState.bump, id="bump-btn"),
            rx.button(
                "Copy from URL",
                id="url-copy-ok",
                on_click=rx.set_clipboard(url="/hello.txt"),
            ),
            rx.button(
                "Copy missing URL",
                id="url-copy-missing",
                on_click=rx.set_clipboard(url="/clipboard-missing.txt"),
            ),
            rx.button(
                "Copy HTML URL",
                id="url-copy-html",
                on_click=rx.set_clipboard(url="/hello.html"),
            ),
        )

    # Same factory-time, config-aware public write as CodeBlockApp: the file
    # must exist before the frontend's startup scan of the public directory.
    public_dir = Path(get_web_dir()) / constants.Dirs.PUBLIC
    public_dir.mkdir(parents=True, exist_ok=True)
    (public_dir / "hello.txt").write_text("copied from a fetched URL")
    (public_dir / "hello.html").write_text("<html><body>not plain text</body></html>")
    # clipboard-missing.txt is deliberately never written.

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def clipboard_url_error_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start the clipboard url error test app.

    Args:
        tmp_path_factory: Pytest tmp path factory.

    Yields:
        The running app harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("clipboard_url_error_app"),
        app_source=ClipboardUrlErrorApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def _goto_clipboard_url_error_app(
    clipboard_url_error_app: AppHarness, page: Page
) -> None:
    """Navigate to the error app and pass the hydration gate.

    The token gate guarantees the socket and the exception-forwarding
    handlers are live before any stateful click.

    Args:
        clipboard_url_error_app: Running error app harness.
        page: Playwright page.
    """
    assert clipboard_url_error_app.frontend_url is not None
    page.goto(clipboard_url_error_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")


def _seed_clipboard(page: Page) -> None:
    """Seed the clipboard with the sentinel and read it back.

    Args:
        page: Playwright page.
    """
    page.evaluate(
        "text => navigator.clipboard.writeText(text)", arg=SENTINEL_CLIPBOARD_TEXT
    )
    assert page.evaluate("navigator.clipboard.readText()") == SENTINEL_CLIPBOARD_TEXT


def _barrier_backend_round_trip(page: Page) -> None:
    """Bound in-flight frontend events with an observable backend round trip.

    Backend event processing is ordered per token, so every frontend event
    dispatched before the bump click, including the exception report, has
    been processed once the rendered counter updates.

    Args:
        page: Playwright page.
    """
    before = int(page.locator("#counter").inner_text())
    page.click("#bump-btn")
    expect(page.locator("#counter")).to_have_text(str(before + 1))


# Chromium stack-frame lines carry build/run-dependent source locations
# (``file:line:column``) that shift with any bundle rebuild. Locations are
# normalized to ``:<LOC>`` on recognized stack-frame lines only (optional
# leading whitespace followed by ``at ``); message lines, including any
# colon-separated numbers inside the message text, stay byte-exact.
_LOCATION_RE = re.compile(r":\d+:\d+")
_FRAME_LINE_RE = re.compile(r"^\s*at\s")


def _normalize_report(report: str) -> str:
    """Normalize the run-dependent parts of a frontend exception report.

    The origin with its port, bundle-hash path segments, and source
    locations on stack-frame lines become fixed placeholders; message text
    is left untouched. The whole normalized value (message lines and stack
    with frame names, order and count) is then compared for equality.

    Args:
        report: The raw collected exception string.

    Returns:
        The normalized report.
    """
    normalized = re.sub(r"https?://localhost:\d+", "<ORIGIN>", report)
    normalized = re.sub(
        r"(?<=-)[A-Za-z0-9_-]{8,}(?=\.(?:js|mjs|css))", "<HASH>", normalized
    )
    return "\n".join(
        _LOCATION_RE.sub(":<LOC>", line) if _FRAME_LINE_RE.match(line) else line
        for line in normalized.split("\n")
    )


def _assert_single_normalized_report(reports: list[str], expected: str) -> None:
    """Assert exactly one report, equal to the frozen normalized value.

    Args:
        reports: The collected exception strings.
        expected: The frozen normalized expectation.
    """
    assert len(reports) == 1, f"expected exactly one report, got {len(reports)}"
    assert _normalize_report(reports[0]) == expected


def test_normalize_report_layout_only_changes_are_equivalent() -> None:
    """Port, bundle hash and frame locations normalize to fixed placeholders."""
    base = (
        "Error: set_clipboard: HTTP 404\n"
        "    at onClick (http://localhost:3000/_static/app-a1b2c3d4.js:179:28)"
    )
    shifted = (
        "Error: set_clipboard: HTTP 404\n"
        "    at onClick (http://localhost:54321/_static/app-f9e8d7c6.js:42:17)"
    )
    expected = (
        "Error: set_clipboard: HTTP 404\n"
        "    at onClick (<ORIGIN>/_static/app-<HASH>.js:<LOC>)"
    )
    assert _normalize_report(base) == expected
    assert _normalize_report(shifted) == expected


def test_normalize_report_keeps_message_text_exact() -> None:
    """Message text, including colon-separated numbers, stays byte-exact."""
    report = "Error: ratio 12:34:56 out of range\n    at onClick (/app.js:1:1)"
    normalized = _normalize_report(report)
    assert normalized.split("\n", 1)[0] == "Error: ratio 12:34:56 out of range"
    changed_message = report.replace("12:34:56", "12:34:57")
    assert _normalize_report(report) != _normalize_report(changed_message)


def test_normalize_report_distinguishes_frame_identity() -> None:
    """Function or file changes on frames remain distinguishable."""
    base = "Error: boom\n    at onClick (/app.js:1:1)"
    other_function = "Error: boom\n    at onSubmit (/app.js:1:1)"
    other_file = "Error: boom\n    at onClick (/other.js:1:1)"
    assert _normalize_report(base) != _normalize_report(other_function)
    assert _normalize_report(base) != _normalize_report(other_file)


def test_normalize_report_distinguishes_frame_count_and_order() -> None:
    """Removed or reordered frames remain distinguishable."""
    base = "Error: boom\n    at a (/a.js:1:1)\n    at b (/b.js:2:2)"
    removed = "Error: boom\n    at a (/a.js:1:1)"
    reordered = "Error: boom\n    at b (/b.js:2:2)\n    at a (/a.js:1:1)"
    assert _normalize_report(base) != _normalize_report(removed)
    assert _normalize_report(base) != _normalize_report(reordered)


def test_set_clipboard_url_http_error_reports_once(
    code_block_app: AppHarness,
    clipboard_url_error_app: AppHarness,
    page: Page,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 404 fetch reports exactly once through the ClipboardItem path.

    Coverage limit: the dev harness provably cannot return a real 404 for a
    missing asset (react-router catch-all serves 200 text/html), so the
    HTTP-status branch is tested against a deterministic scoped fetch mock,
    not server behavior; the MIME-refusal test keeps real-server coverage.

    This test also pins concurrent-routing coverage: it requests BOTH
    module-scoped fixtures, and module-scoped fixtures are finalized at
    module end, so both harnesses are alive while it runs.

    Args:
        code_block_app: Running code block app harness.
        clipboard_url_error_app: Running error app harness.
        page: Playwright page.
        monkeypatch: pytest fixture for patching the exception handler.
    """
    assert code_block_app.app_instance is not None, "code block app is not running"
    assert clipboard_url_error_app.frontend_url is not None
    assert clipboard_url_error_app.app_instance is not None
    page.context.grant_permissions(
        ["clipboard-read", "clipboard-write"],
        origin=clipboard_url_error_app.frontend_url,
    )
    page.add_init_script(_OBSERVER_INIT_SCRIPT)
    page.add_init_script(_FETCH_404_INIT_SCRIPT)
    reports: list[str] = []
    monkeypatch.setattr(
        clipboard_url_error_app.app_instance,
        "frontend_exception_handler",
        lambda exc: reports.append(str(exc)),
    )
    _goto_clipboard_url_error_app(clipboard_url_error_app, page)
    _seed_clipboard(page)

    page.click("#url-copy-missing")
    page.wait_for_function(
        "() => window.__clipboardUnhandled.length === 1"
        " && window.__clipboardTagCount === 1"
    )
    _barrier_backend_round_trip(page)

    assert page.evaluate("window.__clipboardUnhandled") == [
        "Error: set_clipboard: HTTP 404"
    ]
    assert page.evaluate("window.__clipboardTagCount") == 1
    assert page.evaluate("window.__clipboardWindowErrors") == []
    assert AppHarness._poll_for(lambda: reports), (
        "backend was not told about the clipboard failure"
    )
    _assert_single_normalized_report(reports, EXPECTED_REPORT_HTTP_404)
    assert page.evaluate("navigator.clipboard.readText()") == SENTINEL_CLIPBOARD_TEXT


def test_set_clipboard_url_mime_refusal_reports_once(
    clipboard_url_error_app: AppHarness, page: Page, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A text/html fetch is refused by the MIME policy and reported once.

    Real-server case: hello.html is served by the actual dev frontend. The
    captured Content-Type is normalized (split at ";", trimmed, lowercased)
    and compared as a complete value.

    Args:
        clipboard_url_error_app: Running error app harness.
        page: Playwright page.
        monkeypatch: pytest fixture for patching the exception handler.
    """
    assert clipboard_url_error_app.frontend_url is not None
    assert clipboard_url_error_app.app_instance is not None
    page.context.grant_permissions(
        ["clipboard-read", "clipboard-write"],
        origin=clipboard_url_error_app.frontend_url,
    )
    page.add_init_script(_OBSERVER_INIT_SCRIPT)
    served_types: list[str] = []
    page.on(
        "response",
        lambda response: (
            served_types.append(response.headers.get("content-type", ""))
            if "hello.html" in response.url
            else None
        ),
    )
    reports: list[str] = []
    monkeypatch.setattr(
        clipboard_url_error_app.app_instance,
        "frontend_exception_handler",
        lambda exc: reports.append(str(exc)),
    )
    _goto_clipboard_url_error_app(clipboard_url_error_app, page)
    _seed_clipboard(page)

    page.click("#url-copy-html")
    page.wait_for_function(
        "() => window.__clipboardUnhandled.length === 1"
        " && window.__clipboardTagCount === 1"
    )
    _barrier_backend_round_trip(page)

    assert served_types, "no response captured for hello.html"
    assert {ct.split(";")[0].strip().lower() for ct in served_types} == {"text/html"}
    assert page.evaluate("window.__clipboardUnhandled") == [
        "Error: set_clipboard: unsupported content type"
    ]
    assert page.evaluate("window.__clipboardTagCount") == 1
    assert page.evaluate("window.__clipboardWindowErrors") == []
    assert AppHarness._poll_for(lambda: reports), (
        "backend was not told about the clipboard failure"
    )
    _assert_single_normalized_report(reports, EXPECTED_REPORT_MIME_REFUSED)
    assert page.evaluate("navigator.clipboard.readText()") == SENTINEL_CLIPBOARD_TEXT


def test_set_clipboard_url_write_rejection_reports_once(
    clipboard_url_error_app: AppHarness, page: Page, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An async clipboard.write rejection reports exactly once.

    The fetch succeeds; only the write is mocked to reject. This is scoped
    as a reporting-contract test: it claims nothing about native permission
    behavior, and it exercises the async rejection path only.

    Args:
        clipboard_url_error_app: Running error app harness.
        page: Playwright page.
        monkeypatch: pytest fixture for patching the exception handler.
    """
    assert clipboard_url_error_app.frontend_url is not None
    assert clipboard_url_error_app.app_instance is not None
    page.context.grant_permissions(
        ["clipboard-read", "clipboard-write"],
        origin=clipboard_url_error_app.frontend_url,
    )
    page.add_init_script(_OBSERVER_INIT_SCRIPT)
    page.add_init_script(_WRITE_REJECT_INIT_SCRIPT)
    reports: list[str] = []
    monkeypatch.setattr(
        clipboard_url_error_app.app_instance,
        "frontend_exception_handler",
        lambda exc: reports.append(str(exc)),
    )
    _goto_clipboard_url_error_app(clipboard_url_error_app, page)
    _seed_clipboard(page)

    page.click("#url-copy-ok")
    page.wait_for_function(
        "() => window.__clipboardUnhandled.length === 1"
        " && window.__clipboardTagCount === 1"
    )
    _barrier_backend_round_trip(page)

    assert page.evaluate("window.__clipboardUnhandled") == ["Error: mock write denial"]
    assert page.evaluate("window.__clipboardTagCount") == 1
    assert page.evaluate("window.__clipboardWindowErrors") == []
    assert AppHarness._poll_for(lambda: reports), (
        "backend was not told about the clipboard failure"
    )
    _assert_single_normalized_report(reports, EXPECTED_REPORT_WRITE_DENIAL)
    assert page.evaluate("navigator.clipboard.readText()") == SENTINEL_CLIPBOARD_TEXT


def test_set_clipboard_url_writetext_fallback_success(
    clipboard_url_error_app: AppHarness, page: Page, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without ClipboardItem, the writeText fallback copies the fetched text.

    Args:
        clipboard_url_error_app: Running error app harness.
        page: Playwright page.
        monkeypatch: pytest fixture for patching the exception handler.
    """
    assert clipboard_url_error_app.frontend_url is not None
    assert clipboard_url_error_app.app_instance is not None
    page.context.grant_permissions(
        ["clipboard-read", "clipboard-write"],
        origin=clipboard_url_error_app.frontend_url,
    )
    page.add_init_script(_OBSERVER_INIT_SCRIPT)
    page.add_init_script(_NO_CLIPBOARD_ITEM_INIT_SCRIPT)
    reports: list[str] = []
    monkeypatch.setattr(
        clipboard_url_error_app.app_instance,
        "frontend_exception_handler",
        lambda exc: reports.append(str(exc)),
    )
    _goto_clipboard_url_error_app(clipboard_url_error_app, page)
    _seed_clipboard(page)

    page.click("#url-copy-ok")
    page.wait_for_function(
        "expected => navigator.clipboard.readText().then(text => text === expected)",
        arg=URL_COPY_CONTENT,
    )
    _barrier_backend_round_trip(page)

    assert page.evaluate("window.__clipboardUnhandled") == []
    assert page.evaluate("window.__clipboardTagCount") == 0
    assert page.evaluate("window.__clipboardWindowErrors") == []
    assert reports == []


def test_set_clipboard_url_writetext_fallback_fetch_failure(
    clipboard_url_error_app: AppHarness, page: Page, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without ClipboardItem, a 404 fetch reports once and preserves the seed.

    Same scoped-fetch-mock coverage limit as the HTTP-error test above.

    Args:
        clipboard_url_error_app: Running error app harness.
        page: Playwright page.
        monkeypatch: pytest fixture for patching the exception handler.
    """
    assert clipboard_url_error_app.frontend_url is not None
    assert clipboard_url_error_app.app_instance is not None
    page.context.grant_permissions(
        ["clipboard-read", "clipboard-write"],
        origin=clipboard_url_error_app.frontend_url,
    )
    page.add_init_script(_OBSERVER_INIT_SCRIPT)
    page.add_init_script(_NO_CLIPBOARD_ITEM_INIT_SCRIPT)
    page.add_init_script(_FETCH_404_INIT_SCRIPT)
    reports: list[str] = []
    monkeypatch.setattr(
        clipboard_url_error_app.app_instance,
        "frontend_exception_handler",
        lambda exc: reports.append(str(exc)),
    )
    _goto_clipboard_url_error_app(clipboard_url_error_app, page)
    _seed_clipboard(page)

    page.click("#url-copy-missing")
    page.wait_for_function(
        "() => window.__clipboardUnhandled.length === 1"
        " && window.__clipboardTagCount === 1"
    )
    _barrier_backend_round_trip(page)

    assert page.evaluate("window.__clipboardUnhandled") == [
        "Error: set_clipboard: HTTP 404"
    ]
    assert page.evaluate("window.__clipboardTagCount") == 1
    assert page.evaluate("window.__clipboardWindowErrors") == []
    assert AppHarness._poll_for(lambda: reports), (
        "backend was not told about the clipboard failure"
    )
    _assert_single_normalized_report(reports, EXPECTED_REPORT_HTTP_404)
    assert page.evaluate("navigator.clipboard.readText()") == SENTINEL_CLIPBOARD_TEXT
