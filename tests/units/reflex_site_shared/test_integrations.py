"""Tests for reflex_site_shared.integrations URL helpers."""

import pytest
from reflex_site_shared import integrations
from reflex_site_shared.integrations import (
    RAW_DOC_IMAGES_PREFIX,
    rewrite_integration_doc_image_src,
)


@pytest.fixture(autouse=True)
def _backend_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the symlink step and reset the cached image URL between tests."""
    monkeypatch.setenv("REFLEX_BACKEND_ONLY", "true")
    integrations._integrations_images_url.cache_clear()


def test_rewrite_matching_url_returns_local_asset() -> None:
    src = f"{RAW_DOC_IMAGES_PREFIX}databricks_integration_1.webp"
    assert (
        rewrite_integration_doc_image_src(src)
        == "/external/integrations_docs/docs/databricks_integration_1.webp"
    )


def test_rewrite_non_matching_url_unchanged() -> None:
    for src in (
        "https://example.com/image.png",
        "/local/image.webp",
        "https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/logos/light/aws.svg",
    ):
        assert rewrite_integration_doc_image_src(src) == src
