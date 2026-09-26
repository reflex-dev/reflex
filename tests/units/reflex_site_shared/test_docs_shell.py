"""Tests for the shared documentation shell."""

from pathlib import Path
from typing import cast

import pytest
from reflex_site_shared.components import docs_shell
from reflex_site_shared.components.docs_shell import (
    DocsFeedbackState,
    _docs_external_page_footer_memo,
    docs_feedback_button,
    docs_feedback_button_toc,
    docs_left_sidebar,
    docs_page_footer,
    docs_right_sidebar,
    docs_sidebar_category,
    docs_sidebar_group,
    docs_sidebar_leaf,
    docs_sidebar_section,
)
from reflex_site_shared.docs.models import DocsLayoutConfig, DocsPage, NavigationItem
from reflex_site_shared.templates.docs import docs_layout

import reflex as rx
from reflex.istate.data import ReflexURL, RouterData


def test_sidebar_active_marker_aligns_with_section_guide() -> None:
    """Use the same guide alignment and row spacing as a nested Learn group."""
    rendered = str(docs_sidebar_leaf._definition.component)
    section = docs_sidebar_section("MCP", "/mcp/", rx.text("Overview"))
    group = docs_sidebar_group("Getting Started", rx.text("Installation"))
    section_rows = section.children[1]
    group_rows = group.children[0].children[1]

    for rows in (section_rows, group_rows):
        assert "left-[2.5rem]" in str(cast(rx.Component, rows.children[0]).class_name)
        assert "gap-1" in str(cast(rx.Component, rows).class_name)
    assert "-bottom-1 -top-1 left-0" in rendered


def test_feedback_choices_are_individual_popover_triggers():
    """Each feedback choice is a real button, without an interactive div parent."""
    choices = docs_feedback_button().children[0]
    assert choices.tag == "div"
    assert len(choices.children) == 2
    assert all("Trigger" in (child.tag or "") for child in choices.children)


def test_shared_feedback_preserves_the_official_form_structure() -> None:
    """Keep the feedback form layout and accessible clear control."""
    rendered = str(docs_feedback_button_toc())

    assert "w-full gap-4 flex flex-col" in rendered
    assert "flex flex-col gap-4 w-full" in rendered
    assert '"aria-label":"Clear input"' in rendered
    assert 'jsx(Popover.Close,{"data-slot":"popover-close",render:' in rendered


def test_docs_layout_rejects_conflicting_footer_factories() -> None:
    """Require one unambiguous footer API per documentation site."""
    with pytest.raises(ValueError, match="page_footer and footer"):
        DocsLayoutConfig(
            page_footer=lambda page: rx.text(page.title),
            footer=lambda: rx.text("Footer"),
        )


def test_bannerless_sidebars_use_static_navbar_offsets() -> None:
    """Do not consult banner state when a site has no banner."""
    left = str(docs_left_sidebar(rx.text("Navigation"), show_banner=False))
    right = str(docs_right_sidebar([(2, "Overview")], show_banner=False))

    assert "hosting_banner_state" not in left
    assert "hosting_banner_state" not in right
    assert (
        "top-[var(--docs-header-height)] h-[calc(100vh-var(--docs-header-height))]"
        in left
    )
    assert "mt-[calc(var(--docs-header-height)+2rem)]" in right


def test_bannerless_layout_uses_navbar_only_content_offset() -> None:
    """Remove the announcement-height gap from bannerless page content."""
    page = DocsPage(
        source_path=Path("guide.md"),
        relative_path=Path("guide.md"),
        route="/guide",
        title="Guide",
        description=None,
        metadata={},
        content="# Guide",
    )
    rendered = str(
        docs_layout(
            page,
            rx.text("Content"),
            (NavigationItem(title="Guide", route="/guide"),),
            config=DocsLayoutConfig(
                show_banner=False,
                navbar=lambda: rx.fragment(),
                footer=lambda: rx.fragment(),
            ),
        )
    )

    assert "hosting_banner_state" not in rendered
    assert "pt-[calc(var(--docs-header-height)+2rem)]" in rendered
    assert "pt-[9.5rem]" not in rendered


def test_docs_layout_uses_site_owned_sidebar_renderer() -> None:
    """Let a site curate navigation without replacing the shared shell."""
    page = DocsPage(
        source_path=Path("guide.md"),
        relative_path=Path("guide.md"),
        route="/guide/",
        title="Guide",
        description=None,
        metadata={},
        content="# Guide",
    )
    routes: list[str] = []

    def sidebar(route: str) -> rx.Component:
        routes.append(route)
        return rx.text("Curated navigation")

    rendered = str(
        docs_layout(
            page,
            rx.text("Content"),
            (NavigationItem(title="Generated navigation", route="/guide/"),),
            config=DocsLayoutConfig(
                show_banner=False,
                navbar=lambda: rx.fragment(),
                footer=lambda: rx.fragment(),
                sidebar=sidebar,
            ),
        )
    )

    assert routes == ["/guide/"]
    assert "Curated navigation" in rendered
    assert "Generated navigation" not in rendered


def test_shared_sidebar_rows_keep_official_structure() -> None:
    """Keep category and collapsible rows visually identical across sites."""
    category = str(
        docs_sidebar_category(
            "Learn",
            "/getting-started/",
            "graduation-cap",
            True,
        )
    )
    group = str(
        docs_sidebar_group(
            "Getting Started",
            rx.text("Installation"),
            icon="rocket",
            open_=True,
        )
    )

    assert "Navigate to Learn" in category
    assert "ml-[2.5rem]" in category
    assert "LucideGraduationCap" in category
    assert "group/details" in group
    assert "ArrowDown01Icon" in group
    assert 'jsx("summary"' in group
    assert 'jsx("ul"' in group
    assert "open:true" in group


def test_official_docs_footer_content_is_shared() -> None:
    """Keep the complete official footer available to package docs sites."""
    component = docs_page_footer(
        issue_href="https://github.com/example/project/issues/new",
        edit_href="https://github.com/example/project/blob/main/docs/index.md",
    )
    rendered = str(component)

    assert "https://github.com/example/project/issues/new" in str(component)
    assert "Raise an issue" in rendered
    assert "Edit this page" in rendered
    assert "Get started" in rendered
    assert "Documentation" in rendered
    assert "Resources" in rendered
    assert "Social link for Github" in rendered
    assert "Social link for Forum" in rendered
    assert "Pynecone, Inc." in rendered
    assert "https://reflex.dev/docs/getting-started/introduction/" not in rendered
    assert "/getting-started/introduction/" in rendered

    external_rendered = str(_docs_external_page_footer_memo._definition.component)
    assert "https://reflex.dev/docs/getting-started/introduction/" in external_rendered
    for path in (
        "/ai/",
        "/api-reference/app/",
        "/ai/integrations/agent-toolkit/",
        "/enterprise/overview/",
    ):
        assert f"https://reflex.dev/docs{path}" in external_rendered
        assert f"https://reflex.dev/docs{path}" not in rendered
        assert path in rendered
    for path in ("/", "/blog/", "/faq/"):
        assert f'href:"https://reflex.dev{path}"' in rendered


def test_docs_layout_uses_page_aware_footer_renderer() -> None:
    """Pass the discovered source page to a site-specific footer renderer."""
    page = DocsPage(
        source_path=Path("guide/index.md"),
        relative_path=Path("guide/index.md"),
        route="/guide/",
        title="Guide",
        description=None,
        metadata={},
        content="# Guide",
    )
    paths: list[Path] = []

    def page_footer(current_page: DocsPage) -> rx.Component:
        paths.append(current_page.relative_path)
        return rx.text("Official footer")

    rendered = str(
        docs_layout(
            page,
            rx.text("Content"),
            (NavigationItem(title="Guide", route="/guide/"),),
            config=DocsLayoutConfig(
                show_banner=False,
                navbar=lambda: rx.fragment(),
                page_footer=page_footer,
            ),
        )
    )

    assert paths == [Path("guide/index.md")]
    assert "Official footer" in rendered


def test_docs_layout_supports_a_sidebar_aware_breadcrumb() -> None:
    """Allow consumers to reuse the official mobile in-page drawer."""
    page = DocsPage(
        source_path=Path("guide/index.md"),
        relative_path=Path("guide/index.md"),
        route="/guide/",
        title="Guide",
        description=None,
        metadata={},
        content="# Guide",
    )
    received: list[tuple[Path, rx.Component]] = []

    def breadcrumb(current_page: DocsPage, sidebar: rx.Component) -> rx.Component:
        received.append((current_page.relative_path, sidebar))
        return rx.text("Mobile page drawer")

    rendered = str(
        docs_layout(
            page,
            rx.text("Content"),
            (NavigationItem(title="Guide", route="/guide/"),),
            config=DocsLayoutConfig(
                show_banner=False,
                navbar=lambda: rx.fragment(),
                breadcrumb=breadcrumb,
            ),
        )
    )

    assert received[0][0] == Path("guide/index.md")
    assert "Documentation navigation" in str(received[0][1])
    assert "Mobile page drawer" in rendered


def _mock_slack(monkeypatch, delivered: bool) -> list[tuple[str, str]]:
    """Replace the Slack post with a stub that reports a fixed outcome.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        delivered: Whether the stub reports the post as delivered.

    Returns:
        The posted ``(text, channel)`` pairs, in send order.
    """
    posts: list[tuple[str, str]] = []

    async def post_to_slack(text: str, channel: str) -> bool:  # noqa: RUF029
        posts.append((text, channel))
        return delivered

    monkeypatch.setattr(docs_shell, "post_to_slack", post_to_slack)
    monkeypatch.setattr(docs_shell, "SLACK_DOCS_FEEDBACK_CHANNEL", "docs-feedback")
    return posts


def _feedback_state(score: int) -> DocsFeedbackState:
    """Create a feedback state on a docs page with a selected score.

    Args:
        score: The selected feedback score.

    Returns:
        The feedback state.
    """
    root = rx.State(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    root.router = RouterData(url=ReflexURL("https://reflex.dev/docs/guide/"))
    state = cast(DocsFeedbackState, root.get_substate([DocsFeedbackState.get_name()]))
    state.score = score
    return state


async def test_feedback_submission_is_posted_to_slack(monkeypatch) -> None:
    """Post the page, score, contact and escaped comment to the feedback channel."""
    posts = _mock_slack(monkeypatch, delivered=True)
    toast = await DocsFeedbackState.handle_submit.fn(
        _feedback_state(0),
        {"feedback": "Outdated <!channel> example.", "email": "dev@example.com"},
    )

    assert len(posts) == 1
    text, channel = posts[0]
    assert channel == "docs-feedback"
    assert "Page: https://reflex.dev/docs/guide/" in text
    assert "Score: 👎" in text
    assert "Contact: dev@example.com" in text
    assert "Feedback: Outdated &lt;!channel&gt; example." in text
    assert "Thank you for your feedback!" in str(toast)


async def test_feedback_submission_reports_undelivered_posts(monkeypatch) -> None:
    """Tell the reader when their feedback could not be delivered."""
    _mock_slack(monkeypatch, delivered=False)

    toast = await DocsFeedbackState.handle_submit.fn(
        _feedback_state(1), {"feedback": "Great page, thanks!"}
    )

    assert "An error occurred while submitting your feedback" in str(toast)


@pytest.mark.parametrize("feedback", ["too short", "x" * 501])
async def test_feedback_submission_rejects_invalid_length(
    monkeypatch, feedback: str
) -> None:
    """Warn about comments outside the accepted length without sending them."""
    posts = _mock_slack(monkeypatch, delivered=True)
    toast = await DocsFeedbackState.handle_submit.fn(
        _feedback_state(1), {"feedback": feedback}
    )

    assert posts == []
    assert "Between 10 and 500 characters" in str(toast)
