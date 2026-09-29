"""Integration tests for precompressed production frontend responses."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from reflex.testing import AppHarnessProd
from tests.integration.utils import request_raw

# (config name, Accept-Encoding token, magic-byte prefix or None)
ENCODING_CASES: tuple[tuple[str, str, bytes | None], ...] = (
    ("gzip", "gzip", b"\x1f\x8b"),
    ("brotli", "br", None),
    ("zstd", "zstd", b"\x28\xb5\x2f\xfd"),
)
ENCODING_IDS = [case[0] for case in ENCODING_CASES]


def PrecompressedFrontendApp():
    """A minimal app for production static frontend checks."""
    import reflex as rx

    app = rx.App()

    @app.add_page
    def index():
        return rx.el.main(
            rx.heading("Precompressed Frontend"),
            rx.text("Hello from Reflex"),
        )


@pytest.fixture(scope="module")
def all_compression_formats_env() -> Generator[None, None, None]:
    """Configure the harness to build with every supported compression format.

    Yields:
        Control to the test, then restores the prior environment.
    """
    mp = pytest.MonkeyPatch()
    mp.setenv("REFLEX_FRONTEND_COMPRESSION_FORMATS", "gzip,brotli,zstd")
    yield
    mp.undo()


@pytest.fixture(scope="module")
def prod_test_app(
    all_compression_formats_env: None,
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarnessProd, None, None]:
    """Start the precompressed test app in production mode.

    Yields:
        A running production app harness.
    """
    with AppHarnessProd.create(
        root=tmp_path_factory.mktemp("precompressed_frontend"),
        app_name="precompressed_frontend",
        app_source=PrecompressedFrontendApp,
    ) as harness:
        yield harness


@pytest.mark.parametrize(
    ("_format_name", "accept_encoding", "magic"),
    ENCODING_CASES,
    ids=ENCODING_IDS,
)
def test_prod_frontend_serves_precompressed_index_html(
    prod_test_app: AppHarnessProd,
    _format_name: str,
    accept_encoding: str,
    magic: bytes | None,
):
    """Root HTML should be served from its precompressed sidecar for every encoding."""
    assert prod_test_app.frontend_url is not None

    status, headers, body = request_raw(
        prod_test_app.frontend_url,
        "/",
        headers={"Accept-Encoding": accept_encoding},
    )

    assert status == 200
    assert headers["content-encoding"] == accept_encoding
    assert headers["vary"] == "Accept-Encoding"
    if magic is not None:
        assert body[: len(magic)] == magic


@pytest.mark.parametrize(
    ("_format_name", "accept_encoding", "magic"),
    ENCODING_CASES,
    ids=ENCODING_IDS,
)
def test_prod_frontend_serves_precompressed_404_fallback(
    prod_test_app: AppHarnessProd,
    _format_name: str,
    accept_encoding: str,
    magic: bytes | None,
):
    """Unknown routes should serve the compressed 404.html fallback for every encoding."""
    assert prod_test_app.frontend_url is not None

    status, headers, body = request_raw(
        prod_test_app.frontend_url,
        "/missing-route",
        headers={"Accept-Encoding": accept_encoding},
    )

    assert status == 404
    assert headers["content-encoding"] == accept_encoding
    if magic is not None:
        assert body[: len(magic)] == magic
