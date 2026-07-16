"""Tests for shared documentation content discovery."""

from pathlib import Path

import pytest
from reflex_site_shared.docs import DocsSiteConfig, discover_docs


def test_discover_docs_builds_routes_and_metadata(tmp_path: Path):
    """Discover Markdown recursively and derive stable routes and metadata."""
    (tmp_path / "index.md").write_text("# Home\n\nWelcome.", encoding="utf-8")
    guide = tmp_path / "getting_started"
    guide.mkdir()
    (guide / "first_steps.md").write_text(
        "---\ntitle: First Steps\ndescription: Start here.\n---\n\n# Ignored heading",
        encoding="utf-8",
    )

    pages = discover_docs(
        DocsSiteConfig(content_dir=tmp_path, route_prefix="/reference")
    )

    assert [(page.route, page.title, page.description) for page in pages] == [
        ("/reference/", "Home", None),
        ("/reference/getting-started/first-steps/", "First Steps", "Start here."),
    ]
    assert pages[1].relative_path.as_posix() == "getting_started/first_steps.md"
    assert pages[1].content == "# Ignored heading"


def test_discover_docs_supports_excluded_globs(tmp_path: Path):
    """Exclude private or generated Markdown using consumer-provided globs."""
    (tmp_path / "public.md").write_text("# Public", encoding="utf-8")
    (tmp_path / "draft.md").write_text("# Draft", encoding="utf-8")
    generated = tmp_path / "generated"
    generated.mkdir()
    (generated / "api.md").write_text("# API", encoding="utf-8")

    pages = discover_docs(
        DocsSiteConfig(
            content_dir=tmp_path,
            exclude=("draft.md", "generated/**"),
        )
    )

    assert [page.route for page in pages] == ["/public/"]


def test_discover_docs_uses_central_navigation_order(tmp_path: Path):
    """Use centralized route order before falling back to route order."""
    (tmp_path / "index.md").write_text("# Home", encoding="utf-8")
    (tmp_path / "advanced.md").write_text("# Advanced", encoding="utf-8")
    (tmp_path / "start.md").write_text("# Start", encoding="utf-8")
    (tmp_path / "reference.md").write_text("# Reference", encoding="utf-8")

    pages = discover_docs(
        DocsSiteConfig(
            content_dir=tmp_path,
            navigation_order=("/", "/start/", "/advanced/"),
        )
    )

    assert [page.route for page in pages] == [
        "/",
        "/start/",
        "/advanced/",
        "/reference/",
    ]


def test_discover_docs_rejects_unknown_navigation_route(tmp_path: Path):
    """Reject navigation entries that do not have a discovered page."""
    (tmp_path / "guide.md").write_text("# Guide", encoding="utf-8")

    with pytest.raises(ValueError, match="unknown routes"):
        discover_docs(
            DocsSiteConfig(
                content_dir=tmp_path,
                navigation_order=("/missing/",),
            )
        )


def test_discover_docs_excludes_nested_paths(tmp_path: Path) -> None:
    """Recursive directory exclusions should cover every descendant."""
    (tmp_path / "index.md").write_text("# Home", encoding="utf-8")
    nested = tmp_path / "app" / ".venv" / "licenses"
    nested.mkdir(parents=True)
    (nested / "dependency.md").write_text("# Dependency", encoding="utf-8")

    pages = discover_docs(
        DocsSiteConfig(content_dir=tmp_path, exclude=("app/**",)),
    )

    assert [page.relative_path for page in pages] == [Path("index.md")]


def test_discover_docs_rejects_duplicate_routes(tmp_path: Path):
    """Reject filenames that normalize to the same public route."""
    (tmp_path / "first_step.md").write_text("# One", encoding="utf-8")
    (tmp_path / "first-step.md").write_text("# Two", encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate documentation route"):
        discover_docs(DocsSiteConfig(content_dir=tmp_path))


def test_discover_docs_requires_a_directory(tmp_path: Path):
    """Fail clearly when the configured content directory does not exist."""
    content_dir = tmp_path / "missing"

    with pytest.raises(FileNotFoundError, match=str(content_dir)):
        discover_docs(DocsSiteConfig(content_dir=content_dir))
