"""Regression coverage for canonical-page Markdown exports."""

from types import SimpleNamespace

import pytest

from agent_files import AgentFilesPlugin


@pytest.mark.parametrize("frontmatter", ["", "---\ntitle: Build with AI\n---\n\n"])
def test_post_build_exports_missing_pages_and_preserves_authored_markdown(
    tmp_path, monkeypatch, frontmatter
):
    """Catalog links and answers survive export without replacing authored code."""
    monkeypatch.setattr(
        "agent_files._plugin.get_config",
        lambda: SimpleNamespace(frontend_path="/docs", deploy_url="https://reflex.dev"),
    )
    monkeypatch.setattr(
        "reflex_site_shared.utils.url.get_config",
        lambda: SimpleNamespace(frontend_path="/docs", deploy_url="https://reflex.dev"),
    )
    root = tmp_path / "docs"
    for route, body in {
        "": '<h1>Reflex Docs</h1><p>Choose a workflow.</p><a href="/docs/ai/">Build with AI</a>',
        "ai/": '<h1>Build with AI</h1><h2>Use Reflex Build</h2><p>Recommended workflow.</p><a href="/docs/ai/guide/">Read the guide</a>',
        "ai/guide/": "<h1>Guide</h1><p>Rendered example.</p>",
    }.items():
        page = root / route / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(
            f"<html><head><title>Docs</title></head><body><nav>Global navigation</nav><main><article>{body}<footer>Copyright</footer></article></main></body></html>"
        )
    authored = '# Guide\n\n```python\nprint("keep original code")\n```\n'
    (root / "ai/guide.md").write_text(authored)
    (root / "ai.md").write_text(
        "> For AI agents: old directive\n\n"
        + frontmatter
        + "```python exec\nfrom example import page\n```\n\n```python eval\npage()\n```\n"
    )
    (tmp_path / "sitemap.xml").write_text(
        "<urlset>"
        + "".join(
            f"<url><loc>https://reflex.dev/docs/{route}</loc></url>"
            for route in ("", "ai/", "ai/guide/")
        )
        + "</urlset>"
    )
    plugin = AgentFilesPlugin()
    plugin.post_build(static_dir=tmp_path)
    assert (root / "index.md").is_file()
    generated = (root / "ai.md").read_text()
    assert "# Build with AI" in generated
    assert "Recommended workflow." in generated
    assert "https://reflex.dev/docs/ai/guide/" in generated
    assert "Global navigation" not in generated and "Copyright" not in generated
    assert "python eval" not in generated and "from example" not in generated
    assert (root / "ai/guide.md").read_text() == authored
    assert "https://reflex.dev/docs/index.md" in (root / "llms.txt").read_text()
    assert "https://reflex.dev/docs/ai.md" in (root / "llms.txt").read_text()
    combined = (root / "llms-full.txt").read_text()
    assert (
        "Recommended workflow." in combined
        and 'print("keep original code")' in combined
    )
    plugin.post_build(static_dir=tmp_path)
    assert (root / "llms-full.txt").read_text() == combined


def test_rendered_markdown_retains_code_tables_and_links():
    """Fallback exports preserve the answer and handle Markdown delimiters."""
    from agent_files._rendered import rendered_content

    title, content = rendered_content(
        '<main><a href="#reference"><h1>Reference</h1></a><pre><code>def example():\n    return "```"</code></pre>'
        "<table><thead><tr><th>Prop</th><th>Type</th></tr></thead><tbody>"
        "<tr><td><code>color</code></td><td>str | None</td></tr></tbody></table>"
        '<p><a href="/docs/guide/?a=1&amp;b=2#example">Guide</a></p>'
        '<button>Copy</button><span aria-hidden="true">Decoration</span></main>',
        "https://reflex.dev/docs/reference/",
    )
    assert title == "Reference"
    assert content.startswith("# Reference\n")
    assert '````\ndef example():\n    return "```"\n````' in content
    assert "| `color` | str \\| None |" in content
    assert "https://reflex.dev/docs/guide/?a=1&b=2#example" in content
    assert "Copy" not in content and "Decoration" not in content


def test_linked_cards_keep_their_content_and_destination():
    """Heading wrappers and empty overlay links must not discard navigation."""
    from agent_files._rendered import rendered_content

    _, content = rendered_content(
        '<main><h1>Build with AI</h1><a href="/docs/build/" aria-label="Use Build">'
        "<h2>Use Build</h2><p>Recommended workflow.</p></a>"
        '<a href="/docs/agents/" aria-label="Agent Toolkit"></a></main>',
        "https://reflex.dev/docs/ai/",
    )
    assert "## Use Build" in content and "Recommended workflow." in content
    assert "[Use Build](https://reflex.dev/docs/build/)" in content
    assert "[Agent Toolkit](https://reflex.dev/docs/agents/)" in content
