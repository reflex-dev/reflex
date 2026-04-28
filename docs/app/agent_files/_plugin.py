import re
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from reflex.constants import Dirs
from reflex_base.plugins import CommonContext, Plugin
from typing_extensions import Unpack

MCP_DOC_PATHS = {
    "ai/integrations/mcp-installation.md",
    "ai/integrations/mcp-overview.md",
}
AI_ONBOARDING_DOC_PATHS = {
    "ai/integrations/ai-onboarding.md",
}
MCP_DOC_ORDER = {
    "ai/integrations/mcp-overview.md": 0,
    "ai/integrations/mcp-installation.md": 1,
}
SKILLS_DOC_PATHS = {
    "ai/integrations/skills.md",
}

LLMS_FULL_INTRO = """\
# Reflex Documentation
Source: {docs_home_url}

This file stitches together the full Reflex documentation as Markdown for AI agents and LLM indexing.

For a navigable index with links to individual docs pages, see [llms.txt]({llms_txt_url}).
"""


@dataclass(frozen=True)
class MarkdownFileEntry:
    """A generated markdown file and its llms.txt metadata."""

    url_path: Path
    source_path: Path
    title: str
    section: str


def _format_title(value: str) -> str:
    """Format a route or file segment as a title."""
    words = re.split(r"[-_\s]+", value)
    acronyms = {
        "ag": "AG",
        "ai": "AI",
        "api": "API",
        "cli": "CLI",
        "css": "CSS",
        "html": "HTML",
        "ide": "IDE",
        "mcp": "MCP",
        "ui": "UI",
        "url": "URL",
        "urls": "URLs",
    }
    return " ".join(acronyms.get(word.lower(), word.capitalize()) for word in words)


def _extract_markdown_title(source: str) -> str | None:
    """Extract the first top-level heading from markdown source."""
    in_frontmatter = source.startswith("---\n")
    in_code_block = False

    for line in source.splitlines():
        stripped = line.strip()
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if stripped.startswith("# "):
            return stripped.removeprefix("# ").strip()
    return None


def _llms_url_for_path(url_path: Path) -> str:
    """Return the public URL for a generated markdown asset."""
    from reflex_base.config import get_config

    config = get_config()
    deploy_url = config.deploy_url.removesuffix("/") if config.deploy_url else ""
    frontend_path = (config.frontend_path or "").strip("/")
    base_url = deploy_url
    if frontend_path:
        base_url = f"{base_url}/{frontend_path}" if base_url else f"/{frontend_path}"
    return (
        f"{base_url}/{url_path.as_posix()}" if base_url else f"/{url_path.as_posix()}"
    )


def _docs_home_url() -> str:
    """Return the public URL for the docs home."""
    from reflex_base.config import get_config

    config = get_config()
    deploy_url = config.deploy_url.removesuffix("/") if config.deploy_url else ""
    frontend_path = (config.frontend_path or "").strip("/")
    if deploy_url and frontend_path:
        return f"{deploy_url}/{frontend_path}/"
    if deploy_url:
        return f"{deploy_url}/"
    if frontend_path:
        return f"/{frontend_path}/"
    return "/"


def _strip_first_heading(source: str) -> str:
    """Remove the first top-level markdown heading from a page body."""
    lines = source.strip().splitlines()
    in_frontmatter = bool(lines) and lines[0].strip() == "---"
    in_code_block = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if in_frontmatter:
            if stripped == "---" and index > 0:
                in_frontmatter = False
            continue
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if stripped.startswith("# "):
            return "\n".join([*lines[:index], *lines[index + 1 :]]).strip()
    return source.strip()


def _include_in_llms_txt(markdown_file: MarkdownFileEntry) -> bool:
    """Return whether a markdown file should appear in llms.txt."""
    path = markdown_file.url_path.as_posix()
    return (
        path in MCP_DOC_PATHS
        or path in AI_ONBOARDING_DOC_PATHS
        or path in SKILLS_DOC_PATHS
        or not path.startswith("ai/")
        or path.startswith("ai/overview/")
    )


def _section_for_path(url_path: Path) -> str:
    """Return the llms.txt section for a generated markdown asset."""
    path = url_path.as_posix()
    if path in AI_ONBOARDING_DOC_PATHS:
        return "AI Onboarding"
    if path in MCP_DOC_PATHS:
        return "MCP"
    if path in SKILLS_DOC_PATHS:
        return "Skills"
    if path.startswith("ai/"):
        return "AI Builder"
    return _format_title(path.split("/", maxsplit=1)[0])


def _ordered_sections(
    sections: OrderedDict[str, list[MarkdownFileEntry]],
) -> list[str]:
    """Return sections in display order."""
    ordered_sections = list(sections)
    if "AI Builder" in sections and "MCP" in sections:
        ordered_sections.remove("MCP")
        ordered_sections.insert(ordered_sections.index("AI Builder") + 1, "MCP")
    if "AI Builder" in sections and "AI Onboarding" in sections:
        ordered_sections.remove("AI Onboarding")
        ordered_sections.insert(
            ordered_sections.index("AI Builder") + 1, "AI Onboarding"
        )
    if "MCP" in sections and "Skills" in sections:
        ordered_sections.remove("Skills")
        ordered_sections.insert(ordered_sections.index("MCP") + 1, "Skills")
    elif "AI Builder" in sections and "Skills" in sections:
        ordered_sections.remove("Skills")
        ordered_sections.insert(ordered_sections.index("AI Builder") + 1, "Skills")
    return ordered_sections


def _ordered_entries(
    section: str, entries: list[MarkdownFileEntry]
) -> list[MarkdownFileEntry]:
    """Return entries in display order within a section."""
    if section == "MCP":
        return sorted(
            entries,
            key=lambda entry: MCP_DOC_ORDER[entry.url_path.as_posix()],
        )
    return entries


def generate_markdown_file_entries() -> tuple[MarkdownFileEntry, ...]:
    """Generate the markdown files exposed to agents and llms.txt."""
    from reflex_docs.pages.docs import (
        all_docs,
        doc_route_from_path,
        doc_title_from_path,
        manual_titles,
    )
    from reflex_docs.whitelist import _check_whitelisted_path

    return tuple([
        MarkdownFileEntry(
            url_path=Path(route.strip("/") + ".md"),
            source_path=resolved,
            title=manual_titles.get(
                virtual_path,
                _extract_markdown_title(resolved.read_text(encoding="utf-8"))
                or _format_title(doc_title_from_path(virtual_path)),
            ),
            section=_section_for_path(Path(route.strip("/") + ".md")),
        )
        for virtual_path, source_path in sorted(all_docs.items())
        if not virtual_path.endswith(("-style.md", "-ll.md"))
        if _check_whitelisted_path(route := doc_route_from_path(virtual_path))
        if (resolved := Path(source_path)).is_file()
    ])


def generate_markdown_files() -> tuple[tuple[Path, str | bytes], ...]:
    """Generate markdown asset contents for agent-friendly docs pages."""
    return tuple(
        (entry.url_path, entry.source_path.read_bytes())
        for entry in generate_markdown_file_entries()
    )


def generate_llms_txt(
    markdown_files: Sequence[MarkdownFileEntry],
) -> tuple[Path, str]:
    """Generate an llms.txt index grouped by docs section."""
    sections: OrderedDict[str, list[MarkdownFileEntry]] = OrderedDict()
    for markdown_file in markdown_files:
        if not _include_in_llms_txt(markdown_file):
            continue
        sections.setdefault(markdown_file.section, []).append(markdown_file)

    lines = ["# Reflex", "", "## Docs", ""]
    for section in _ordered_sections(sections):
        entries = _ordered_entries(section, sections[section])
        lines.extend([f"### {section}", ""])
        lines.extend(
            f"- [{entry.title}]({_llms_url_for_path(entry.url_path)})"
            for entry in entries
        )
        lines.append("")

    return (Path("llms.txt"), "\n".join(lines).rstrip() + "\n")


def generate_llms_full_txt(
    markdown_files: Sequence[MarkdownFileEntry],
) -> tuple[Path, str]:
    """Generate an llms-full.txt by stitching all docs markdown together."""
    lines = [
        LLMS_FULL_INTRO.format(
            docs_home_url=_docs_home_url(),
            llms_txt_url=_llms_url_for_path(Path("llms.txt")),
        ).strip(),
        "",
    ]
    for entry in markdown_files:
        source = _strip_first_heading(entry.source_path.read_text(encoding="utf-8"))
        lines.extend([
            f"# {entry.title}",
            f"Source: {_llms_url_for_path(entry.url_path)}",
            "",
            source,
            "",
        ])

    return (Path("llms-full.txt"), "\n".join(lines).rstrip() + "\n")


def generate_agent_files() -> tuple[tuple[Path, str | bytes], ...]:
    markdown_file_entries = generate_markdown_file_entries()
    markdown_files = tuple(
        (entry.url_path, entry.source_path.read_bytes())
        for entry in markdown_file_entries
    )
    return (
        *markdown_files,
        generate_llms_txt(markdown_file_entries),
        generate_llms_full_txt(markdown_file_entries),
    )


class AgentFilesPlugin(Plugin):
    def get_static_assets(
        self, **context: Unpack[CommonContext]
    ) -> Sequence[tuple[Path, str | bytes]]:
        return [
            (Dirs.PUBLIC / path, content) for path, content in generate_agent_files()
        ]
