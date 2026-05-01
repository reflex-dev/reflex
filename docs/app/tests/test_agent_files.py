"""Tests for agent-facing static file generation."""

from pathlib import Path
from types import SimpleNamespace

from agent_files._plugin import (
    MarkdownFileEntry,
    MarkdownIndexEntry,
    dynamic_api_reference_index_entries,
    generate_dynamic_api_reference_files,
    generate_llms_full_txt,
    generate_llms_txt,
    generate_markdown_file_content,
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
        MarkdownIndexEntry(
            url_path=Path("components/props.md"),
            title="Props",
            section="Components",
        ),
        MarkdownIndexEntry(
            url_path=Path("components/rendering-iterables.md"),
            title="Rendering Iterables",
            section="Components",
        ),
        MarkdownIndexEntry(
            url_path=Path("state/overview.md"),
            title="State Overview",
            section="State",
        ),
        MarkdownIndexEntry(
            url_path=Path("ai/overview/best-practices.md"),
            title="Reflex Build: Best Practices",
            section="AI Builder",
        ),
        MarkdownIndexEntry(
            url_path=Path("ai/integrations/resend.md"),
            title="Resend Integration",
            section="AI Builder",
        ),
        MarkdownIndexEntry(
            url_path=Path("ai/integrations/mcp-overview.md"),
            title="Overview",
            section="MCP",
        ),
        MarkdownIndexEntry(
            url_path=Path("ai/integrations/ai-onboarding.md"),
            title="AI Onboarding",
            section="AI Onboarding",
        ),
        MarkdownIndexEntry(
            url_path=Path("ai/integrations/mcp-installation.md"),
            title="Installation",
            section="MCP",
        ),
        MarkdownIndexEntry(
            url_path=Path("ai/integrations/skills.md"),
            title="Skills",
            section="Skills",
        ),
        MarkdownIndexEntry(
            url_path=Path("ai/features/ide.md"),
            title="Reflex Build IDE",
            section="AI Builder",
        ),
    ])

    assert path == Path("llms.txt")
    assert content.startswith(
        "# Reflex Documentation\n\n"
        "> Reflex is a Python framework for building full-stack web apps. "
        "Use this index to find agent-readable Markdown docs, or see "
        "[llms-full.txt](https://reflex.dev/docs/llms-full.txt) for the "
        "complete docs in one file.\n\n"
        "## Docs\n\n"
    )
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


def test_generate_markdown_file_content_adds_agent_directive(monkeypatch, tmp_path):
    """Generated markdown pages advertise the docs index and markdown access."""
    monkeypatch.setattr(
        "reflex_base.config.get_config",
        lambda: SimpleNamespace(
            deploy_url="http://localhost:3000",
            frontend_path="/docs",
        ),
    )
    source = tmp_path / "overview.md"
    source.write_text(
        "# Overview\n\nBuild full-stack apps in Python.\n",
        encoding="utf-8",
    )

    content = generate_markdown_file_content(
        MarkdownFileEntry(
            url_path=Path("getting-started/overview.md"),
            source_path=source,
            title="Overview",
            section="Getting Started",
        )
    )

    assert content.startswith(
        "> For AI agents: the complete documentation index is at "
        "[llms.txt](https://reflex.dev/docs/llms.txt). Markdown versions are "
        "available by appending `.md` or sending `Accept: text/markdown`.\n\n"
        "# Overview"
    )


def test_generate_markdown_file_content_appends_component_props_table(
    monkeypatch, tmp_path
):
    """Component docs markdown includes generated API reference props tables."""
    monkeypatch.setattr(
        "reflex_base.config.get_config",
        lambda: SimpleNamespace(
            deploy_url="https://reflex.dev",
            frontend_path="/docs",
        ),
    )
    source = tmp_path / "button.md"
    source.write_text(
        "---\n"
        "components:\n"
        "  - rx.button\n"
        "---\n\n"
        "# Button\n\n"
        "Buttons trigger actions.\n",
        encoding="utf-8",
    )

    content = generate_markdown_file_content(
        MarkdownFileEntry(
            url_path=Path("library/forms/button.md"),
            source_path=source,
            title="Button",
            section="Library",
        )
    )

    assert "## API Reference\n\n### rx.button" in content
    assert "#### Props" in content
    assert "#### Event Triggers" in content
    assert (
        "Base event triggers: https://reflex.dev/docs/api-reference/event-triggers/"
        in content
    )
    props_table = content.split("#### Props\n\n", maxsplit=1)[1].split(
        "\n\n", maxsplit=1
    )[0]
    props_rows = props_table.splitlines()
    assert props_rows[0].startswith("| Prop")
    assert "Type" in props_rows[0]
    assert "Default" in props_rows[0]
    assert "Description" in props_rows[0]
    assert props_rows[1] == "| --- | --- | --- | --- |"
    assert "Literal[...]" not in props_table
    assert "\\|" not in props_table
    variant_rows = [row for row in props_rows if row.startswith("| `variant`")]
    assert len(variant_rows) == 1
    assert (
        'Literal["classic", "solid", "soft", "surface", "outline", "ghost"]'
        in variant_rows[0]
    )
    assert not any(row.split("|")[1].strip() == "" for row in props_rows[2:])


def test_generate_dynamic_api_reference_files(monkeypatch):
    """Dynamic API reference pages have generated markdown assets."""
    monkeypatch.setattr(
        "reflex_base.config.get_config",
        lambda: SimpleNamespace(
            deploy_url="https://reflex.dev",
            frontend_path="/docs",
        ),
    )

    raw_files = generate_dynamic_api_reference_files()
    files = dict(raw_files)

    assert Path("api-reference/var.md") in files
    assert files[Path("api-reference/var.md")].startswith(
        "> For AI agents: the complete documentation index is at "
        "[llms.txt](https://reflex.dev/docs/llms.txt). Markdown versions are "
        "available by appending `.md` or sending `Accept: text/markdown`.\n\n"
        "# Var\n\n"
    )
    assert "## Methods" in files[Path("api-reference/var.md")]
    assert "`reflex_base.vars.base.Var`" in files[Path("api-reference/var.md")]
    assert Path("api-reference/var-system.md") not in files

    # Dynamic API markdown files match the existing lowercase page routes.
    assert Path("api-reference/eventhandler.md") in files
    assert files[Path("api-reference/eventhandler.md")].startswith(
        "> For AI agents: the complete documentation index is at "
        "[llms.txt](https://reflex.dev/docs/llms.txt). Markdown versions are "
        "available by appending `.md` or sending `Accept: text/markdown`.\n\n"
        "# Eventhandler\n\n"
    )
    assert Path("api-reference/event-handler.md") not in files
    assert Path("api-reference/componentstate.md") in files
    assert Path("api-reference/statemanager.md") in files
    assert Path("api-reference/importvar.md") in files

    env_vars = files[Path("api-reference/environment-variables.md")]
    assert env_vars.startswith(
        "> For AI agents: the complete documentation index is at "
        "[llms.txt](https://reflex.dev/docs/llms.txt). Markdown versions are "
        "available by appending `.md` or sending `Accept: text/markdown`.\n\n"
        "# Environment Variables\n\n"
    )
    assert "`reflex.config.EnvironmentVariables`" in env_vars

    # Dynamic API-reference pages must land in the llms.txt index.
    _, llms_txt = generate_llms_txt(dynamic_api_reference_index_entries(raw_files))
    assert "### API Reference" in llms_txt
    assert "[Var](https://reflex.dev/docs/api-reference/var.md)" in llms_txt
    assert (
        "[Eventhandler](https://reflex.dev/docs/api-reference/eventhandler.md)"
        in llms_txt
    )


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

    path, content = generate_llms_full_txt(
        [
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
        ],
        [
            (
                MarkdownIndexEntry(
                    url_path=Path("api-reference/eventhandler.md"),
                    title="Eventhandler",
                    section="API Reference",
                ),
                "> For AI agents: the complete documentation index is at "
                "[llms.txt](https://reflex.dev/docs/llms.txt). Markdown versions are "
                "available by appending `.md` or sending `Accept: text/markdown`.\n\n"
                "# Eventhandler\n\n"
                "`reflex_base.event.EventHandler`\n",
            )
        ],
    )

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
    assert (
        "# Eventhandler\n"
        "Source: https://reflex.dev/docs/api-reference/eventhandler.md\n\n"
        "`reflex_base.event.EventHandler`"
    ) in content
    assert "For AI agents: the complete documentation index" not in content
