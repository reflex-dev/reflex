"""Tests for the integrations gallery listing."""

from integrations_docs import DOCS_DIR

from reflex_docs.pages.integrations.integration_list import (
    DISPLAY_TITLES,
    get_integration_path,
)


def _titles() -> dict[str, str]:
    """Map each listed integration to its gallery title.

    Returns:
        The gallery title of every listed integration, by name.
    """
    return {
        name: entry["title"]
        for item in get_integration_path()
        for name, entry in item.items()
    }


def test_display_titles_override_title_casing() -> None:
    """Names that title-casing mangles use their brand spelling."""
    titles = _titles()
    assert titles["openai"] == "OpenAI"
    assert titles["microsoft_entra_id"] == "Microsoft Entra ID"
    assert titles["custom_oidc"] == "Custom OIDC"
    assert titles["github"] == "GitHub"


def test_other_titles_are_title_cased() -> None:
    """Names without an override fall back to title-casing the filename."""
    assert _titles()["google_auth"] == "Google Auth"


def test_display_titles_match_existing_docs() -> None:
    """Every override names a doc that exists, so none goes stale silently."""
    for name in DISPLAY_TITLES:
        assert (DOCS_DIR / f"{name}.md").is_file(), name
