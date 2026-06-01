"""Tests for reflex_site_shared.integrations URL helpers."""

import pytest
from reflex_site_shared.integrations import (
    RAW_DOC_IMAGES_PREFIX,
    rewrite_integration_doc_images_in_source,
)


@pytest.fixture(autouse=True)
def _backend_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the symlink step so the helpers run without filesystem side effects."""
    monkeypatch.setenv("REFLEX_BACKEND_ONLY", "true")


def test_rewrite_source_replaces_all_doc_image_urls() -> None:
    source = (
        f"![one]({RAW_DOC_IMAGES_PREFIX}okta_auth_1.png)\n"
        f"text\n"
        f"![two]({RAW_DOC_IMAGES_PREFIX}descope.webp)\n"
    )
    rewritten = rewrite_integration_doc_images_in_source(source)
    assert RAW_DOC_IMAGES_PREFIX not in rewritten
    assert "(/external/integrations_docs/docs/okta_auth_1.png)" in rewritten
    assert "(/external/integrations_docs/docs/descope.webp)" in rewritten


def test_rewrite_source_without_doc_images_unchanged() -> None:
    source = (
        "# Title\n\n"
        "![logo](https://example.com/logo.svg)\n"
        "![aws](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/logos/light/aws.svg)\n"
    )
    assert rewrite_integration_doc_images_in_source(source) == source
