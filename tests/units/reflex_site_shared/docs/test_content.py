"""Tests for shared documentation content discovery."""

import re
from pathlib import Path

import pytest
from reflex_site_shared.docs import DocsSiteConfig, ExternalDoc, discover_docs


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
    assert pages[1].source_text.startswith("---\ntitle: First Steps\n")


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


def test_discover_docs_publishes_external_documents(tmp_path: Path):
    """Publish Markdown from outside the tree at its virtual location."""
    content_dir = tmp_path / "docs"
    content_dir.mkdir()
    (content_dir / "index.md").write_text("# Home", encoding="utf-8")
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## v1.0.0\n", encoding="utf-8")

    pages = discover_docs(
        DocsSiteConfig(
            content_dir=content_dir,
            external_docs=(
                ExternalDoc(
                    source_path=changelog,
                    relative_path=Path("changelog/index.md"),
                ),
            ),
        )
    )

    assert [page.route for page in pages] == ["/", "/changelog/"]
    changelog_page = pages[1]
    assert changelog_page.title == "Changelog"
    assert changelog_page.source_path == changelog
    assert changelog_page.relative_path == Path("changelog/index.md")
    assert changelog_page.content == "# Changelog\n\n## v1.0.0"


def test_discover_docs_uses_the_external_source_override(tmp_path: Path):
    """Render an external document from explicit Markdown, not the file."""
    content_dir = tmp_path / "docs"
    content_dir.mkdir()
    (content_dir / "index.md").write_text("# Home", encoding="utf-8")
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## v1.0.0\n", encoding="utf-8")

    pages = discover_docs(
        DocsSiteConfig(
            content_dir=content_dir,
            external_docs=(
                ExternalDoc(
                    source_path=changelog,
                    relative_path=Path("changelog/package.md"),
                    source=(
                        "---\ndescription: Released changes.\n---\n\n"
                        "# Package Changelog\n\n## v1.0.0\n"
                    ),
                ),
            ),
            navigation_order=("/changelog/package/", "/"),
        )
    )

    assert [page.route for page in pages] == ["/changelog/package/", "/"]
    changelog_page = pages[0]
    assert changelog_page.title == "Package Changelog"
    assert changelog_page.description == "Released changes."
    assert changelog_page.content == "# Package Changelog\n\n## v1.0.0"
    assert changelog_page.source_text.startswith("---\ndescription: Released changes.")


def test_discover_docs_rejects_external_route_collisions(tmp_path: Path):
    """Refuse to publish an external document over an authored page."""
    content_dir = tmp_path / "docs"
    content_dir.mkdir()
    (content_dir / "changelog.md").write_text("# Changelog", encoding="utf-8")
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog", encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate documentation route"):
        discover_docs(
            DocsSiteConfig(
                content_dir=content_dir,
                external_docs=(
                    ExternalDoc(
                        source_path=changelog,
                        relative_path=Path("changelog.md"),
                    ),
                ),
            )
        )


@pytest.mark.parametrize(
    ("relative_path", "message"),
    [
        (Path("/changelog/index.md"), "must be relative"),
        (Path("changelog/index.txt"), "must be a .md path"),
    ],
)
def test_external_doc_validates_its_virtual_path(relative_path: Path, message: str):
    """Reject virtual paths that cannot become a Markdown route."""
    with pytest.raises(ValueError, match=message):
        ExternalDoc(source_path=Path("CHANGELOG.md"), relative_path=relative_path)


def test_discover_docs_requires_a_directory(tmp_path: Path):
    """Fail clearly when the configured content directory does not exist."""
    content_dir = tmp_path / "missing"

    with pytest.raises(FileNotFoundError, match=re.escape(str(content_dir))):
        discover_docs(DocsSiteConfig(content_dir=content_dir))
