"""Rewriting a package README's relative links into permanent GitHub URLs.

PyPI renders the README as a standalone page, so every relative link that works
on GitHub — to sibling documentation, to an image, to another package in the
monorepo — resolves against ``pypi.org`` there and 404s. The publish workflow
rewrites them into absolute URLs pinned at the commit being released, in the
build tree only: the checkout is thrown away after the build, so the repository
keeps its relative links and only the published description carries permalinks.

Pinning the commit rather than a branch is what makes them permanent. A reader
who opens the 1.2.3 description a year later follows its links to the files as
they were in 1.2.3, not to a default branch that has since moved, renamed the
file, or deleted it.
"""

from __future__ import annotations

import dataclasses
import posixpath
import re
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote, unquote

from .config import Config, load_pyproject

#: Suffixes of the README formats this module knows how to rewrite.
MARKDOWN_SUFFIXES = frozenset({".md", ".markdown"})

#: Destinations that already resolve on their own and are left alone: anything
#: carrying a scheme (``https:``, ``mailto:``), protocol-relative URLs, and
#: site-absolute paths — which GitHub itself resolves against the server root
#: rather than the repository, so there is nothing to preserve.
_ABSOLUTE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*:|//|/")

#: Extensions served as media rather than rendered as a page, so a link to one
#: goes to the raw file even when it is not written as an image.
_MEDIA_SUFFIXES = frozenset({
    ".apng",
    ".avif",
    ".bmp",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".mp3",
    ".mp4",
    ".ogg",
    ".png",
    ".svg",
    ".webm",
    ".webp",
})

#: HTML tags whose ``src`` is media rather than a page to navigate to.
_MEDIA_TAGS = frozenset({"audio", "embed", "img", "source", "track", "video"})

#: HTML attributes holding a single URL. ``srcset`` is deliberately absent: its
#: comma-separated candidate syntax is not a URL.
_URL_ATTRIBUTES = ("href", "poster", "src")

#: The destination of a markdown inline link or image, anchored on the ``](``
#: that follows the link text so nested brackets in the text do not matter.
_INLINE_LINK = re.compile(
    r"""\]\(\s*
        (?P<dest><[^<>\n]*>|[^\s()]*)
        (?P<title>\s+(?:"[^"]*"|'[^']*'|\([^()]*\)))?
        \s*\)""",
    re.VERBOSE,
)

#: A link reference definition, e.g. ``[docs]: docs/index.md "Title"``. A
#: footnote definition (``[^1]: ...``) opens with prose, not a destination.
_REFERENCE = re.compile(
    r"""^(?P<prefix>[ ]{0,3}\[(?!\^)[^\]\n]+\]:[ \t]*)
        (?P<dest><[^<>\n]*>|\S+)""",
    re.MULTILINE | re.VERBOSE,
)

#: An HTML start tag, whose attributes are rewritten one by one.
_HTML_TAG = re.compile(r"<(?P<tag>[a-zA-Z][-\w]*)(?P<attrs>[^<>]*)>")

_HTML_ATTRIBUTE = re.compile(
    rf"""\b(?P<attr>{"|".join(_URL_ATTRIBUTES)})\s*=\s*
        (?P<quote>["'])(?P<dest>[^"']*)(?P=quote)""",
    re.IGNORECASE | re.VERBOSE,
)

#: The opening or closing line of a fenced code block.
_FENCE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})")

_GITHUB_COM = "https://github.com"


@dataclasses.dataclass(frozen=True)
class Rewrite:
    """One relative link the rewriter looked at, and what became of it.

    Attributes:
        target: The destination as it is written in the README.
        url: The absolute URL it was rewritten to, or None when it was left
            alone.
        reason: Why it was left alone; empty when it was rewritten.
    """

    target: str
    url: str | None = None
    reason: str = ""


def readme_file(config: Config, package: str) -> Path | None:
    """Return the README a package publishes as its long description.

    Args:
        config: The repository configuration.
        package: The package name.

    Returns:
        The declared ``[project] readme`` path, ``README.md`` when the package
        declares none (the dynamic-metadata case), or None when neither exists.
    """
    directory = config.package_path(package)
    project = load_pyproject(directory / "pyproject.toml").get("project", {})
    readme = project.get("readme")
    if isinstance(readme, dict):
        # PEP 621 allows {file = ...} and {text = ...}; only a file is on disk.
        readme = readme.get("file")
    path = directory / readme if isinstance(readme, str) and readme else None
    if path is None:
        path = directory / "README.md"
    return path if path.is_file() else None


def raw_base_url(repo_url: str) -> str:
    """Return the base URL serving a repository's file contents verbatim.

    Args:
        repo_url: The repository's web URL.

    Returns:
        The prefix a ``<sha>/<path>`` suffix turns into a raw file URL.
    """
    if repo_url.startswith(f"{_GITHUB_COM}/"):
        return f"https://raw.githubusercontent.com{repo_url[len(_GITHUB_COM) :]}"
    # GitHub Enterprise Server serves raw content under the repository itself.
    return f"{repo_url}/raw"


def _repo_path(target: str, base_dir: str) -> str | None:
    """Resolve a relative link target to a repo-relative path.

    Args:
        target: The path part of the destination, as written (percent-encoded).
        base_dir: The repo-relative directory holding the README.

    Returns:
        The normalized POSIX path, or None when it escapes the repository.
    """
    resolved = posixpath.normpath(posixpath.join(base_dir, unquote(target)))
    if resolved == ".." or resolved.startswith("../"):
        return None
    return resolved


def _is_image(text: str, close: int) -> bool:
    """Return whether the markdown link closing at an index is an image.

    Args:
        text: The document being rewritten.
        close: Index of the ``]`` that ends the link text.

    Returns:
        True when the matching ``[`` is preceded by ``!``. Nesting is counted,
        so the outer link of a badge (``[![alt](img)](page)``) is not mistaken
        for an image.
    """
    depth = 0
    for index in range(close, -1, -1):
        char = text[index]
        if char == "]":
            depth += 1
        elif char == "[":
            depth -= 1
            if depth == 0:
                return index > 0 and text[index - 1] == "!"
    return False


def _code_segments(text: str) -> list[tuple[bool, str]]:
    """Split a markdown document into prose and fenced-code segments.

    Args:
        text: The document.

    Returns:
        ``(is_code, segment)`` pairs whose concatenation is the input. Fenced
        blocks are held out so a link written inside a usage example is not
        rewritten into something that no longer demonstrates anything.
    """
    segments: list[tuple[bool, str]] = []
    lines: list[str] = []
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        opening = _FENCE.match(line)
        if fence is None:
            if opening is None:
                lines.append(line)
                continue
            segments.append((False, "".join(lines)))
            lines = [line]
            fence = opening["fence"]
            continue
        lines.append(line)
        stripped = line.strip()
        if stripped == fence[0] * len(stripped) and len(stripped) >= len(fence):
            segments.append((True, "".join(lines)))
            lines = []
            fence = None
    # An unclosed fence runs to the end of the file, exactly as it renders.
    segments.append((fence is not None, "".join(lines)))
    return segments


def _rewrite_segment(segment: str, absolute: Callable[[str, bool], str | None]) -> str:
    """Rewrite every relative destination in one prose segment.

    Args:
        segment: The markdown to rewrite.
        absolute: Maps a destination and whether it is media to its absolute
            URL, or None to leave the destination alone.

    Returns:
        The rewritten segment.
    """

    def replace(dest: str, media: bool) -> str | None:
        """Return the replacement for one destination.

        Args:
            dest: The destination as written, possibly in angle brackets.
            media: Whether it is referenced as media.

        Returns:
            The replacement text, or None to leave it alone.
        """
        wrapped = dest.startswith("<") and dest.endswith(">")
        inner = dest[1:-1] if wrapped else dest
        if not inner or _ABSOLUTE.match(inner):
            return None
        url = absolute(inner, media)
        return None if url is None else (f"<{url}>" if wrapped else url)

    def inline(match: re.Match[str]) -> str:
        """Rewrite an inline link or image.

        Args:
            match: The ``](dest)`` match.

        Returns:
            The replacement text.
        """
        url = replace(match["dest"], _is_image(segment, match.start()))
        return match[0] if url is None else f"]({url}{match['title'] or ''})"

    def reference(match: re.Match[str]) -> str:
        """Rewrite a link reference definition.

        Args:
            match: The definition match.

        Returns:
            The replacement text.
        """
        # Whether the label is used as an image is only known at the use site,
        # so the destination itself decides (a .png is media wherever it is
        # referenced from).
        url = replace(match["dest"], False)
        return match[0] if url is None else f"{match['prefix']}{url}"

    def html(match: re.Match[str]) -> str:
        """Rewrite the URL attributes of one HTML start tag.

        Args:
            match: The tag match.

        Returns:
            The replacement text.
        """
        media = match["tag"].lower() in _MEDIA_TAGS

        def attribute(attr: re.Match[str]) -> str:
            """Rewrite one URL-valued attribute.

            Args:
                attr: The attribute match.

            Returns:
                The replacement text.
            """
            url = replace(attr["dest"], media or attr["attr"].lower() == "poster")
            if url is None:
                return attr[0]
            return f"{attr['attr']}={attr['quote']}{url}{attr['quote']}"

        return f"<{match['tag']}{_HTML_ATTRIBUTE.sub(attribute, match['attrs'])}>"

    rewritten = _INLINE_LINK.sub(inline, segment)
    rewritten = _REFERENCE.sub(reference, rewritten)
    return _HTML_TAG.sub(html, rewritten)


def rewrite_links(
    text: str, *, repo_url: str, sha: str, readme_path: str, root: Path
) -> tuple[str, list[Rewrite]]:
    """Rewrite a README's relative links to URLs pinned at one commit.

    A destination is rewritten only when it resolves to a path that exists in
    the checkout: a file becomes a ``blob`` URL (``raw`` when it is referenced
    as an image or is itself media), a directory a ``tree`` URL. Anything else
    — an absolute URL, a path outside the repository, a target that is not
    there — is left exactly as written and reported instead.

    Args:
        text: The README content.
        repo_url: The repository's web URL, e.g. ``https://github.com/o/r``.
        sha: The commit to pin the links to.
        readme_path: The README's repo-relative POSIX path, which relative
            destinations resolve against.
        root: The repository root, used to classify link targets.

    Returns:
        The rewritten content and one :class:`Rewrite` per relative link found.
    """
    base_dir = posixpath.dirname(readme_path)
    raw_base = raw_base_url(repo_url)
    rewrites: list[Rewrite] = []

    def absolute(dest: str, media: bool) -> str | None:
        """Return the pinned URL for one relative destination.

        Args:
            dest: The destination as written in the README.
            media: Whether it is referenced as an image or other media.

        Returns:
            The absolute URL, or None when the destination is left alone.
        """
        target, separator, fragment = dest.partition("#")
        if not target:
            # A same-page anchor. PyPI renders the description without heading
            # anchors, so the reader is sent to the README on GitHub, where the
            # fragment resolves.
            path, kind = readme_path, "blob"
        else:
            resolved = _repo_path(target, base_dir)
            if resolved is None:
                rewrites.append(Rewrite(dest, reason="resolves outside the repository"))
                return None
            full = root / resolved
            if full.is_dir():
                kind = "tree"
            elif full.is_file():
                kind = (
                    "raw"
                    if media
                    or posixpath.splitext(resolved)[1].lower() in _MEDIA_SUFFIXES
                    else "blob"
                )
            else:
                rewrites.append(Rewrite(dest, reason="no such path in the repository"))
                return None
            path = resolved
        prefix = raw_base if kind == "raw" else f"{repo_url}/{kind}"
        # A link to the repository root itself has no path component.
        suffix = "" if path == "." else f"/{quote(path)}"
        url = f"{prefix}/{sha}{suffix}{separator}{fragment}"
        rewrites.append(Rewrite(dest, url=url))
        return url

    rewritten = "".join(
        segment if is_code else _rewrite_segment(segment, absolute)
        for is_code, segment in _code_segments(text)
    )
    return rewritten, rewrites
