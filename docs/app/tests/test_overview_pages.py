"""Validate the published content and structured data of the overview pages."""

import json
import re
from pathlib import Path

import pytest
from reflex_docgen.markdown import (
    CodeBlock,
    DirectiveBlock,
    HeadingBlock,
    TextBlock,
    parse_document,
)
from reflex_site_shared.docs.markdown import (
    FAQS_END_MARKER,
    FAQS_START_MARKER,
    FAQS_VISIBLE_MARKER,
    _extract_faqs_jsonld,
    _spans_to_plaintext,
    render_docgen_document,
)

from reflex_docs.pages.docs import extract_doc_description

DOCS = Path(__file__).resolve().parents[2]
PAGES = [
    "ai_builder/overview/what_is_reflex_build.md",
    "hosting/self-hosting.md",
    "database/overview.md",
    "ai_builder/integrations/overview.md",
]


@pytest.mark.parametrize("path", PAGES)
def test_overview_faq_schema_matches_visible_answers(path):
    """Every structured answer must also appear in the visible FAQ."""
    source = (DOCS / path).read_text()
    stripped, script = _extract_faqs_jsonld(source)
    assert script is not None
    assert FAQS_START_MARKER not in stripped
    assert FAQS_END_MARKER not in stripped
    assert FAQS_VISIBLE_MARKER not in stripped
    # Script children store a LiteralStringVar, whose string form is a JS literal.
    schema = json.loads(script.children[0].contents._var_value)
    assert schema["@type"] == "FAQPage"
    assert len(schema["mainEntity"]) == 3
    faq = next(
        block
        for block in parse_document(stripped).blocks
        if isinstance(block, DirectiveBlock) and block.name == "faq-section"
    )
    questions = [
        _spans_to_plaintext(block.children)
        for block in faq.children
        if isinstance(block, HeadingBlock) and block.level == 3
    ]
    answers = " ".join(
        _spans_to_plaintext(block.children)
        for block in faq.children
        if isinstance(block, TextBlock)
    )
    for question in schema["mainEntity"]:
        assert questions.count(question["name"]) == 1
        assert " ".join(question["acceptedAnswer"]["text"].split()) in " ".join(
            answers.split()
        )
    assert extract_doc_description(source)
    prose = re.sub(r"^```.*?^```", "", source, flags=re.MULTILINE | re.DOTALL)
    assert len(re.findall(r"^# ", prose, re.MULTILINE)) == 1


@pytest.mark.parametrize("path", PAGES)
def test_overview_renders_twice(path):
    """Markdown, code examples, and the interactive catalog must render cleanly."""
    for _ in range(2):
        body, script = render_docgen_document("docs/" + path, DOCS / path)
        assert body is not None
        assert script is not None
        pending = [body]
        disclosures = []
        while pending:
            component = pending.pop()
            if component.tag == "details":
                disclosures.append(component)
            pending.extend(component.children)
        assert len(disclosures) == 3
        assert all(item.children[0].tag == "summary" for item in disclosures)


def test_legacy_faq_remains_schema_only():
    """Existing FAQ blocks retain their original hidden behavior."""
    source = "Before\n<!-- faqs-start -->\n### Question?\n\nAnswer.\n<!-- faqs-end -->\nAfter"
    body, script = _extract_faqs_jsonld(source)
    assert body == "Before\n\nAfter"
    assert script is not None


@pytest.mark.parametrize("fence", ["```", "````", "   ```"])
def test_visible_faq_preserves_fenced_answers(fence):
    """Code samples must remain inside the FAQ directive with later questions."""
    source = f"""<!-- faqs-start -->
<!-- faqs-visible -->
## FAQ
### First question?
Use **Python** and [the docs](/docs/).

Another paragraph with `code`.
{fence}python
print("hello")
{fence}
### Second question?
Another answer.
<!-- faqs-end -->
"""
    stripped, script = _extract_faqs_jsonld(source)
    assert script is not None
    blocks = parse_document(stripped).blocks
    assert len(blocks) == 1
    faq = blocks[0]
    assert isinstance(faq, DirectiveBlock)
    assert (
        sum(
            isinstance(block, HeadingBlock) and block.level == 3
            for block in faq.children
        )
        == 2
    )
    code = next(block for block in faq.children if isinstance(block, CodeBlock))
    assert code.content.strip() == 'print("hello")'


def test_database_description_preserves_search_terms():
    """The published description must retain the database and use-case terms."""
    description = extract_doc_description((DOCS / "database/overview.md").read_text())
    for term in [
        "MySQL",
        "PostgreSQL",
        "SQL Server",
        "SQLite",
        "dashboards",
        "internal tools",
    ]:
        assert term in description
