"""Tests for agent-facing static file generation."""

from pathlib import Path
from types import SimpleNamespace

from agent_files._plugin import (
    MarkdownFileEntry,
    generate_llms_full_txt,
    generate_llms_txt,
)


def test_generate_llms_txt_groups_docs_at_public_root(monkeypatch):
    """The docs mount exposes public-root llms.txt as /docs/llms.txt."""
    monkeypatch.setattr(
        "reflex_base.config.get_config",
        lambda: SimpleNamespace(
            deploy_url="https://reflex.dev",
            frontend_path="/docs",
        ),
    )

    path, content = generate_llms_txt([
        MarkdownFileEntry(
            url_path=Path("components/props.md"),
            source_path=Path("docs/components/props.md"),
            title="Props",
            section="Components",
        ),
        MarkdownFileEntry(
            url_path=Path("components/rendering-iterables.md"),
            source_path=Path("docs/components/rendering_iterables.md"),
            title="Rendering Iterables",
            section="Components",
        ),
        MarkdownFileEntry(
            url_path=Path("state/overview.md"),
            source_path=Path("docs/state/overview.md"),
            title="State Overview",
            section="State",
        ),
        MarkdownFileEntry(
            url_path=Path("ai/overview/best-practices.md"),
            source_path=Path("docs/ai_builder/overview/best_practices.md"),
            title="Reflex Build: Best Practices",
            section="AI Builder",
        ),
        MarkdownFileEntry(
            url_path=Path("ai/integrations/resend.md"),
            source_path=Path("docs/ai_builder/integrations/resend.md"),
            title="Resend Integration",
            section="AI Builder",
        ),
        MarkdownFileEntry(
            url_path=Path("ai/integrations/mcp-overview.md"),
            source_path=Path("docs/ai_builder/integrations/mcp_overview.md"),
            title="Overview",
            section="MCP",
        ),
        MarkdownFileEntry(
            url_path=Path("ai/integrations/ai-onboarding.md"),
            source_path=Path("docs/ai_builder/integrations/ai_onboarding.md"),
            title="AI Onboarding",
            section="AI Onboarding",
        ),
        MarkdownFileEntry(
            url_path=Path("ai/integrations/mcp-installation.md"),
            source_path=Path("docs/ai_builder/integrations/mcp_installation.md"),
            title="Installation",
            section="MCP",
        ),
        MarkdownFileEntry(
            url_path=Path("ai/integrations/skills.md"),
            source_path=Path("docs/ai_builder/integrations/skills.md"),
            title="Skills",
            section="Skills",
        ),
        MarkdownFileEntry(
            url_path=Path("ai/features/ide.md"),
            source_path=Path("docs/ai_builder/features/ide.md"),
            title="Reflex Build IDE",
            section="AI Builder",
        ),
    ])

    assert path == Path("llms.txt")
    assert content.startswith("# Reflex\n\n## Docs\n\n")
    assert "### Components\n\n" in content
    assert "- [Props](https://reflex.dev/docs/components/props.md)" in content
    assert (
        "- [Rendering Iterables](https://reflex.dev/docs/components/rendering-iterables.md)"
        in content
    )
    assert "### State\n\n" in content
    assert "- [State Overview](https://reflex.dev/docs/state/overview.md)" in content
    assert "### AI Builder\n\n" in content
    assert (
        "- [Reflex Build: Best Practices](https://reflex.dev/docs/ai/overview/best-practices.md)"
        in content
    )
    assert "Resend Integration" not in content
    assert "Reflex Build IDE" not in content
    assert "### AI Onboarding\n\n" in content
    assert (
        "- [AI Onboarding](https://reflex.dev/docs/ai/integrations/ai-onboarding.md)"
        in content
    )
    assert "### MCP\n\n" in content
    assert (
        "- [Overview](https://reflex.dev/docs/ai/integrations/mcp-overview.md)"
        in content
    )
    assert (
        "- [Installation](https://reflex.dev/docs/ai/integrations/mcp-installation.md)"
        in content
    )
    assert "### Skills\n\n" in content
    assert "- [Skills](https://reflex.dev/docs/ai/integrations/skills.md)" in content
    assert content.index("### AI Builder") < content.index("### AI Onboarding")
    assert content.index("### AI Onboarding") < content.index("### MCP")
    assert content.index("### MCP") < content.index("### Skills")
    assert content.index("mcp-overview.md") < content.index("mcp-installation.md")


def test_generate_llms_full_txt_stitches_markdown_docs(monkeypatch, tmp_path):
    """llms-full.txt contains full Markdown page bodies with source URLs."""
    monkeypatch.setattr(
        "reflex_base.config.get_config",
        lambda: SimpleNamespace(
            deploy_url="https://reflex.dev",
            frontend_path="/docs",
        ),
    )
    introduction = tmp_path / "introduction.md"
    introduction.write_text(
        "# Introduction\n\nBuild full-stack apps in Python.\n",
        encoding="utf-8",
    )
    props = tmp_path / "props.md"
    props.write_text(
        "# Props\n\nUse props to configure components.\n",
        encoding="utf-8",
    )

    path, content = generate_llms_full_txt([
        MarkdownFileEntry(
            url_path=Path("getting-started/introduction.md"),
            source_path=introduction,
            title="Introduction",
            section="Getting Started",
        ),
        MarkdownFileEntry(
            url_path=Path("components/props.md"),
            source_path=props,
            title="Props",
            section="Components",
        ),
    ])

    assert path == Path("llms-full.txt")
    assert content.startswith(
        "# Reflex Documentation\n"
        "Source: https://reflex.dev/docs/\n\n"
        "This file stitches together the full Reflex documentation as Markdown"
    )
    assert "[llms.txt](https://reflex.dev/docs/llms.txt)" in content
    assert (
        "# Introduction\n"
        "Source: https://reflex.dev/docs/getting-started/introduction.md\n\n"
        "Build full-stack apps in Python."
    ) in content
    assert (
        "# Props\n"
        "Source: https://reflex.dev/docs/components/props.md\n\n"
        "Use props to configure components."
    ) in content
