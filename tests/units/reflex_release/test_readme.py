"""Tests for reflex_release.readme."""

from __future__ import annotations

from pathlib import Path

import pytest
from reflex_release.config import Config, load_config
from reflex_release.readme import Rewrite, raw_base_url, readme_file, rewrite_links

REPO_URL = "https://github.com/acme/widgets"
SHA = "0123456789abcdef0123456789abcdef01234567"
BLOB = f"{REPO_URL}/blob/{SHA}"
TREE = f"{REPO_URL}/tree/{SHA}"
RAW = f"https://raw.githubusercontent.com/acme/widgets/{SHA}"


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    """Create a repository holding the files the links in these tests point at.

    Args:
        tmp_path: The pytest temporary directory.

    Returns:
        The repository root.
    """
    (tmp_path / "docs" / "images").mkdir(parents=True)
    (tmp_path / "docs" / "guide.md").write_text("guide", encoding="utf-8")
    (tmp_path / "docs" / "my guide.md").write_text("spaces", encoding="utf-8")
    (tmp_path / "docs" / "images" / "logo.png").write_bytes(b"png")
    (tmp_path / "packages" / "widget-core").mkdir(parents=True)
    (tmp_path / "packages" / "widget-core" / "README.md").write_text(
        "sub", encoding="utf-8"
    )
    return tmp_path


def rewrite(root: Path, text: str, readme_path: str = "README.md") -> str:
    """Rewrite a README body against the test repository.

    Args:
        root: The repository root.
        text: The README content.
        readme_path: The README's repo-relative path.

    Returns:
        The rewritten content.
    """
    rewritten, _ = rewrite_links(
        text, repo_url=REPO_URL, sha=SHA, readme_path=readme_path, root=root
    )
    return rewritten


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # A file becomes a blob URL, a directory a tree URL.
        ("[g](docs/guide.md)", f"[g]({BLOB}/docs/guide.md)"),
        ("[d](docs)", f"[d]({TREE}/docs)"),
        ("[d](docs/)", f"[d]({TREE}/docs)"),
        ("[g](./docs/guide.md)", f"[g]({BLOB}/docs/guide.md)"),
        # Media is served raw, whether it is written as an image or not: a blob
        # URL is an HTML page, which does not render inside a description.
        ("![l](docs/images/logo.png)", f"![l]({RAW}/docs/images/logo.png)"),
        ("[l](docs/images/logo.png)", f"[l]({RAW}/docs/images/logo.png)"),
        # The outer link of a badge is a link, not an image.
        (
            "[![l](docs/images/logo.png)](docs/guide.md)",
            f"[![l]({RAW}/docs/images/logo.png)]({BLOB}/docs/guide.md)",
        ),
        # Titles and angle-bracket destinations survive the rewrite.
        ('[g](docs/guide.md "Guide")', f'[g]({BLOB}/docs/guide.md "Guide")'),
        ("[g](<docs/my guide.md>)", f"[g](<{BLOB}/docs/my%20guide.md>)"),
        ("[g](docs/my%20guide.md)", f"[g]({BLOB}/docs/my%20guide.md)"),
        # Fragments are carried over, including a link to a heading of the
        # README itself — PyPI renders no heading anchors, GitHub does.
        ("[g](docs/guide.md#usage)", f"[g]({BLOB}/docs/guide.md#usage)"),
        ("[s](#security)", f"[s]({BLOB}/README.md#security)"),
        # A link to the repository itself keeps the tree URL path-free.
        ("[r](.)", f"[r]({TREE})"),
        # Reference definitions are destinations too.
        ("[g]: docs/guide.md", f"[g]: {BLOB}/docs/guide.md"),
        ('   [g]: <docs/guide.md> "Guide"', f'   [g]: <{BLOB}/docs/guide.md> "Guide"'),
        # HTML is common in READMEs and equally relative.
        (
            '<img src="docs/images/logo.png" width="30">',
            f'<img src="{RAW}/docs/images/logo.png" width="30">',
        ),
        (
            "<a href='docs/guide.md'>g</a>",
            f"<a href='{BLOB}/docs/guide.md'>g</a>",
        ),
        (
            '<video poster="docs/images/logo.png" src="docs/guide.md"></video>',
            (
                f'<video poster="{RAW}/docs/images/logo.png" '
                f'src="{RAW}/docs/guide.md"></video>'
            ),
        ),
    ],
)
def test_relative_links_are_pinned_to_the_commit(
    docs: Path, source: str, expected: str
) -> None:
    assert rewrite(docs, source) == expected


@pytest.mark.parametrize(
    "source",
    [
        "[g](https://example.com/docs)",
        "[g](HTTPS://example.com/docs)",
        "[m](mailto:maintainers@example.com)",
        "[c](//cdn.example.com/logo.png)",
        # GitHub resolves a site-absolute path against the server, not the
        # repository, so there is no relative link to preserve.
        "[g](/docs/guide.md)",
        "[g]()",
        '<a href="https://example.com">e</a>',
    ],
)
def test_absolute_destinations_are_left_alone(docs: Path, source: str) -> None:
    assert rewrite(docs, source) == source


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        ("[g](docs/missing.md)", "no such path in the repository"),
        ("[g](../outside/guide.md)", "resolves outside the repository"),
    ],
)
def test_unresolvable_destinations_are_reported_not_rewritten(
    docs: Path, source: str, reason: str
) -> None:
    rewritten, rewrites = rewrite_links(
        source, repo_url=REPO_URL, sha=SHA, readme_path="README.md", root=docs
    )
    assert rewritten == source
    assert [entry.reason for entry in rewrites] == [reason]


def test_footnote_definitions_are_not_reference_definitions(docs: Path) -> None:
    """``[^1]: text`` opens with prose, not with a destination."""
    source = "[^1]: docs/guide.md explains it\n"
    assert rewrite(docs, source) == source


def test_paths_resolve_against_the_readme_not_the_repository_root(docs: Path) -> None:
    source = "[g](../../docs/guide.md) [own](README.md) [s](#top)"
    readme = "packages/widget-core/README.md"
    assert rewrite(docs, source, readme) == (
        f"[g]({BLOB}/docs/guide.md) "
        f"[own]({BLOB}/packages/widget-core/README.md) "
        f"[s]({BLOB}/packages/widget-core/README.md#top)"
    )


def test_fenced_code_blocks_keep_their_examples(docs: Path) -> None:
    source = (
        "[g](docs/guide.md)\n\n"
        "```markdown\n"
        "[g](docs/guide.md)\n"
        "```\n\n"
        "~~~\n"
        '<img src="docs/images/logo.png">\n'
        "~~~\n\n"
        "[g](docs/guide.md)\n"
    )
    rewritten = rewrite(docs, source)
    assert rewritten.count(f"[g]({BLOB}/docs/guide.md)") == 2
    assert rewritten.count("[g](docs/guide.md)") == 1
    assert '<img src="docs/images/logo.png">' in rewritten


def test_a_fence_inside_a_fenced_block_does_not_end_it(docs: Path) -> None:
    source = "````\n```\n[g](docs/guide.md)\n```\n````\n[g](docs/guide.md)\n"
    assert rewrite(docs, source) == (
        f"````\n```\n[g](docs/guide.md)\n```\n````\n[g]({BLOB}/docs/guide.md)\n"
    )


def test_an_unclosed_fence_runs_to_the_end_of_the_file(docs: Path) -> None:
    source = "```\n[g](docs/guide.md)\n"
    assert rewrite(docs, source) == source


def test_every_relative_link_is_reported(docs: Path) -> None:
    _, rewrites = rewrite_links(
        "[g](docs/guide.md) [h](https://example.com) [i](docs/missing.md)",
        repo_url=REPO_URL,
        sha=SHA,
        readme_path="README.md",
        root=docs,
    )
    assert rewrites == [
        Rewrite("docs/guide.md", url=f"{BLOB}/docs/guide.md"),
        Rewrite("docs/missing.md", reason="no such path in the repository"),
    ]


def test_raw_base_url_serves_enterprise_content_from_the_repository() -> None:
    assert raw_base_url(REPO_URL) == "https://raw.githubusercontent.com/acme/widgets"
    assert (
        raw_base_url("https://github.example.com/acme/widgets")
        == "https://github.example.com/acme/widgets/raw"
    )


def test_readme_file_reads_the_declared_readme(repo: Path, config: Config) -> None:
    (repo / "DESCRIPTION.md").write_text("hi", encoding="utf-8")
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            "\ndependencies", '\nreadme = "DESCRIPTION.md"\ndependencies'
        ),
        encoding="utf-8",
    )
    assert readme_file(load_config(repo), "mypkg") == repo / "DESCRIPTION.md"


def test_readme_file_reads_the_table_form(repo: Path) -> None:
    (repo / "DESCRIPTION.md").write_text("hi", encoding="utf-8")
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            "\ndependencies",
            '\nreadme = {file = "DESCRIPTION.md", content-type = "text/markdown"}'
            "\ndependencies",
        ),
        encoding="utf-8",
    )
    assert readme_file(load_config(repo), "mypkg") == repo / "DESCRIPTION.md"


def test_readme_file_falls_back_to_readme_md(config: Config, repo: Path) -> None:
    """A package with dynamic metadata declares no readme, but still has one."""
    assert readme_file(config, "widget-core") is None
    readme = repo / "packages" / "widget-core" / "README.md"
    readme.write_text("hi", encoding="utf-8")
    assert readme_file(config, "widget-core") == readme


def test_readme_file_ignores_a_declared_file_that_is_missing(repo: Path) -> None:
    (repo / "README.md").write_text("hi", encoding="utf-8")
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            "\ndependencies", '\nreadme = "DESCRIPTION.md"\ndependencies'
        ),
        encoding="utf-8",
    )
    assert readme_file(load_config(repo), "mypkg") is None
