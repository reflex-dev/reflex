"""Tests for the integrations gallery listing."""

from reflex_docs.pages.integrations.integration_list import get_integration_path


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


def test_titles_keep_acronyms_and_brand_names() -> None:
    """Names that title-casing mangles use their acronym or brand spelling."""
    titles = _titles()
    assert titles["aws"] == "AWS"
    assert titles["openai"] == "OpenAI"
    assert titles["hubspot"] == "HubSpot"
    assert titles["microsoft_entra_id"] == "Microsoft Entra ID"
    assert titles["custom_oidc"] == "Custom OIDC"
    assert titles["github"] == "GitHub"


def test_other_titles_are_title_cased() -> None:
    """Names without an acronym are title-cased from the filename."""
    assert _titles()["google_auth"] == "Google Auth"
