"""Tests for agent-facing static file generation."""

from pathlib import Path
from types import SimpleNamespace

from agent_files._plugin import MarkdownFileEntry, generate_llms_txt


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
            url_path=Path("ai-builder/overview/best-practices.md"),
            source_path=Path("docs/ai_builder/overview/best_practices.md"),
            title="Reflex Build: Best Practices",
            section="AI Builder",
        ),
        MarkdownFileEntry(
            url_path=Path("ai-builder/integrations/resend.md"),
            source_path=Path("docs/ai_builder/integrations/resend.md"),
            title="Resend Integration",
            section="AI Builder",
        ),
        MarkdownFileEntry(
            url_path=Path("ai-builder/integrations/mcp-overview.md"),
            source_path=Path("docs/ai_builder/integrations/mcp_overview.md"),
            title="Overview",
            section="MCP",
        ),
        MarkdownFileEntry(
            url_path=Path("ai-builder/integrations/mcp-installation.md"),
            source_path=Path("docs/ai_builder/integrations/mcp_installation.md"),
            title="Installation",
            section="MCP",
        ),
        MarkdownFileEntry(
            url_path=Path("ai-builder/features/ide.md"),
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
        "- [Reflex Build: Best Practices](https://reflex.dev/docs/ai-builder/overview/best-practices.md)"
        in content
    )
    assert "Resend Integration" not in content
    assert "Reflex Build IDE" not in content
    assert "### MCP\n\n" in content
    assert (
        "- [Overview](https://reflex.dev/docs/ai-builder/integrations/mcp-overview.md)"
        in content
    )
    assert (
        "- [Installation](https://reflex.dev/docs/ai-builder/integrations/mcp-installation.md)"
        in content
    )
    assert content.index("### AI Builder") < content.index("### MCP")
    assert content.index("mcp-overview.md") < content.index("mcp-installation.md")
