"""Integration tests for the production build pipeline.

Tests precompressed assets against a real prod build served via AppHarnessProd.
"""

from __future__ import annotations

import json
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
    """A small app for build pipeline testing.

    Its pages share a stateful navbar and have a stateful part of their own.
    ``/`` and ``/b`` are registered from one module, ``/c`` as if from another.
    """
    import reflex as rx

    menu = rx.client_state(False)

    def page(marker: str) -> rx.Component:
        clicks = rx.client_state(0)
        return rx.el.main(
            rx.heading("Build Pipeline Test"),
            rx.el.nav(
                rx.el.button(
                    "Menu", on_click=menu.set(~menu.value), aria_label="shared-marker"
                ),
            ),
            rx.el.button(marker, on_click=clicks.set(1), aria_label=marker),
        )

    def index() -> rx.Component:
        return page("only-on-index")

    def b() -> rx.Component:
        return page("only-on-b")

    def c() -> rx.Component:
        return page("only-on-c")

    c.__module__ = "prod_build_pipeline_pages.c"

    app = rx.App()
    app.add_page(index, route="/")
    app.add_page(b, route="/b")
    app.add_page(c, route="/c")


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


def test_bundles_exclude_embedded_core_js(prod_app: AppHarness):
    """Emitted browser assets must not carry json5's embedded core-js runtime.

    Regression for https://github.com/reflex-dev/reflex/issues/7163: json5 was
    dropped as a direct dependency, but the upload helper kept importing it, so
    it resolved transitively and its UMD browser build shipped core-js 2.6.5
    into production bundles. Checking the dependency manifest alone does not
    catch that, so assert against the built assets.
    """
    js_files = _find_build_files(prod_app, "**/*.js")
    assert js_files, "No JS files in build"

    offenders = [
        path.name
        for path in js_files
        if "__core-js_shared__" in path.read_text(encoding="utf-8", errors="ignore")
    ]

    assert not offenders, f"bundles embed a core-js runtime: {offenders}"


def _route_code(harness: AppHarness, route_id: str) -> str:
    """Read the JS a route loads: its module and every chunk it imports.

    Args:
        harness: The running prod harness.
        route_id: The route's id in the react-router manifest.

    Returns:
        The code of those files.
    """
    static_dir = harness.app_path / prerequisites.get_web_dir() / constants.Dirs.STATIC
    (manifest_file,) = _find_build_files(harness, "assets/manifest-*.js")
    manifest = json.loads(
        manifest_file
        .read_text()
        .removeprefix("window.__reactRouterManifest=")
        .removesuffix(";")
    )
    route = manifest["routes"][route_id]
    return "\n".join(
        (static_dir / path.lstrip("/")).read_text()
        for path in {route["module"], *route["imports"]}
    )


def test_pages_load_only_their_own_auto_memos(prod_app: AppHarness):
    """A page's chunks hold its own memos and the shared ones, not another page's."""
    markers = {
        "_index": "only-on-index",
        "[b]._index": "only-on-b",
        "[c]._index": "only-on-c",
    }
    for stem, marker in markers.items():
        code = _route_code(prod_app, f"routes/{stem}")
        assert marker in code
        assert "shared-marker" in code
        for other in set(markers.values()) - {marker}:
            assert other not in code, (stem, other)


def test_shared_auto_memos_are_emitted_once(prod_app: AppHarness):
    """A memo several pages use is in one chunk, not copied into each page's."""
    chunks = [
        path.name
        for path in _find_build_files(prod_app, "assets/*.js")
        if "shared-marker" in path.read_text()
    ]
    assert len(chunks) == 1, chunks
