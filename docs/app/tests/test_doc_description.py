"""Unit tests for the meta-description extraction in reflex_docs.pages.docs."""

from reflex_docs.pages.docs import extract_doc_description

# A body paragraph comfortably longer than the 120-char min_len threshold.
LONG_PROSE = (
    "5 minutes of configuration is all you need to get started with this "
    "powerful Python framework, and then some more prose to be safely long."
)


def test_prose_starting_with_minutes_is_not_stripped():
    """A sentence opening with '<n> minutes …' must not be treated as a badge."""
    result = extract_doc_description(LONG_PROSE)
    assert result is not None
    assert result.startswith("5 minutes of configuration")


def test_real_reading_time_badge_is_stripped():
    """A genuine reading-time marker ('N min read ·') is removed."""
    body = (
        "3 min read · Everything you need to know about deploying your Reflex "
        "applications to production with confidence, speed, and reliability."
    )
    result = extract_doc_description(body)
    assert result is not None
    assert not result.startswith("3 min")
    assert result.startswith("Everything you need")


def test_reading_time_badge_with_bullet_only_is_stripped():
    """A marker using only the '·' separator (no 'read' keyword) is removed."""
    body = (
        "10 min · A thorough walkthrough of building, styling, and shipping a "
        "full-stack Reflex application entirely in pure Python code today."
    )
    result = extract_doc_description(body)
    assert result is not None
    assert result.startswith("A thorough walkthrough")


def test_frontmatter_long_description_after_short_meta_description():
    """A short meta_description must not shadow a later long description."""
    long_desc = (
        "A genuinely long and useful description of this page that easily "
        "exceeds one hundred and twenty characters so it is used verbatim."
    )
    text = f"---\nmeta_description: Docs\ndescription: {long_desc}\n---\nBody.\n"
    assert extract_doc_description(text) == long_desc


def test_metadata_dict_long_description_returned():
    """A long description in the parsed metadata dict is returned directly."""
    long_desc = (
        "A complete overview of the component, covering its props, styling, and "
        "typical usage patterns in enough detail to exceed the length floor."
    )
    assert extract_doc_description(None, {"description": long_desc}) == long_desc


def test_metadata_dict_short_description_falls_through_to_body():
    """A too-short metadata description falls through to the body prose."""
    result = extract_doc_description(LONG_PROSE, {"description": "Docs"})
    assert result is not None
    assert result.startswith("5 minutes of configuration")
