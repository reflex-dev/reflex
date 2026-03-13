"""Integration tests for runtime SSR (server-side rendering).

Spins up a blog app with ``runtime_ssr=True`` via ``AppHarnessSSR``, then
verifies:
  - Bots receive fully rendered HTML with blog data.
  - Normal users receive the SPA shell (no blog content in raw HTML).
  - Playwright (a real browser) can navigate to dynamic routes and hydrate.
  - The ``/_ssr_data`` backend endpoint returns serialized state.
"""

from __future__ import annotations

from collections.abc import Generator

import httpx
import pytest
from playwright.sync_api import Page, expect

import reflex as rx
from reflex.testing import AppHarnessSSR

# ---------------------------------------------------------------------------
# App source - a minimal blog with a dynamic /blog/[slug] route.
# ---------------------------------------------------------------------------


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

    def index() -> rx.Component:
        return rx.container(
            rx.heading("SSR Blog", size="8", data_testid="index-heading"),
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
    app.add_page(index)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GOOGLEBOT_UA = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@pytest.fixture(scope="module")
def ssr_blog_app(tmp_path_factory) -> Generator[AppHarnessSSR, None, None]:
    """Create and start the SSR blog app.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        AppHarnessSSR: A running harness for the SSR blog app.
    """
    with AppHarnessSSR.create(
        root=tmp_path_factory.mktemp("ssr_blog"),
        app_source=SSRBlogApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_bot_gets_ssr_html(ssr_blog_app: AppHarnessSSR):
    """Bots (Googlebot) should receive fully rendered HTML with blog data.

    Args:
        ssr_blog_app: The running SSR blog app harness.
    """
    assert ssr_blog_app.frontend_url is not None
    url = f"{ssr_blog_app.frontend_url}/blog/hello-world"
    resp = httpx.get(url, headers={"User-Agent": GOOGLEBOT_UA}, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.text
    # The HTML should contain the actual blog post data (server-rendered).
    assert "Hello World" in body
    assert "First post content for SSR testing." in body
    assert "Test Author" in body


def test_normal_user_gets_spa_shell(ssr_blog_app: AppHarnessSSR):
    """Normal users should receive the SPA shell without blog-specific content.

    Args:
        ssr_blog_app: The running SSR blog app harness.
    """
    assert ssr_blog_app.frontend_url is not None
    url = f"{ssr_blog_app.frontend_url}/blog/hello-world"
    resp = httpx.get(
        url,
        headers={
            "User-Agent": CHROME_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    body = resp.text
    # The SPA shell should NOT contain post-specific rendered content.
    assert "First post content for SSR testing." not in body
    # But it should be valid HTML with the app shell structure.
    assert "<html" in body.lower()


def test_direct_access_blog_post(ssr_blog_app: AppHarnessSSR, page: Page):
    """Navigating directly to a blog post URL should hydrate and show content.

    Args:
        ssr_blog_app: The running SSR blog app harness.
        page: A Playwright page.
    """
    assert ssr_blog_app.frontend_url is not None
    page.goto(f"{ssr_blog_app.frontend_url}/blog/hello-world")

    title = page.get_by_test_id("post-title")
    expect(title).to_be_visible(timeout=15000)
    expect(title).to_have_text("Hello World")

    content = page.get_by_test_id("post-content")
    expect(content).to_have_text("First post content for SSR testing.")

    author = page.get_by_test_id("post-author")
    expect(author).to_have_text("Test Author")


def test_client_navigation(ssr_blog_app: AppHarnessSSR, page: Page):
    """Clicking a link on the index should navigate to the blog post via SPA.

    Args:
        ssr_blog_app: The running SSR blog app harness.
        page: A Playwright page.
    """
    assert ssr_blog_app.frontend_url is not None
    page.goto(ssr_blog_app.frontend_url)

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


def test_navigate_between_posts(ssr_blog_app: AppHarnessSSR, page: Page):
    """Navigate from Post A -> home -> Post B to verify multi-step navigation.

    Args:
        ssr_blog_app: The running SSR blog app harness.
        page: A Playwright page.
    """
    assert ssr_blog_app.frontend_url is not None

    # Start at the first post.
    page.goto(f"{ssr_blog_app.frontend_url}/blog/hello-world")
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


def test_ssr_data_endpoint(ssr_blog_app: AppHarnessSSR):
    """The /_ssr_data backend endpoint should return serialized state.

    Args:
        ssr_blog_app: The running SSR blog app harness.
    """
    api_url = rx.config.get_config().api_url
    assert api_url is not None

    resp = httpx.post(
        f"{api_url}/{rx.constants.Endpoint.SSR_DATA.value}",
        json={"path": "/blog/hello-world", "headers": {}},
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


def test_not_found_post(ssr_blog_app: AppHarnessSSR, page: Page):
    """Navigating to a non-existent slug should show the "Post Not Found" text.

    Args:
        ssr_blog_app: The running SSR blog app harness.
        page: A Playwright page.
    """
    assert ssr_blog_app.frontend_url is not None
    page.goto(f"{ssr_blog_app.frontend_url}/blog/does-not-exist")

    not_found = page.get_by_test_id("not-found")
    expect(not_found).to_be_visible(timeout=15000)
    expect(not_found).to_have_text("Post Not Found")
