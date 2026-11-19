"""Integration tests for runtime SSR (server-side rendering).

Spins up a blog app with ``runtime_ssr=True`` via ``AppHarnessSSR``, then
verifies:
  - Bots receive fully rendered HTML with blog data, the home page included.
  - Normal users receive the SPA shell (no blog content in raw HTML).
  - Both hold below a frontend_path prefix.
  - Playwright (a real browser) can navigate to dynamic routes and hydrate.
  - The ``/_ssr_data`` backend endpoint returns serialized state.
"""

from __future__ import annotations

from collections.abc import Callable, Generator

import httpx
import pytest
from playwright.sync_api import Browser, Page, expect

import reflex as rx
from reflex.testing import AppHarnessSSR


def SSRBlogApp():
    """A blog app with dynamic routes for SSR testing."""
    import reflex as rx

    POSTS = {
        "hello-world": {
            "title": "Hello World",
            "content": "First post content for SSR testing.",
            "author": "Test Author",
        },
        "second-post": {
            "title": "Second Post",
            "content": "Another post for navigation tests.",
            "author": "Test Author",
        },
    }

    class BlogState(rx.State):
        title: rx.Field[str] = rx.field("")
        content: rx.Field[str] = rx.field("")
        author: rx.Field[str] = rx.field("")
        not_found: rx.Field[bool] = rx.field(False)

        @rx.event
        def on_load_post(self):
            slug: str = self.slug  # pyright: ignore[reportAttributeAccessIssue]
            post = POSTS.get(slug)
            if post:
                self.title = post["title"]
                self.content = post["content"]
                self.author = post["author"]
                self.not_found = False
            else:
                self.title = "Not Found"
                self.content = f"No post with slug '{slug}'"
                self.author = ""
                self.not_found = True

    class IndexState(rx.State):
        post_count: rx.Field[int] = rx.field(0)

        @rx.event
        def on_load_index(self):
            self.post_count = len(POSTS)

    def index() -> rx.Component:
        return rx.container(
            rx.heading("SSR Blog", size="8", data_testid="index-heading"),
            rx.text(IndexState.post_count, data_testid="post-count"),
            rx.vstack(
                rx.link(
                    "Hello World",
                    href="/blog/hello-world",
                    data_testid="link-hello-world",
                ),
                rx.link(
                    "Second Post",
                    href="/blog/second-post",
                    data_testid="link-second-post",
                ),
                spacing="3",
            ),
        )

    @rx.page(
        route="/blog/[slug]",
        title="Blog Post",
        on_load=BlogState.on_load_post,
    )
    def blog_post() -> rx.Component:
        return rx.container(
            rx.link("Back", href="/", data_testid="back-link"),
            rx.cond(
                BlogState.not_found,
                rx.text("Post Not Found", data_testid="not-found"),
                rx.vstack(
                    rx.heading(BlogState.title, size="7", data_testid="post-title"),
                    rx.text(BlogState.author, data_testid="post-author"),
                    rx.text(BlogState.content, data_testid="post-content"),
                    spacing="4",
                ),
            ),
        )

    app = rx.App()
    app.add_page(index, on_load=IndexState.on_load_index)


GOOGLEBOT_UA = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@pytest.fixture(scope="module", params=["", "/app"], ids=["no-prefix", "prefix"])
def frontend_path(request: pytest.FixtureRequest) -> str:
    """Run every test with and without a frontend_path.

    Args:
        request: pytest fixture for accessing the current parameter.

    Returns:
        The frontend_path value for this test instance.
    """
    return request.param


@pytest.fixture(scope="module")
def ssr_blog_app(
    tmp_path_factory: pytest.TempPathFactory, frontend_path: str
) -> Generator[AppHarnessSSR, None, None]:
    """Create and start the SSR blog app.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories.
        frontend_path: The frontend_path the app is served below.

    Yields:
        AppHarnessSSR: A running harness for the SSR blog app.
    """
    with pytest.MonkeyPatch.context() as mp:
        if frontend_path:
            mp.setenv("REFLEX_FRONTEND_PATH", frontend_path)
        else:
            mp.delenv("REFLEX_FRONTEND_PATH", raising=False)
        with AppHarnessSSR.create(
            root=tmp_path_factory.mktemp("ssr_blog"),
            app_source=SSRBlogApp,
        ) as harness:
            assert harness.app_instance is not None, "app is not running"
            yield harness


@pytest.fixture
def pages_url(ssr_blog_app: AppHarnessSSR, frontend_path: str) -> str:
    """The URL the app's pages are served below.

    Args:
        ssr_blog_app: The running SSR blog app harness.
        frontend_path: The frontend_path the app is served below.

    Returns:
        The frontend URL followed by the frontend_path.
    """
    assert ssr_blog_app.frontend_url is not None
    return ssr_blog_app.frontend_url + frontend_path


@pytest.fixture
def server_html(browser: Browser) -> Generator[Callable[[str, str], Page], None, None]:
    """Open pages with scripts disabled, so they show the HTML the server sent.

    Args:
        browser: The Playwright browser.

    Yields:
        A function opening a URL with the given user agent.
    """
    contexts = []

    def open_page(url: str, user_agent: str) -> Page:
        context = browser.new_context(user_agent=user_agent, java_script_enabled=False)
        contexts.append(context)
        page = context.new_page()
        page.goto(url)
        return page

    yield open_page
    for context in contexts:
        context.close()


def test_bot_gets_ssr_html(pages_url: str, server_html: Callable[[str, str], Page]):
    """Bots (Googlebot) should receive fully rendered HTML with blog data.

    Args:
        pages_url: The URL the app's pages are served below.
        server_html: Opens a page showing the HTML the server sent.
    """
    page = server_html(f"{pages_url}/blog/hello-world", GOOGLEBOT_UA)

    expect(page.get_by_test_id("post-title")).to_have_text("Hello World")
    expect(page.get_by_test_id("post-content")).to_have_text(
        "First post content for SSR testing."
    )
    expect(page.get_by_test_id("post-author")).to_have_text("Test Author")


def test_bot_gets_ssr_home_page(
    pages_url: str, server_html: Callable[[str, str], Page]
):
    """The home page is server-rendered for bots too, not served as the shell.

    Args:
        pages_url: The URL the app's pages are served below.
        server_html: Opens a page showing the HTML the server sent.
    """
    page = server_html(f"{pages_url}/", GOOGLEBOT_UA)

    expect(page.get_by_test_id("post-count")).to_have_text("2")


def test_normal_user_gets_spa_shell(
    pages_url: str, server_html: Callable[[str, str], Page]
):
    """Normal users should receive the SPA shell without blog-specific content.

    Args:
        pages_url: The URL the app's pages are served below.
        server_html: Opens a page showing the HTML the server sent.
    """
    page = server_html(f"{pages_url}/blog/hello-world", CHROME_UA)

    # The shell is the home page rendered without backend state.
    expect(page.get_by_test_id("index-heading")).to_have_text("SSR Blog")
    expect(page.get_by_test_id("post-count")).to_have_text("0")
    expect(page.get_by_test_id("post-content")).to_have_count(0)


def test_direct_access_blog_post(pages_url: str, page: Page):
    """Navigating directly to a blog post URL should hydrate and show content.

    Args:
        pages_url: The URL the app's pages are served below.
        page: A Playwright page.
    """
    page.goto(f"{pages_url}/blog/hello-world")

    title = page.get_by_test_id("post-title")
    expect(title).to_be_visible(timeout=15000)
    expect(title).to_have_text("Hello World")

    content = page.get_by_test_id("post-content")
    expect(content).to_have_text("First post content for SSR testing.", timeout=15000)

    author = page.get_by_test_id("post-author")
    expect(author).to_have_text("Test Author", timeout=15000)


def test_client_navigation(pages_url: str, page: Page):
    """Clicking a link on the index should navigate to the blog post via SPA.

    Args:
        pages_url: The URL the app's pages are served below.
        page: A Playwright page.
    """
    page.goto(f"{pages_url}/")

    heading = page.get_by_test_id("index-heading")
    expect(heading).to_be_visible(timeout=15000)
    expect(heading).to_have_text("SSR Blog")

    # Click the link to navigate to a blog post.
    link = page.get_by_test_id("link-hello-world")
    expect(link).to_be_visible()
    link.click()

    # Wait for the blog post content to appear.
    title = page.get_by_test_id("post-title")
    expect(title).to_be_visible(timeout=15000)
    expect(title).to_have_text("Hello World")


def test_navigate_between_posts(pages_url: str, page: Page):
    """Navigate from Post A -> home -> Post B to verify multi-step navigation.

    Args:
        pages_url: The URL the app's pages are served below.
        page: A Playwright page.
    """
    # Start at the first post.
    page.goto(f"{pages_url}/blog/hello-world")
    title = page.get_by_test_id("post-title")
    expect(title).to_be_visible(timeout=15000)
    expect(title).to_have_text("Hello World")

    # Go back to index.
    back = page.get_by_test_id("back-link")
    back.click()
    heading = page.get_by_test_id("index-heading")
    expect(heading).to_be_visible(timeout=15000)

    # Navigate to the second post.
    link = page.get_by_test_id("link-second-post")
    expect(link).to_be_visible()
    link.click()

    title2 = page.get_by_test_id("post-title")
    expect(title2).to_be_visible(timeout=15000)
    expect(title2).to_have_text("Second Post")

    content2 = page.get_by_test_id("post-content")
    expect(content2).to_have_text("Another post for navigation tests.")


def test_ssr_data_endpoint(frontend_path: str):
    """The /_ssr_data backend endpoint should return serialized state.

    Args:
        frontend_path: The frontend_path the app is served below.
    """
    api_url = rx.config.get_config().api_url
    assert api_url is not None

    resp = httpx.post(
        f"{api_url}/{rx.constants.Endpoint.SSR_DATA.value}",
        json={"path": f"{frontend_path}/blog/hello-world", "headers": {}},
    )
    assert resp.status_code == 200

    data = resp.json()
    assert "state" in data
    state = data["state"]
    # The state is a nested dict: top-level keys are substate paths like
    # "reflex___state____state.ssrblogapp___ssrblogapp____blog_state".
    # Var names are mangled with a suffix (e.g. "title" → "title_rx_state_").
    # Find the BlogState substate and verify blog data is present.
    blog_state = None
    for key, value in state.items():
        if "blog_state" in key and isinstance(value, dict):
            blog_state = value
            break
    assert blog_state is not None, (
        f"BlogState substate not found in: {list(state.keys())}"
    )
    # Check that the title field is set (may be mangled with a suffix).
    title_values = [v for k, v in blog_state.items() if k.startswith("title")]
    assert any(v == "Hello World" for v in title_values), (
        f"Expected 'Hello World' in title fields: {blog_state}"
    )


def test_not_found_post(pages_url: str, page: Page):
    """Navigating to a non-existent slug should show the "Post Not Found" text.

    Args:
        pages_url: The URL the app's pages are served below.
        page: A Playwright page.
    """
    page.goto(f"{pages_url}/blog/does-not-exist")

    not_found = page.get_by_test_id("not-found")
    expect(not_found).to_be_visible(timeout=15000)
    expect(not_found).to_have_text("Post Not Found")
