"""Integration tests for the production build pipeline.

Tests precompressed assets against a real prod build served via AppHarnessProd.
"""

from __future__ import annotations

import re
import sys
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


def LinkedStylesheetApp():
    """An app whose stylesheets are a package's, linked in like rx.asset(shared=True)."""
    import zlib
    from pathlib import Path

    import reflex as rx

    # The font and image next to the package's stylesheets are not linked
    # themselves. Above Vite's 4 KiB inline limit, the build emits them as files.
    package = Path.cwd() / "site_package"
    (package / "css").mkdir(parents=True, exist_ok=True)
    (package / "fonts").mkdir(exist_ok=True)
    (package / "images").mkdir(exist_ok=True)
    (package / "fonts" / "x.woff2").write_bytes(zlib.compress(b"font", 0) * 500)
    (package / "images" / "y.png").write_bytes(zlib.compress(b"image", 0) * 500)
    (package / "css" / "site.css").write_text(
        '@font-face { font-family: Site; src: url(../fonts/x.woff2) format("woff2"); }'
    )
    (package / "css" / "page.css").write_text(
        ".hero { background-image: url(../images/y.png); }"
    )
    external = Path.cwd() / "assets" / "external" / "site_package" / "css"
    external.mkdir(parents=True, exist_ok=True)
    for name in ("site.css", "page.css"):
        if not (external / name).is_symlink():
            (external / name).symlink_to(package / "css" / name)

    app = rx.App(stylesheets=["/external/site_package/css/site.css"])
    app.add_page(rx.el.main("Index", style={"font_family": "Site"}), route="/")
    app.add_page(
        rx.el.main("Styled", class_name="hero"),
        route="/styled",
        stylesheets=["/external/site_package/css/page.css"],
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


@pytest.fixture(scope="module")
def linked_stylesheet_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Build and serve the linked stylesheet app in production mode.

    Yields:
        A running production app harness.
    """
    if app_harness_env is not AppHarnessProd:
        pytest.skip("build pipeline checks are prod-only")
    if sys.platform == "win32":
        pytest.skip("symlinks need a privilege on Windows")

    root = tmp_path_factory.mktemp("linked_stylesheet")
    # Without Tailwind, which rewrites the urls of the stylesheets it imports
    # against its own base instead of the importing stylesheet.
    (root / "rxconfig.py").write_text(
        'import reflex as rx\n\nconfig = rx.Config(app_name="linked_stylesheet", plugins=[])\n'
    )
    (root / "linked_stylesheet").mkdir()
    (root / "linked_stylesheet" / "__init__.py").touch()
    with app_harness_env.create(
        root=root,
        app_name="linked_stylesheet",
        app_source=LinkedStylesheetApp,
    ) as harness:
        yield harness


def test_linked_stylesheet_urls_resolve_next_to_their_real_file(
    linked_stylesheet_app: AppHarness,
):
    """A shared stylesheet's relative urls become fingerprinted build assets.

    Args:
        linked_stylesheet_app: The running prod harness.
    """
    [font] = _find_build_files(linked_stylesheet_app, "assets/x-*.woff2")
    [image] = _find_build_files(linked_stylesheet_app, "assets/y-*.png")
    urls = {
        url
        for css in _find_build_files(linked_stylesheet_app, "assets/*.css")
        for url in re.findall(r"url\(([^)]+)\)", css.read_text())
    }

    assert urls == {f"/assets/{font.name}", f"/assets/{image.name}"}


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
