"""Markdown document utilities — YAML frontmatter parsing and file discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.+?)\n---\s*\n(.*)$", re.DOTALL)


@dataclass(kw_only=True)
class MarkdownDocument:
    """A markdown document with YAML frontmatter."""

    metadata: dict[str, Any] = field(default_factory=dict)
    content: str

    @classmethod
    def from_source(cls, source: str) -> MarkdownDocument:
        """Parse a markdown source string with optional YAML frontmatter.

        Returns:
            The parsed document.
        """
        match = re.match(_FRONT_MATTER_RE, source)
        if not match:
            return cls(content=source)
        front_matter = yaml.safe_load(match.group(1)) or {}
        return cls(metadata=front_matter, content=match.group(2))

    @classmethod
    def from_file(cls, path: str | Path) -> MarkdownDocument:
        """Load a markdown document from a file.

        Returns:
            The parsed document.
        """
        text = Path(path).read_text(encoding="utf-8")
        return cls.from_source(text)


def get_md_files(directory: str | Path) -> list[Path]:
    """Recursively find all .md files in a directory.

    Returns:
        Sorted list of .md file paths.
    """
    return sorted(Path(directory).rglob("*.md"))
