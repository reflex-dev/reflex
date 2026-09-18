"""Validate the published content and structured data of the overview pages."""

import json
import re
from pathlib import Path

import pytest
from reflex_site_shared.docs.markdown import (
    FAQS_END_MARKER,
    FAQS_START_MARKER,
    FAQS_VISIBLE_MARKER,
    _extract_faqs_jsonld,
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
    schema = json.loads(json.loads(str(script.children[0].contents)))
    assert schema["@type"] == "FAQPage"
    assert len(schema["mainEntity"]) == 3
    for question in schema["mainEntity"]:
        assert stripped.count(question["name"]) == 1
        assert stripped.count(question["acceptedAnswer"]["text"]) == 1
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


def test_legacy_faq_remains_schema_only():
    """Existing FAQ blocks retain their original hidden behavior."""
    source = "Before\n<!-- faqs-start -->\n### Question?\n\nAnswer.\n<!-- faqs-end -->\nAfter"
    body, script = _extract_faqs_jsonld(source)
    assert body == "Before\n\nAfter"
    assert script is not None
