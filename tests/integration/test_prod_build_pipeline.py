"""Integration tests for the production build pipeline.

Tests precompressed assets against a real prod build served via AppHarnessProd.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

import reflex.constants as constants
import reflex.utils.prerequisites as prerequisites
from reflex.testing import AppHarness, AppHarnessProd
from tests.integration.utils import request_raw

# (config name, Accept-Encoding token, sidecar suffix, magic-byte prefix or None)
ENCODING_CASES: tuple[tuple[str, str, str, bytes | None], ...] = (
    ("gzip", "gzip", ".gz", b"\x1f\x8b"),
    ("brotli", "br", ".br", None),
    ("zstd", "zstd", ".zst", b"\x28\xb5\x2f\xfd"),
)
ENCODING_IDS = [case[0] for case in ENCODING_CASES]


def ProdBuildPipelineApp():
    """A minimal app for build pipeline testing."""
    import reflex as rx

    app = rx.App()

    @app.add_page
    def index():
        return rx.el.main(
            rx.heading("Build Pipeline Test"),
            rx.text("Hello"),
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
def prod_app(
    app_harness_env: type[AppHarness],
    all_compression_formats_env: None,
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Build and serve the test app in production mode.

    Yields:
        A running production app harness.
    """
    if app_harness_env is not AppHarnessProd:
        pytest.skip("build pipeline checks are prod-only")

    with app_harness_env.create(
        root=tmp_path_factory.mktemp("prod_build_pipeline"),
        app_name="prod_build_pipeline",
        app_source=ProdBuildPipelineApp,
    ) as harness:
        yield harness


def _find_build_files(harness: AppHarness, pattern: str) -> list[Path]:
    """Find files matching a glob pattern in the prod build output.

    Args:
        harness: The running prod harness.
        pattern: A ``rglob``-style pattern.

    Returns:
        Sorted list of matching paths.
    """
    static_dir = harness.app_path / prerequisites.get_web_dir() / constants.Dirs.STATIC
    return sorted(static_dir.rglob(pattern))


@pytest.mark.parametrize(
    ("_format_name", "_accept_encoding", "suffix", "_magic"),
    ENCODING_CASES,
    ids=ENCODING_IDS,
)
def test_js_bundles_have_sidecars(
    prod_app: AppHarness,
    _format_name: str,
    _accept_encoding: str,
    suffix: str,
    _magic: bytes | None,
):
    """Production JS bundles should have a sidecar for every configured format."""
    assert _find_build_files(prod_app, "**/*.js"), "No JS files in build"
    assert _find_build_files(prod_app, f"**/*.js{suffix}"), (
        f"No .js{suffix} sidecars found"
    )


@pytest.mark.parametrize(
    ("_format_name", "_accept_encoding", "suffix", "_magic"),
    ENCODING_CASES,
    ids=ENCODING_IDS,
)
def test_css_bundles_have_sidecars(
    prod_app: AppHarness,
    _format_name: str,
    _accept_encoding: str,
    suffix: str,
    _magic: bytes | None,
):
    """Production CSS bundles should have a sidecar for every configured format."""
    assert _find_build_files(prod_app, "**/*.css"), "No CSS files in build"
    assert _find_build_files(prod_app, f"**/*.css{suffix}"), (
        f"No .css{suffix} sidecars found"
    )


@pytest.mark.parametrize(
    ("_format_name", "accept_encoding", "suffix", "magic"),
    ENCODING_CASES,
    ids=ENCODING_IDS,
)
def test_content_negotiation(
    prod_app: AppHarness,
    _format_name: str,
    accept_encoding: str,
    suffix: str,
    magic: bytes | None,
):
    """Server should return the encoded response matching the Accept-Encoding token."""
    assert prod_app.frontend_url is not None
    js_files = _find_build_files(prod_app, "assets/**/*.js")
    assert js_files, "No JS bundles to test"

    static_dir = prod_app.app_path / prerequisites.get_web_dir() / constants.Dirs.STATIC
    js_path = "/" + str(js_files[0].relative_to(static_dir))

    status, headers, body = request_raw(
        prod_app.frontend_url,
        js_path,
        headers={"Accept-Encoding": accept_encoding},
    )
    assert status == 200
    assert headers.get("content-encoding") == accept_encoding
    sidecar_bytes = (js_files[0].parent / (js_files[0].name + suffix)).read_bytes()
    assert body == sidecar_bytes
    if magic is not None:
        assert body[: len(magic)] == magic
