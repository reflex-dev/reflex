"""Validate /docs/* markdown links against the generated sitemap.xml.

For every .md file under the docs tree, find markdown links of the form
`[text](/docs/...)` and verify:

1. The URL path contains no underscores (URLs use hyphens).
2. After stripping the `/docs` prefix, the path exists in sitemap.xml.

Run after building the frontend so .web/public/sitemap.xml is present, e.g.:

    cd docs/app
    uv run reflex export --frontend-only --no-zip
    uv run python scripts/check_doc_links.py
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

LINK_RE = re.compile(r"\]\(\s*(/docs(?=[/)#?\s])[^)]*?)(?:\s+\"[^\"]*\")?\s*\)")
SITEMAP_NS = {"sm": "https://www.sitemaps.org/schemas/sitemap/0.9"}
SKIP_DIRS = {".web", "node_modules", "__pycache__", ".git", ".venv", "dist", "build"}


def _normalize(path: str) -> str:
    path = path.split("#", 1)[0].split("?", 1)[0]
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/") or "/"


def _strip_docs_prefix(path: str) -> str:
    """Drop a leading `/docs` segment so both deployment styles compare equal."""
    if path == "/docs":
        return "/"
    if path.startswith("/docs/"):
        return path[len("/docs") :]
    return path


def load_sitemap_paths(sitemap_path: Path) -> set[str]:
    """Return the set of normalized URL paths declared in sitemap.xml."""
    tree = ET.parse(sitemap_path)
    paths: set[str] = set()
    for loc in tree.getroot().findall("sm:url/sm:loc", SITEMAP_NS):
        if loc.text is None:
            continue
        path = urlparse(loc.text.strip()).path
        paths.add(_strip_docs_prefix(_normalize(path)))
    return paths


def iter_md_files(md_root: Path):
    """Yield .md files under md_root, skipping build/vendor directories."""
    for path in md_root.rglob("*.md"):
        if any(part in SKIP_DIRS for part in path.relative_to(md_root).parts):
            continue
        yield path


def iter_md_links(md_root: Path):
    """Yield (file, line_no, raw_url) for every /docs/* markdown link."""
    for md_file in iter_md_files(md_root):
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for match in LINK_RE.finditer(line):
                yield md_file, line_no, match.group(1)


def check(md_root: Path, sitemap_path: Path) -> list[str]:
    """Return a list of human-readable error strings."""
    if not sitemap_path.is_file():
        return [
            f"sitemap.xml not found at {sitemap_path}. "
            "Build the frontend first (e.g. `uv run reflex export --frontend-only --no-zip`)."
        ]

    valid_paths = load_sitemap_paths(sitemap_path)
    print(f"Loaded {len(valid_paths)} URLs from sitemap {sitemap_path}")

    md_files = list(iter_md_files(md_root))
    if not md_files:
        return [f"No .md files found under {md_root}. Check --md-root."]
    print(f"Scanning {len(md_files)} markdown file(s) under {md_root}")

    errors: list[str] = []
    links_checked = 0
    for md_file, line_no, raw in iter_md_links(md_root):
        links_checked += 1
        location = f"{md_file}:{line_no}"
        path_only = raw.split("#", 1)[0].split("?", 1)[0]
        sitemap_key = _strip_docs_prefix(_normalize(raw))
        ok = sitemap_key in valid_paths and "_" not in path_only
        print(f"  [{'OK  ' if ok else 'FAIL'}] {location} -> {raw}")

        if "_" in path_only:
            errors.append(
                f"{location}: link contains an underscore (use hyphens): {raw!r}"
            )
        if sitemap_key not in valid_paths:
            errors.append(
                f"{location}: {raw!r} -> {sitemap_key!r} not found in sitemap"
            )

    print(f"Checked {links_checked} /docs link(s) across {len(md_files)} file(s).")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    here = Path(__file__).resolve().parent
    parser.add_argument(
        "--md-root",
        type=Path,
        default=here.parent.parent,
        help="Root directory containing .md docs (default: ../..).",
    )
    parser.add_argument(
        "--sitemap",
        type=Path,
        default=here.parent / ".web" / "public" / "sitemap.xml",
        help="Path to sitemap.xml (default: ../.web/public/sitemap.xml).",
    )
    args = parser.parse_args()

    errors = check(args.md_root.resolve(), args.sitemap.resolve())
    if errors:
        print(f"Found {len(errors)} broken /docs link(s):", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1
    print("All /docs links resolve against sitemap.xml.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
