"""Tests for reflex_site_shared.integrations URL helpers."""

import re
from pathlib import Path

import integrations_docs
import pytest
from reflex_site_shared.integrations import (
    RAW_DOC_IMAGES_PREFIX,
    _integrations_doc_images_url,
    rewrite_integration_doc_images_in_source,
)

DOC_IMAGES_DIR = Path(integrations_docs.__file__).parent / "images" / "docs"


@pytest.fixture(autouse=True)
def _backend_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the symlink step so the helpers run without filesystem side effects."""
    monkeypatch.setenv("REFLEX_BACKEND_ONLY", "true")


def test_rewrite_source_replaces_all_doc_image_urls() -> None:
    """Every raw GitHub doc-image URL in the source is rewritten to its local asset URL."""
    source = (
        f"![one]({RAW_DOC_IMAGES_PREFIX}okta_auth_1.png)\n"
        f"text\n"
        f"![two]({RAW_DOC_IMAGES_PREFIX}descope.webp)\n"
    )
    rewritten = rewrite_integration_doc_images_in_source(source)
    local_prefix = _integrations_doc_images_url()
    assert RAW_DOC_IMAGES_PREFIX not in rewritten
    assert f"({local_prefix}okta_auth_1.png)" in rewritten
    assert f"({local_prefix}descope.webp)" in rewritten


def test_rewrite_source_without_doc_images_unchanged() -> None:
    """Source without any raw GitHub doc-image URL is returned unchanged."""
    source = (
        "# Title\n\n"
        "![logo](https://example.com/logo.svg)\n"
        "![aws](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/logos/light/aws.svg)\n"
    )
    assert rewrite_integration_doc_images_in_source(source) == source


def test_doc_image_references_exist_locally() -> None:
    """Every screenshot URL in the docs must resolve to a local image, since the rewrite serves it locally."""
    missing = [
        f"{md.name}: {image_name}"
        for md in sorted(integrations_docs.DOCS_DIR.glob("*.md"))
        for image_name in re.findall(
            re.escape(RAW_DOC_IMAGES_PREFIX) + r"([^)\s]+)", md.read_text()
        )
        if not (DOC_IMAGES_DIR / image_name).is_file()
    ]
    assert not missing, f"docs reference images missing from images/docs/: {missing}"


def test_doc_image_references_use_image_syntax() -> None:
    """Screenshot URLs must use ![alt](url) image syntax, not a [!alt](url) link typo."""
    malformed = [
        md.name
        for md in sorted(integrations_docs.DOCS_DIR.glob("*.md"))
        if re.search(
            r"(?<!!)\[[^\]]*\]\(" + re.escape(RAW_DOC_IMAGES_PREFIX), md.read_text()
        )
    ]
    assert not malformed, (
        f"docs embed screenshots as links instead of images: {malformed}"
    )
