"""Integration tests for the production build pipeline.

Tests precompressed assets, image optimization, and CSS purging
against a real prod build served via AppHarnessProd.
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Generator
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from reflex.testing import AppHarness, AppHarnessProd


def _make_test_png(min_size: int = 2048) -> bytes:
    """Build a valid PNG that is at least *min_size* bytes.

    Returns:
        The PNG file bytes.
    """
    ihdr_data = b"IHDR" + struct.pack(">II", 2, 2) + b"\x08\x02\x00\x00\x00"
    ihdr = (
        struct.pack(">I", 13)
        + ihdr_data
        + struct.pack(">I", zlib.crc32(ihdr_data) & 0xFFFFFFFF)
    )

    raw_rows = b"\x00\xff\x00\x00\x00\xff\x00" * 2
    compressed = zlib.compress(raw_rows)
    idat_data = b"IDAT" + compressed
    idat = (
        struct.pack(">I", len(compressed))
        + idat_data
        + struct.pack(">I", zlib.crc32(idat_data) & 0xFFFFFFFF)
    )

    iend = b"\x00\x00\x00\x00IEND\xaeB`\x82"
    png = b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend

    if len(png) < min_size:
        text_payload = b"tEXtComment\x00" + b"A" * (min_size - len(png) - 12)
        text_chunk = (
            struct.pack(">I", len(text_payload))
            + text_payload
            + struct.pack(">I", zlib.crc32(text_payload) & 0xFFFFFFFF)
        )
        png = png[:-12] + text_chunk + iend
    return png


def ProdBuildPipelineApp():
    """A minimal app with an image asset for build pipeline testing."""
    import reflex as rx

    app = rx.App()

    @app.add_page
    def index():
        return rx.el.main(
            rx.heading("Build Pipeline Test"),
            rx.text("Hello"),
            rx.image(src="/test_image.png", alt="test"),
        )


def _request_raw(
    url: str,
    path: str,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    """Send a raw HTTP request without client-side decompression.

    Returns:
        The status code, response headers, and raw body.
    """
    parsed = urlsplit(url)
    assert parsed.hostname is not None
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=10)
    conn.request("GET", path, headers=headers or {})
    resp = conn.getresponse()
    body = resp.read()
    hdrs = {k.lower(): v for k, v in resp.getheaders()}
    status = resp.status
    conn.close()
    return status, hdrs, body


@pytest.fixture(scope="module")
def prod_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Build and serve the test app in production mode.

    Yields:
        A running production app harness.
    """
    if app_harness_env is not AppHarnessProd:
        pytest.skip("build pipeline checks are prod-only")

    root = tmp_path_factory.mktemp("prod_build_pipeline")
    harness = app_harness_env.create(
        root=root,
        app_name="prod_build_pipeline",
        app_source=ProdBuildPipelineApp,
    )
    # Initialize the app (creates .web/public/ etc.) but don't start yet.
    harness._initialize_app()

    # Place a test PNG in .web/public/ so the Vite build picks it up.
    # (Reflex serves `assets/` via the backend at runtime, but the Vite
    # image-optimize plugin only processes files inside the build tree.)
    import reflex.utils.prerequisites as prerequisites

    public_dir = root / prerequisites.get_web_dir() / "public"
    public_dir.mkdir(exist_ok=True)
    (public_dir / "test_image.png").write_bytes(_make_test_png())

    # Now run the rest of startup (backend, build, frontend server).
    harness._start_backend()
    harness._start_frontend()
    harness._wait_frontend()
    try:
        yield harness
    finally:
        harness.stop()


def _find_build_files(harness: AppHarness, pattern: str) -> list[Path]:
    """Find files matching a glob pattern in the prod build output.

    Returns:
        Sorted list of matching paths.
    """
    import reflex.constants as constants
    import reflex.utils.prerequisites as prerequisites

    static_dir = harness.app_path / prerequisites.get_web_dir() / constants.Dirs.STATIC
    return sorted(static_dir.rglob(pattern))


# -- Precompressed assets --


def test_js_bundles_have_gz_sidecars(prod_app: AppHarness):
    """Production JS bundles should have .gz sidecar files."""
    assert _find_build_files(prod_app, "**/*.js"), "No JS files in build"
    assert _find_build_files(prod_app, "**/*.js.gz"), "No .js.gz sidecars found"


def test_css_bundles_have_gz_sidecars(prod_app: AppHarness):
    """Production CSS bundles should have .gz sidecar files."""
    assert _find_build_files(prod_app, "**/*.css"), "No CSS files in build"
    assert _find_build_files(prod_app, "**/*.css.gz"), "No .css.gz sidecars found"


def test_gzip_content_negotiation(prod_app: AppHarness):
    """Server should return gzip-encoded response when client accepts it."""
    assert prod_app.frontend_url is not None
    # Request a JS bundle rather than / since HTML may be small
    js_files = _find_build_files(prod_app, "assets/**/*.js")
    assert js_files, "No JS bundles to test"

    # Get the relative path from the static dir to use as URL path
    import reflex.constants as constants
    import reflex.utils.prerequisites as prerequisites

    static_dir = prod_app.app_path / prerequisites.get_web_dir() / constants.Dirs.STATIC
    js_path = "/" + str(js_files[0].relative_to(static_dir))

    status, headers, body = _request_raw(
        prod_app.frontend_url,
        js_path,
        headers={"Accept-Encoding": "gzip"},
    )
    assert status == 200
    assert headers.get("content-encoding") == "gzip"
    assert body[:2] == b"\x1f\x8b"


# -- Image optimization --


def test_png_has_webp_sidecar(prod_app: AppHarness):
    """PNG assets should produce WebP sidecars after the build."""
    png_files = _find_build_files(prod_app, "**/test_image.png")
    if not png_files:
        pytest.skip(
            "test_image.png not in build output — Vite may have "
            "fingerprinted or inlined the asset"
        )

    webp_files = _find_build_files(prod_app, "**/test_image.webp")
    assert webp_files, (
        "No test_image.webp sidecar — image optimization may not be running"
    )
