import dataclasses
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path, PureWindowsPath
from typing import Any

import pytest
from pytest_mock import MockerFixture
from reflex_base import constants
from reflex_base.components.app_wraps import collect_subtree_app_wraps
from reflex_base.components.component import BaseComponent, Component
from reflex_base.components.dynamic import (
    _bundle_library,
    bundle_library,
    reset_bundled_libraries,
)
from reflex_base.components.memo import MEMOS
from reflex_base.constants.base import LiteralColorMode
from reflex_base.constants.compiler import PageNames
from reflex_base.environment import environment
from reflex_base.plugins import CompileContext, CompilerHooks, PageContext
from reflex_base.plugins.sitemap import SitemapPlugin
from reflex_base.registry import RegistrationContext
from reflex_base.utils import memo_paths
from reflex_base.utils.console import PoorProgress
from reflex_base.utils.exceptions import (
    DynamicRouteArgShadowsStateVarError,
    PageValueError,
    RouteValueError,
)
from reflex_base.utils.imports import ImportVar, ParsedImportDict
from reflex_base.vars.base import Var
from reflex_base.vars.sequence import LiteralStringVar
from reflex_components_core.base import Description, document
from reflex_components_core.base.document import Links, Scripts
from reflex_components_core.el.elements.metadata import Head, Link, Meta
from reflex_components_core.el.elements.other import Html

import reflex as rx
from reflex.app import default_backend_exception_handler
from reflex.compiler import compiler, utils
from reflex.compiler.plugins import default_page_plugins
from reflex.state import BaseState
from reflex.utils import prerequisites
from reflex.utils.misc import preload_color_theme
from tests.units.compiler.test_dynamic_components_codegen import (
    app_root_loaders,
    loader,
)


@pytest.mark.parametrize("with_plugin", [False, True])
@pytest.mark.usefixtures("clean_registration_context")
def test_compile_progress_ends_at_its_total(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    with_plugin: bool,
):
    """The compile progress bar ends exactly at its total.

    Args:
        tmp_path: The temporary application directory.
        monkeypatch: Fixture for selecting the application directory.
        mocker: Fixture for avoiding frontend dependency installation.
        with_plugin: Whether a plugin adds its own files to save.
    """
    progress_bars: list[PoorProgress] = []

    class RecordingProgress(PoorProgress):
        """A plain progress bar that keeps every instance for inspection."""

        def __init__(self):
            """Initialize the progress bar and record it."""
            super().__init__()
            progress_bars.append(self)

    monkeypatch.setattr(compiler.console, "PoorProgress", RecordingProgress)
    monkeypatch.chdir(tmp_path)
    config = rx.Config(
        app_name="progress_test", plugins=[SitemapPlugin()] if with_plugin else []
    )
    mocker.patch("reflex_base.config._get_config", return_value=config)
    app = rx.App(enable_state=False)
    app.add_page(lambda: rx.el.div("hello"), route="index")
    mocker.patch.object(app, "_get_frontend_packages")

    compiler.compile_app(app, use_rich=False)

    assert len(progress_bars) == 1
    (task,) = progress_bars[0].tasks.values()
    assert task["current"] == task["total"]


@pytest.mark.parametrize("remove_assets_directory", [False, True])
@pytest.mark.usefixtures("clean_registration_context")
def test_compile_removes_deleted_app_assets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    remove_assets_directory: bool,
):
    """Repeated compiles remove deleted app assets while preserving public files.

    Args:
        tmp_path: The temporary application directory.
        monkeypatch: Fixture for selecting the application directory.
        mocker: Fixture for avoiding frontend dependency installation.
        remove_assets_directory: Whether to remove the entire source directory.
    """
    monkeypatch.chdir(tmp_path)
    config = rx.Config(app_name="asset_test", plugins=[])
    mocker.patch("reflex_base.config._get_config", return_value=config)
    app = rx.App(enable_state=False)
    app.add_page(lambda: rx.el.div("hello"), route="index")
    mocker.patch.object(app, "_get_frontend_packages")
    assets = tmp_path / "assets"
    (assets / "nested").mkdir(parents=True)
    (assets / "obsolete.txt").write_text("obsolete")
    (assets / "nested" / "obsolete.txt").write_text("nested obsolete")
    compiler.compile_app(app, use_rich=False)

    public = prerequisites.get_web_dir() / "public"
    assert (public / "obsolete.txt").read_text() == "obsolete"
    assert (public / "nested" / "obsolete.txt").read_text() == "nested obsolete"
    (public / "plugin.txt").write_text("generated")
    (public / "nested" / "plugin.txt").write_text("nested generated")
    if remove_assets_directory:
        shutil.rmtree(assets)
    else:
        (assets / "obsolete.txt").unlink()
        shutil.rmtree(assets / "nested")
        (assets / "current.txt").write_text("current")

    manifest = public.parent / utils._ASSET_MANIFEST_FILENAME
    previous_manifest = manifest.read_bytes()
    compiler.compile_app(app, dry_run=True, use_rich=False)
    assert (public / "obsolete.txt").read_text() == "obsolete"
    assert manifest.read_bytes() == previous_manifest

    compiler.compile_app(app, use_rich=False)

    assert not (public / "obsolete.txt").exists()
    assert not (public / "nested" / "obsolete.txt").exists()
    assert (public / "plugin.txt").read_text() == "generated"
    assert (public / "nested" / "plugin.txt").read_text() == "nested generated"
    if not remove_assets_directory:
        assert (public / "current.txt").read_text() == "current"


@pytest.mark.parametrize("content", ["", '["index",'])
def test_read_stateful_pages_marker_recovers_legacy_corruption(
    tmp_path, mocker, content
):
    """A marker truncated by an older writer requests full page evaluation."""
    mocker.patch("reflex.utils.prerequisites.get_backend_dir", return_value=tmp_path)
    (tmp_path / constants.Dirs.STATEFUL_PAGES).write_text(content)
    assert compiler._read_stateful_pages_marker() is None


def test_read_stateful_pages_marker_recovers_undecodable_marker(tmp_path, mocker):
    """A marker that is not valid UTF-8 requests full page evaluation."""
    mocker.patch("reflex.utils.prerequisites.get_backend_dir", return_value=tmp_path)
    # No BOM: json.loads() would decode a UTF-16 one and raise JSONDecodeError.
    (tmp_path / constants.Dirs.STATEFUL_PAGES).write_bytes(b"\xff garbage")
    assert compiler._read_stateful_pages_marker() is None


@pytest.mark.parametrize("windows", [False, True])
def test_read_stateful_pages_marker_sharing_violation(mocker, windows):
    """An unavailable Windows marker requests evaluation without hiding POSIX errors."""
    mocker.patch.object(constants, "IS_WINDOWS", windows)
    mocker.patch.object(Path, "read_bytes", side_effect=PermissionError)
    if windows:
        assert compiler._read_stateful_pages_marker() is None
    else:
        with pytest.raises(PermissionError):
            compiler._read_stateful_pages_marker()


@pytest.mark.parametrize(
    ("fields", "test_default", "test_rest"),
    [
        (
            [ImportVar(tag="axios", is_default=True)],
            "axios",
            [],
        ),
        (
            [ImportVar(tag="foo"), ImportVar(tag="bar")],
            "",
            ["bar", "foo"],
        ),
        (
            [
                ImportVar(tag="axios", is_default=True),
                ImportVar(tag="foo"),
                ImportVar(tag="bar"),
            ],
            "axios",
            ["bar", "foo"],
        ),
    ],
)
def test_compile_import_statement(
    fields: list[ImportVar], test_default: str, test_rest: str
):
    """Test the compile_import_statement function.

    Args:
        fields: The fields to import.
        test_default: The expected output of default library.
        test_rest: The expected output rest libraries.
    """
    default, rest = utils.compile_import_statement(fields)
    assert default == test_default
    assert sorted(rest) == test_rest


@pytest.mark.parametrize(
    ("import_dict", "test_dicts"),
    [
        ({}, []),
        (
            {"axios": [ImportVar(tag="axios", is_default=True)]},
            [{"lib": "axios", "default": "axios", "rest": []}],
        ),
        (
            {"axios": [ImportVar(tag="foo"), ImportVar(tag="bar")]},
            [{"lib": "axios", "default": "", "rest": ["bar", "foo"]}],
        ),
        (
            {
                "axios": [
                    ImportVar(tag="axios", is_default=True),
                    ImportVar(tag="foo"),
                    ImportVar(tag="bar"),
                ],
                "react": [ImportVar(tag="react", is_default=True)],
            },
            [
                {"lib": "axios", "default": "axios", "rest": ["bar", "foo"]},
                {"lib": "react", "default": "react", "rest": []},
            ],
        ),
        (
            {"": [ImportVar(tag="lib1.js"), ImportVar(tag="lib2.js")]},
            [
                {"lib": "lib1.js", "default": "", "rest": []},
                {"lib": "lib2.js", "default": "", "rest": []},
            ],
        ),
        (
            {
                "": [ImportVar(tag="lib1.js"), ImportVar(tag="lib2.js")],
                "axios": [ImportVar(tag="axios", is_default=True)],
            },
            [
                {"lib": "lib1.js", "default": "", "rest": []},
                {"lib": "lib2.js", "default": "", "rest": []},
                {"lib": "axios", "default": "axios", "rest": []},
            ],
        ),
    ],
)
def test_compile_imports(import_dict: ParsedImportDict, test_dicts: list[dict]):
    """Test the compile_imports function.

    Args:
        import_dict: The import dictionary.
        test_dicts: The expected output.
    """
    imports = utils.compile_imports(import_dict)
    for one_import_dict, test_dict in zip(imports, test_dicts, strict=True):
        assert one_import_dict["lib"] == test_dict["lib"]
        assert one_import_dict["default"] == test_dict["default"]
        assert (
            sorted(
                one_import_dict["rest"],
                key=lambda i: i if isinstance(i, str) else (i.tag or ""),
            )
            == test_dict["rest"]
        )


def test_compile_stylesheets(tmp_path: Path, mocker: MockerFixture):
    """Test that stylesheets compile correctly.

    Args:
        tmp_path: The test directory.
        mocker: Pytest mocker object.
    """
    project = tmp_path / "test_project"
    project.mkdir()

    assets_dir = project / "assets"
    assets_dir.mkdir()

    (assets_dir / "style.css").write_text(
        "button.rt-Button {\n\tborder-radius:unset !important;\n}"
    )
    mocker.patch("reflex.compiler.compiler.Path.cwd", return_value=project)
    mocker.patch(
        "reflex.compiler.compiler.get_web_dir",
        return_value=project / constants.Dirs.WEB,
    )
    mocker.patch(
        "reflex.compiler.utils.get_web_dir", return_value=project / constants.Dirs.WEB
    )

    stylesheets = [
        "https://fonts.googleapis.com/css?family=Sofia&effect=neon|outline|emboss|shadow-multiple",
        "https://cdn.jsdelivr.net/npm/bootstrap@3.3.7/dist/css/bootstrap.min.css",
        "/style.css",
        "https://cdn.jsdelivr.net/npm/bootstrap@3.3.7/dist/css/bootstrap-theme.min.css",
    ]

    assert compiler.compile_root_stylesheet(stylesheets) == (
        str(
            project
            / constants.Dirs.WEB
            / "styles"
            / (PageNames.STYLESHEET_ROOT + ".css")
        ),
        (
            "@layer __reflex_base;\n"
            "@import url('./__reflex_style_reset.css');\n"
            "@import url('https://fonts.googleapis.com/css?family=Sofia&effect=neon|outline|emboss|shadow-multiple');\n"
            "@import url('https://cdn.jsdelivr.net/npm/bootstrap@3.3.7/dist/css/bootstrap.min.css');\n"
            "@import url('https://cdn.jsdelivr.net/npm/bootstrap@3.3.7/dist/css/bootstrap-theme.min.css');\n"
            "@import url('./style.css');"
        ),
    )

    assert (project / constants.Dirs.WEB / "styles" / "style.css").read_text() == (
        assets_dir / "style.css"
    ).read_text()


def test_compile_stylesheets_scss_sass(tmp_path: Path, mocker: MockerFixture):
    if importlib.util.find_spec("sass") is None:
        pytest.skip(
            'The `libsass` package is required to compile sass/scss stylesheet files. Run `pip install "libsass>=0.23.0"`.'
        )
    if os.name == "nt":
        pytest.skip("Skipping test on Windows")

    project = tmp_path / "test_project"
    project.mkdir()

    assets_dir = project / "assets"
    assets_dir.mkdir()

    assets_preprocess_dir = assets_dir / "preprocess"
    assets_preprocess_dir.mkdir()

    (assets_dir / "style.css").write_text(
        "button.rt-Button {\n\tborder-radius:unset !important;\n}"
    )
    (assets_preprocess_dir / "styles_a.sass").write_text(
        "button.rt-Button\n\tborder-radius:unset !important"
    )
    (assets_preprocess_dir / "styles_b.scss").write_text(
        "button.rt-Button {\n\tborder-radius:unset !important;\n}"
    )
    mocker.patch("reflex.compiler.compiler.Path.cwd", return_value=project)
    mocker.patch(
        "reflex.compiler.compiler.get_web_dir",
        return_value=project / constants.Dirs.WEB,
    )
    mocker.patch(
        "reflex.compiler.utils.get_web_dir", return_value=project / constants.Dirs.WEB
    )

    stylesheets = [
        "/style.css",
        "/preprocess/styles_a.sass",
        "/preprocess/styles_b.scss",
    ]

    assert compiler.compile_root_stylesheet(stylesheets) == (
        str(
            project
            / constants.Dirs.WEB
            / "styles"
            / (PageNames.STYLESHEET_ROOT + ".css")
        ),
        (
            "@layer __reflex_base;\n"
            "@import url('./__reflex_style_reset.css');\n"
            "@import url('./style.css');\n"
            "@import url('./preprocess/styles_a.css');\n"
            "@import url('./preprocess/styles_b.css');"
        ),
    )

    stylesheets = [
        "/style.css",
        "/preprocess",  # this is a folder containing "styles_a.sass" and "styles_b.scss"
    ]

    assert compiler.compile_root_stylesheet(stylesheets) == (
        str(
            project
            / constants.Dirs.WEB
            / "styles"
            / (PageNames.STYLESHEET_ROOT + ".css")
        ),
        (
            "@layer __reflex_base;\n"
            "@import url('./__reflex_style_reset.css');\n"
            "@import url('./style.css');\n"
            "@import url('./preprocess/styles_a.css');\n"
            "@import url('./preprocess/styles_b.css');"
        ),
    )

    assert (project / constants.Dirs.WEB / "styles" / "style.css").read_text() == (
        assets_dir / "style.css"
    ).read_text()

    expected_result = "button.rt-Button{border-radius:unset !important}\n"
    assert (
        project / constants.Dirs.WEB / "styles" / "preprocess" / "styles_a.css"
    ).read_text() == expected_result
    assert (
        project / constants.Dirs.WEB / "styles" / "preprocess" / "styles_b.css"
    ).read_text() == expected_result


def test_compile_stylesheets_nested_import_uses_posix_separators(
    tmp_path: Path, mocker: MockerFixture
):
    """Nested stylesheet imports must use forward slashes on every platform.

    A CSS `@import url(...)` treats a backslash as an escape introducer, not a
    path separator, so emitting `str(target_path)` breaks nested stylesheets on
    Windows (where the relative path is backslash-separated). Simulate that by
    forcing the relative path to a `PureWindowsPath` and assert the emitted
    import is POSIX-normalized.

    Args:
        tmp_path: The test directory.
        mocker: Pytest mocker object.
    """
    project = tmp_path / "test_project"
    project.mkdir()

    assets_dir = project / "assets"
    assets_dir.mkdir()

    nested_dir = assets_dir / "subdir"
    nested_dir.mkdir()
    (nested_dir / "theme.css").write_text(".root { color: red; }")

    mocker.patch("reflex.compiler.compiler.Path.cwd", return_value=project)
    mocker.patch(
        "reflex.compiler.compiler.get_web_dir",
        return_value=project / constants.Dirs.WEB,
    )
    mocker.patch(
        "reflex.compiler.utils.get_web_dir", return_value=project / constants.Dirs.WEB
    )

    real_relative_to = Path.relative_to
    mocker.patch.object(
        Path,
        "relative_to",
        lambda self, *args, **kwargs: PureWindowsPath(
            real_relative_to(self, *args, **kwargs)
        ),
    )

    _, code = compiler.compile_root_stylesheet(["/subdir/theme.css"])

    assert "@import url('./subdir/theme.css');" in code
    assert "\\" not in code


def test_compile_stylesheets_exclude_tailwind(tmp_path, mocker: MockerFixture):
    """Test that Tailwind is excluded if tailwind config is explicitly set to None.

    Args:
        tmp_path: The test directory.
        mocker: Pytest mocker object.
    """
    project = tmp_path / "test_project"
    project.mkdir()

    assets_dir = project / "assets"
    assets_dir.mkdir()
    mock = mocker.Mock()

    mocker.patch.object(mock, "tailwind", None)
    mocker.patch.object(mock, "plugins", [])
    mocker.patch("reflex.compiler.compiler.get_config", return_value=mock)

    (assets_dir / "style.css").touch()
    mocker.patch("reflex.compiler.compiler.Path.cwd", return_value=project)

    stylesheets = [
        "/style.css",
    ]

    assert compiler.compile_root_stylesheet(stylesheets) == (
        str(Path(".web") / "styles" / (PageNames.STYLESHEET_ROOT + ".css")),
        "@layer __reflex_base;\n@import url('./__reflex_style_reset.css');\n@import url('./style.css');",
    )


def test_compile_stylesheets_no_reset(tmp_path: Path, mocker: MockerFixture):
    """Test that stylesheets compile correctly without reset styles.

    Args:
        tmp_path: The test directory.
        mocker: Pytest mocker object.
    """
    project = tmp_path / "test_project"
    project.mkdir()

    assets_dir = project / "assets"
    assets_dir.mkdir()

    (assets_dir / "style.css").write_text(
        "button.rt-Button {\n\tborder-radius:unset !important;\n}"
    )
    mocker.patch("reflex.compiler.compiler.Path.cwd", return_value=project)
    mocker.patch(
        "reflex.compiler.compiler.get_web_dir",
        return_value=project / constants.Dirs.WEB,
    )
    mocker.patch(
        "reflex.compiler.utils.get_web_dir", return_value=project / constants.Dirs.WEB
    )

    stylesheets = ["/style.css"]

    # Test with reset_style=False
    assert compiler.compile_root_stylesheet(stylesheets, reset_style=False) == (
        str(
            project
            / constants.Dirs.WEB
            / "styles"
            / (PageNames.STYLESHEET_ROOT + ".css")
        ),
        "@layer __reflex_base;\n@import url('./style.css');",
    )


def test_compile_stylesheets_includes_radix_plugin(
    tmp_path: Path, mocker: MockerFixture
):
    """Explicit RadixThemesPlugin should add the Radix stylesheet import."""
    project = tmp_path / "test_project"
    project.mkdir()

    assets_dir = project / "assets"
    assets_dir.mkdir()
    (assets_dir / "style.css").write_text(".root { color: red; }")

    config = mocker.Mock()
    config.plugins = [rx.plugins.RadixThemesPlugin()]
    mocker.patch("reflex.compiler.compiler.get_config", return_value=config)
    mocker.patch("reflex.compiler.compiler.Path.cwd", return_value=project)
    mocker.patch(
        "reflex.compiler.compiler.get_web_dir",
        return_value=project / constants.Dirs.WEB,
    )
    mocker.patch(
        "reflex.compiler.utils.get_web_dir", return_value=project / constants.Dirs.WEB
    )

    assert compiler.compile_root_stylesheet(["/style.css"]) == (
        str(
            project
            / constants.Dirs.WEB
            / "styles"
            / (PageNames.STYLESHEET_ROOT + ".css")
        ),
        "@layer __reflex_base;\n@import url('./__reflex_style_reset.css');\n@import url('@radix-ui/themes/styles.css');\n@import url('./style.css');",
    )


def test_compile_app_root_omits_radix_window_library_by_default():
    """Apps without Radix should not import it in the app root."""
    reset_bundled_libraries()

    _, code = compiler.compile_app_root(rx.el.div("hello"))

    assert "@radix-ui/themes" not in code


def test_compile_preserves_app_bundle_registrations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
):
    """Keep module-level registrations available to pages and the emitted bundle.

    Args:
        tmp_path: Directory for compiler output.
        monkeypatch: Fixture for changing the app directory.
        mocker: Fixture for configuring the test app.
    """
    monkeypatch.chdir(tmp_path)
    with RegistrationContext() as context:

        class FrontendLibraryPlugin(rx.plugins.Plugin):
            """Contribute a library only while the plugin is configured."""

            def get_frontend_dependencies(self, **context) -> tuple[str, ...]:
                """Return the library contributed by this plugin.

                Returns:
                    The frontend dependency to bundle.
                """
                return ("compile-only-library",)

        config = rx.Config(app_name="bundle_test", plugins=[FrontendLibraryPlugin()])
        mocker.patch("reflex_base.config._get_config", return_value=config)
        bundle_library("d3-format@3.1.0")
        app = rx.App()
        seen = []
        use_radix = True

        def index():
            """Record the registrations visible during page evaluation.

            Returns:
                A component that optionally enables Radix for this compile.
            """
            seen.append(tuple(RegistrationContext.get().bundled_libraries))
            return rx.text("hello") if use_radix else rx.el.div("hello")

        app.add_page(index)
        compiler.compile_app(app, dry_run=True, use_rich=False)
        assert seen
        assert all("d3-format" in libraries for libraries in seen)
        assert "d3-format" in context.bundled_libraries
        _, code = compiler.compile_app_root(rx.el.div())
        assert app_root_loaders(code) == [
            loader("@emotion/react", "emotion_react"),
            loader("d3-format", "d3_format"),
            loader("compile-only-library", "compile_only_library"),
            loader("@radix-ui/themes", "radix_ui_themes"),
        ]
        assert "compile-only-library" in context.bundled_libraries
        assert "@radix-ui/themes" in context.bundled_libraries

        config.plugins.clear()
        use_radix = False
        compiler.compile_app(app, dry_run=True, use_rich=False)
        assert all("d3-format" in libraries for libraries in seen)
        assert "d3-format" in context.bundled_libraries
        assert "compile-only-library" not in context.bundled_libraries
        assert "@radix-ui/themes" not in context.bundled_libraries


def test_compile_preserves_lazily_imported_bundle_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
):
    """Retain an app registration first imported while evaluating a page.

    Args:
        tmp_path: The temporary application directory.
        monkeypatch: Fixture for selecting the app directory and import path.
        mocker: Fixture for configuring the application.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    module_name = "lazy_bundle_registration_test"
    (tmp_path / f"{module_name}.py").write_text(
        "from reflex_base.components.dynamic import bundle_library\n"
        'bundle_library("d3-format@3.1.0")\n'
    )
    with RegistrationContext() as context:
        config = rx.Config(app_name="lazy_bundle_test", plugins=[])
        mocker.patch("reflex_base.config._get_config", return_value=config)
        app = rx.App()

        def index():
            """Import the registration module when the page is evaluated.

            Returns:
                A component without implicit plugin dependencies.
            """
            importlib.import_module(module_name)
            return rx.el.div("hello")

        app.add_page(index)
        try:
            for _ in range(2):
                compiler.compile_app(app, dry_run=True, use_rich=False)
                assert "d3-format" in context.bundled_libraries
        finally:
            sys.modules.pop(module_name, None)


@pytest.mark.parametrize("lazy", [False, True])
def test_compile_app_root_uses_unique_window_library_aliases(
    lazy: bool, mocker: MockerFixture
):
    """Bundle subpaths with valid, distinct aliases in eager and lazy mode.

    Args:
        lazy: Whether application libraries should be loaded lazily.
        mocker: Fixture for configuring the bundle loading mode.
    """
    with RegistrationContext():
        mocker.patch(
            "reflex_base.config._get_config",
            return_value=rx.Config(
                app_name="testing", frontend_lazy_bundled_libraries=lazy
            ),
        )
        bundle_library("foo.bar")
        bundle_library("foo_bar")
        bundle_library("foo/bar.mjs")
        _, code = compiler.compile_app_root(rx.el.div("hello"))

    if lazy:
        loader = (
            '    "{}": () => import("$/utils/dynamic_libraries/{}")'
            ".then((module) => module.default),"
        )
        lines = code.splitlines()
        assert loader.format("foo.bar", "foo_bar") in lines
        assert loader.format("foo_bar", "foo_bar_2") in lines
        assert loader.format("foo/bar.mjs", "foo_bar_mjs") in lines
    else:
        assert 'import * as foo_bar from "foo.bar";' in code
        assert 'import * as foo_bar_2 from "foo_bar";' in code
        assert 'import * as foo_bar_mjs from "foo/bar.mjs";' in code


def test_compile_app_root_omits_hydrate_fallback_by_default():
    """Apps without a hydrate_fallback should not export a HydrateFallback."""
    reset_bundled_libraries()

    _, code = compiler.compile_app_root(rx.el.div("hello"))

    assert "HydrateFallback" not in code


def test_compile_app_root_with_hydrate_fallback_exports_hydrate_fallback():
    """A hydrate_fallback memo export should be re-exported as HydrateFallback."""
    reset_bundled_libraries()

    _, code = compiler.compile_app_root(rx.el.div("hello"), "MyFallback")

    assert (
        "export { MyFallback as HydrateFallback } "
        'from "$/utils/components/MyFallback";' in code
    )


def test_compile_app_root_includes_radix_window_library_when_bundled(mocker):
    """Bundled Radix libraries should be exposed to window.__reflex."""
    mocker.patch(
        "reflex.compiler.compiler.get_config",
        return_value=rx.Config(
            app_name="eager_libraries", frontend_lazy_bundled_libraries=False
        ),
    )
    reset_bundled_libraries()
    try:
        bundle_library("@radix-ui/themes@3.3.0")

        _, code = compiler.compile_app_root(rx.el.div("hello"))

        assert 'import * as radix_ui_themes from "@radix-ui/themes";' in code
        assert '"@radix-ui/themes": radix_ui_themes' in code
    finally:
        reset_bundled_libraries()


_APP_ROOT_HEAD = """
import {Fragment,createElement as jsx,useEffect} from "react"

import { defaultColorMode } from "$/utils/context";
import { ThemeProvider } from '$/utils/react-theme';
import { Layout as AppLayout } from './_document';
import { Outlet } from 'react-router';
import * as React from "react";
import * as utils_context from "$/utils/context";
import * as utils_context_registry from "$/utils/context-registry";
import * as utils_state from "$/utils/state";
"""

_APP_ROOT_TAIL = """
  return jsx(ThemeProvider, {defaultTheme: defaultColorMode, attribute: "class"},
    jsx(AppWrap, {}, children)
  );
}


function AppWrap({children}) {

return (jsx("div",{},"hello"))
}

export function Layout({children}) {
  return jsx(AppLayout, {}, jsx(ReflexProviders, {}, children));
}

// Used by entry.client.js when mount_target is configured: skips the document
// shell (which renders react-router's <Meta>/<Scripts>/<Links> and requires a
// framework router context) but keeps the runtime providers.
export function EmbedLayout({children}) {
  return jsx(ReflexProviders, {}, children);
}

export default function App() {
  return jsx(Outlet, {});
}

"""

_APP_ROOT_WITHOUT_LOADERS = (
    _APP_ROOT_HEAD
    + """



function ReflexProviders({children}) {
  useEffect(() => {
    // Make contexts and state objects available globally for dynamic eval'd components
    window.__reflex = {
          "react": React,
    "$/utils/context": utils_context,
    "$/utils/context-registry": utils_context_registry,
    "$/utils/state": utils_state,
    };
  }, []);
"""
    + _APP_ROOT_TAIL
)


def _app_root_with_loaders(*loaders: str) -> str:
    """Build the root.jsx that loads optional libraries on demand.

    Args:
        *loaders: The loader entry of each optional library, in order.

    Returns:
        The complete expected module.
    """
    return (
        _APP_ROOT_HEAD
        + """
if (typeof window !== "undefined") {
  window.__reflex = { ...window.__reflex,
        "react": React,
    "$/utils/context": utils_context,
    "$/utils/context-registry": utils_context_registry,
    "$/utils/state": utils_state,
  };
  const loaders = {
"""
        + "".join(f"    {loader}\n" for loader in loaders)
        + """  };
  const pending = Object.create(null);
  window.__reflex_load = (libraries = Object.keys(loaders)) => {
    return Promise.all(libraries.filter((name) => Object.hasOwn(loaders, name) && !Object.hasOwn(window.__reflex, name)).map((name) => {
      if (!pending[name]) {
        pending[name] = loaders[name]().then((module) => {
          window.__reflex[name] = module;
        }).catch((error) => {
          delete pending[name];
          throw error;
        });
      }
      return pending[name];
    }));
  };
}




function ReflexProviders({children}) {
  \n"""
        + _APP_ROOT_TAIL
    )


_EMOTION_LOADER = '"@emotion/react": () => import("$/utils/dynamic_libraries/emotion_react").then((module) => module.default),'
_RADIX_LOADER = '"@radix-ui/themes": () => import("$/utils/dynamic_libraries/radix_ui_themes").then((module) => module.default),'
_D3_LOADER = '"d3-format": () => import("$/utils/dynamic_libraries/d3_format").then((module) => module.default),'
_EMOTION_MODULE = (
    "emotion_react.js",
    'import * as library from "@emotion/react";\nexport default library;\n',
)
_RADIX_MODULE = (
    "radix_ui_themes.js",
    'import * as library from "@radix-ui/themes";\nexport default library;\n',
)
_D3_MODULE = (
    "d3_format.js",
    'import * as library from "d3-format";\nexport default library;\n',
)


@pytest.mark.parametrize(
    ("app_libraries", "dynamic_components", "expected_root", "expected_modules"),
    [
        pytest.param(
            (),
            True,
            _app_root_with_loaders(_EMOTION_LOADER, _RADIX_LOADER),
            [_EMOTION_MODULE, _RADIX_MODULE],
            id="dynamic_components",
        ),
        pytest.param(
            (), False, _APP_ROOT_WITHOUT_LOADERS, [], id="no_dynamic_components"
        ),
        pytest.param(
            ("d3-format@3.1.0",),
            True,
            _app_root_with_loaders(_EMOTION_LOADER, _RADIX_LOADER, _D3_LOADER),
            [_EMOTION_MODULE, _RADIX_MODULE, _D3_MODULE],
            id="dynamic_components_and_app_library",
        ),
        pytest.param(
            ("d3-format@3.1.0",),
            False,
            _app_root_with_loaders(_D3_LOADER),
            [_D3_MODULE],
            id="app_library_only",
        ),
    ],
)
def test_compile_app_root_loads_optional_libraries_on_demand(
    app_libraries: tuple[str, ...],
    dynamic_components: bool,
    expected_root: str,
    expected_modules: list[tuple[str, str]],
    mocker: MockerFixture,
):
    """Keep optional library namespaces out of root.jsx, in modules of their own.

    A library the compiler registered is only loadable when the app renders a
    dynamic component, a library the app registered is always loadable. Emotion
    is one of the former: only a dynamic component with a ``css`` prop calls it.

    Args:
        app_libraries: The libraries the app registers with bundle_library.
        dynamic_components: Whether the app renders a dynamic component.
        expected_root: The complete expected root.jsx.
        expected_modules: The expected file name and code of each library module.
        mocker: Fixture for configuring the app.
    """
    mocker.patch(
        "reflex_base.config._get_config",
        return_value=rx.Config(app_name="lazy_libraries"),
    )
    with RegistrationContext():
        _bundle_library("@radix-ui/themes")
        for library in app_libraries:
            bundle_library(library)
        root_path, code = compiler.compile_app_root(
            rx.el.div("hello"), dynamic_components=dynamic_components
        )
        modules = compiler.compile_dynamic_libraries(
            dynamic_components=dynamic_components
        )

    assert root_path == str(prerequisites.get_web_dir() / "app" / "root.jsx")
    assert code == expected_root
    assert modules == [
        (
            str(prerequisites.get_web_dir() / "utils" / "dynamic_libraries" / name),
            module_code,
        )
        for name, module_code in expected_modules
    ]


def test_compile_dynamic_libraries_is_empty_for_eager_libraries(mocker: MockerFixture):
    """Write no library modules when root.jsx imports the namespaces itself.

    Args:
        mocker: Fixture for configuring the app.
    """
    mocker.patch(
        "reflex_base.config._get_config",
        return_value=rx.Config(
            app_name="eager_libraries", frontend_lazy_bundled_libraries=False
        ),
    )
    with RegistrationContext():
        bundle_library("d3-format@3.1.0")
        assert compiler.compile_dynamic_libraries() == []


@pytest.mark.parametrize("dynamic", [False, True])
def test_compile_detects_dynamic_components(
    dynamic: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    """Tell the app root whether any page renders a dynamic component.

    Args:
        dynamic: Whether the page renders a component held in state.
        tmp_path: Directory for compiler output.
        monkeypatch: Fixture for changing the app directory.
        mocker: Fixture for configuring the test app.
    """
    monkeypatch.chdir(tmp_path)
    with RegistrationContext():
        mocker.patch(
            "reflex_base.config._get_config",
            return_value=rx.Config(app_name="dynamic_detection", plugins=[]),
        )

        class DynamicDetectionState(rx.State):
            """A state holding a component and a plain value."""

            component: rx.Component = rx.el.div("dynamic")
            text: str = "static"

        def index() -> rx.Component:
            """Render the component or the plain value from state.

            Returns:
                The page.
            """
            return rx.el.div(
                DynamicDetectionState.component
                if dynamic
                else DynamicDetectionState.text
            )

        app = rx.App()
        app.add_page(index)
        compile_root = mocker.spy(compiler, "compile_app_root")
        compile_libraries = mocker.spy(compiler, "compile_dynamic_libraries")
        compiler.compile_app(app, dry_run=True, use_rich=False)

    assert compile_root.call_args.kwargs == {"dynamic_components": dynamic}
    assert compile_libraries.call_args == mocker.call(dynamic_components=dynamic)


def _mock_config_color_mode(mocker: MockerFixture, mode: LiteralColorMode) -> None:
    """Point the compiler's get_config at a fresh config with the given mode.

    Builds a standalone Config rather than mutating the shared singleton so the
    override cannot leak into other tests regardless of execution order.

    Args:
        mocker: Pytest mocker fixture.
        mode: The default color mode to configure.
    """
    config = rx.Config(
        app_name="test_default_color_mode",
        default_color_mode=mode,
        _skip_plugins_checks=True,
    )
    mocker.patch("reflex.compiler.compiler.get_config", return_value=config)


@pytest.mark.parametrize("mode", ["system", "light", "dark"])
def test_compile_contexts_uses_config_default_color_mode(
    mode: LiteralColorMode, mocker: MockerFixture
):
    """The Config.default_color_mode option should drive the compiled default."""
    _mock_config_color_mode(mocker, mode)

    _, code = compiler.compile_contexts(None, None)

    assert f'export const defaultColorMode = "{mode}"' in code


def test_compile_contexts_theme_appearance_overrides_config(mocker: MockerFixture):
    """An explicit theme appearance should still win over the config default."""
    _mock_config_color_mode(mocker, "light")

    _, code = compiler.compile_contexts(None, rx.theme(appearance="dark"))

    assert 'export const defaultColorMode = "dark"' in code


def test_compile_contexts_embeds_frontend_state_schema():
    """The context module carries the hash of the state tree it was compiled for.

    The frontend sends it on every socket connect, and the backend computes
    the same function over its own tree, so the two values drift only when
    the trees do.
    """

    # A root of its own: compiling rx.State would instantiate every state other
    # test modules registered in this process.
    class SchemaContextRoot(BaseState):
        value: int = 0

    class SchemaContextChild(SchemaContextRoot):
        name: str = ""

    _, code = compiler.compile_contexts(SchemaContextRoot, None)

    schema = SchemaContextRoot._to_frontend_schema()
    assert f'export const stateSchema = "{schema}"' in code
    on_load_internal_event = (
        f"{SchemaContextRoot.get_full_name()}.{constants.CompileVars.ON_LOAD_INTERNAL}"
    )
    assert f"export const on_load_internal_event = '{on_load_internal_event}'" in code
    start = code.index("registerApp({")
    assert "stateSchema," in code[start : code.index("});", start)]
    assert "on_load_internal_event," in code[start : code.index("});", start)]
    assert SchemaContextChild.get_full_name() in code

    # Without state there is nothing to compare, and nothing to connect with.
    _, code = compiler.compile_contexts(None, None)
    assert "export const stateSchema = null" in code
    assert "export const on_load_internal_event = undefined" in code


@pytest.mark.parametrize(
    ("theme", "config_mode", "expected"),
    [
        (None, "system", "system"),
        (None, "dark", "dark"),
        (None, "light", "light"),
        # An explicit theme appearance wins over the config default.
        (rx.theme(appearance="dark"), "light", "dark"),
        # "inherit" (the default) falls back to the config default.
        (rx.theme(appearance="inherit"), "dark", "dark"),
        (rx.theme(), "dark", "dark"),
    ],
)
def test_resolve_default_color_mode(
    theme, config_mode: LiteralColorMode, expected: str, mocker: MockerFixture
):
    """The resolved default matches theme appearance, else the config default."""
    _mock_config_color_mode(mocker, config_mode)

    assert compiler._resolve_default_color_mode(theme) == expected


@pytest.mark.parametrize("mode", ["system", "light", "dark"])
def test_preload_color_theme_uses_default(mode: str):
    """The preload script falls back to the given default when no theme is saved."""
    from reflex.utils.misc import preload_color_theme

    code = str(preload_color_theme(mode))

    assert f"|| {mode!r}" in code


def test_compile_document_root_bakes_default_color_mode(mocker: MockerFixture):
    """compile_document_root threads the resolved default into the preload script."""
    _mock_config_color_mode(mocker, "dark")
    mocker.patch(
        "reflex.compiler.compiler.get_web_dir",
        return_value=Path("/tmp/does_not_matter"),
    )

    _, code = compiler.compile_document_root(
        [], default_color_mode=compiler._resolve_default_color_mode(None)
    )

    assert "|| 'dark'" in code


def test_compile_document_root_prod(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
):
    """A production document preloads its stylesheet and no script of its own.

    Its scripts are the Reflex wrapper of react-router's, which starts them
    after the first paint on a prerendered page.
    """
    monkeypatch.setenv("REFLEX_ENV_MODE", constants.Env.PROD.value)
    mocker.patch(
        "reflex.compiler.compiler.get_web_dir",
        return_value=Path("/tmp/does_not_matter"),
    )

    path, code = compiler.compile_document_root([], default_color_mode="system")

    theme_script = preload_color_theme("system").render()["children"][0]["contents"]
    assert path == str(Path("/tmp/does_not_matter/app/_document.js"))
    assert (
        code
        == f"""import {{Links,Meta,ScrollRestoration}} from "react-router"
import reflexGlobalStyles from "$/styles/__reflex_global_styles.css?url"
import {{Scripts}} from "$/utils/scripts"
import {{Fragment,createElement as jsx,useEffect}} from "react"

export function Layout({{children}}) {{
  return (
    jsx("html",{{lang:"en"}},jsx("head",{{}},jsx("script",{{}},{theme_script}),jsx("meta",{{charSet:"utf-8"}},),jsx("meta",{{content:"width=device-width, initial-scale=1",name:"viewport"}},),jsx(Meta,{{}},),jsx("link",{{as:"style",href:reflexGlobalStyles,rel:"preload"}},),jsx("link",{{href:reflexGlobalStyles,rel:"stylesheet",type:"text/css"}},),jsx(Links,{{}},)),jsx("body",{{}},children,jsx(ScrollRestoration,{{}},),jsx(Scripts,{{}},)))
  )
}}"""
    )


def test_compile_nonexistent_stylesheet(tmp_path, mocker: MockerFixture):
    """Test that an error is thrown for non-existent stylesheets.

    Args:
        tmp_path: The test directory.
        mocker: Pytest mocker object.
    """
    project = tmp_path / "test_project"
    project.mkdir()

    assets_dir = project / "assets"
    assets_dir.mkdir()

    mocker.patch("reflex.compiler.compiler.Path.cwd", return_value=project)

    stylesheets = ["/style.css"]

    with pytest.raises(FileNotFoundError):
        compiler.compile_root_stylesheet(stylesheets)


@pytest.fixture
def dev_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin dev mode, whose document head omits the stylesheet preload.

    Args:
        monkeypatch: Selects dev mode and restores the previous mode afterwards.
    """
    monkeypatch.setenv("REFLEX_ENV_MODE", constants.Env.DEV.value)


@pytest.mark.usefixtures("dev_mode")
def test_create_document_root():
    """Test that the document root is created correctly."""
    # Test with no components.
    root = utils.create_document_root()
    root.render()
    assert isinstance(root, Html)
    assert isinstance(root.children[0], Head)
    # Default language.
    lang = root.lang  # pyright: ignore [reportAttributeAccessIssue]
    assert isinstance(lang, LiteralStringVar)
    assert lang.equals(Var.create("en"))
    # No children in head.
    assert len(root.children[0].children) == 6
    assert isinstance(root.children[0].children[1], Meta)
    char_set = root.children[0].children[1].char_set  # pyright: ignore [reportAttributeAccessIssue]
    assert isinstance(char_set, LiteralStringVar)
    assert char_set.equals(Var.create("utf-8"))
    assert isinstance(root.children[0].children[2], Meta)
    name = root.children[0].children[2].name  # pyright: ignore [reportAttributeAccessIssue]
    assert isinstance(name, LiteralStringVar)
    assert name.equals(Var.create("viewport"))
    assert isinstance(root.children[0].children[3], document.Meta)
    assert isinstance(root.children[0].children[4], Link)
    assert isinstance(root.children[0].children[5], Links)


def test_add_meta_accepts_dynamic_description():
    """Dynamic page descriptions should be represented as component Vars."""

    class PageState(rx.State):
        description: str = "Dynamic description"

    page = rx.box()
    utils.add_meta(
        page,
        title="title",
        image="",
        meta=(),
        description=PageState.description,
    )

    description = page.children[1]
    assert isinstance(description, Description)
    assert description.content is PageState.description  # pyright: ignore [reportAttributeAccessIssue]


def test_add_meta_drops_empty_description():
    """An empty-string description keeps producing no description tag."""
    page = rx.box()
    utils.add_meta(
        page,
        title="title",
        image="",
        meta=(),
        description="",
    )

    assert not any(isinstance(child, Description) for child in page.children)


@pytest.mark.usefixtures("dev_mode")
def test_create_document_root_with_scripts():
    # Test with components.
    comps = [
        Scripts.create(src="foo.js"),
        Scripts.create(src="bar.js"),
    ]
    root = utils.create_document_root(
        head_components=comps,
        html_lang="rx",
        html_custom_attrs={"project": "reflex"},
    )
    assert isinstance(root, Html)
    assert len(root.children[0].children) == 8
    names = [c.tag for c in root.children[0].children]
    assert names == [
        "script",
        "Scripts",
        "Scripts",
        "meta",
        "meta",
        "Meta",
        "link",
        "Links",
    ]
    lang = root.lang  # pyright: ignore [reportAttributeAccessIssue]
    assert isinstance(lang, LiteralStringVar)
    assert lang.equals(Var.create("rx"))
    assert isinstance(root.custom_attrs, dict)
    assert root.custom_attrs == {"project": "reflex"}


@pytest.mark.usefixtures("dev_mode")
def test_create_document_root_with_meta_char_set():
    # Test with components.
    comps = [
        Meta.create(char_set="cp1252"),
    ]
    root = utils.create_document_root(
        head_components=comps,
    )
    assert isinstance(root, Html)
    assert len(root.children[0].children) == 6
    names = [c.tag for c in root.children[0].children]
    assert names == ["script", "meta", "meta", "Meta", "link", "Links"]
    assert str(root.children[0].children[1].char_set) == '"cp1252"'  # pyright: ignore [reportAttributeAccessIssue]


@pytest.mark.usefixtures("dev_mode")
def test_create_document_root_with_meta_viewport():
    # Test with components.
    comps = [
        Meta.create(http_equiv="refresh", content="5"),
        Meta.create(name="viewport", content="foo"),
    ]
    root = utils.create_document_root(
        head_components=comps,
    )
    assert isinstance(root, Html)
    assert len(root.children[0].children) == 7
    names = [c.tag for c in root.children[0].children]
    assert names == ["script", "meta", "meta", "meta", "Meta", "link", "Links"]
    assert str(root.children[0].children[1].http_equiv) == '"refresh"'  # pyright: ignore [reportAttributeAccessIssue]
    assert str(root.children[0].children[2].name) == '"viewport"'  # pyright: ignore [reportAttributeAccessIssue]
    assert str(root.children[0].children[2].content) == '"foo"'  # pyright: ignore [reportAttributeAccessIssue]
    assert str(root.children[0].children[3].char_set) == '"utf-8"'  # pyright: ignore [reportAttributeAccessIssue]


class _RoutePlugin(rx.plugins.Plugin):
    """Plugin that records how often it contributes its route."""

    calls = 0

    def register_route(self, *, add_page, **_):
        """Contribute a page through the staged hook capability.

        Args:
            add_page: The staged page-adding capability.
            _: Additional hook context.
        """
        self.calls += 1
        add_page(lambda: rx.el.div("plugin page"), route="/plugin-page")


def test_register_plugin_routes_runs_once_per_app():
    """Route hooks run once and retain their contributed pages."""
    app = rx.App()
    plugin = _RoutePlugin()

    compiler._register_plugin_routes(app, [plugin])
    compiler._register_plugin_routes(app, [plugin])

    assert plugin.calls == 1
    assert "plugin-page" in app._unevaluated_pages


@pytest.mark.parametrize("with_stateful_marker", [False, True])
@pytest.mark.usefixtures("clean_registration_context")
def test_compile_registers_plugin_routes_on_backend_early_return(
    tmp_path: Path,
    mocker: MockerFixture,
    with_stateful_marker: bool,
):
    """Backend-only compiles register routes before either early-return path."""
    app = rx.App()
    plugin = _RoutePlugin()
    config = rx.Config(app_name="testing", plugins=[plugin])
    mocker.patch.object(app, "_apply_decorated_pages")
    mocker.patch.object(app, "_should_compile", return_value=False)
    compile_page = mocker.patch.object(app, "_compile_page")
    mocker.patch.object(app, "_add_optional_endpoints")
    mocker.patch.object(prerequisites, "get_backend_dir", return_value=tmp_path)
    mocker.patch.object(compiler, "get_config", return_value=config)

    if with_stateful_marker:
        (tmp_path / constants.Dirs.STATEFUL_PAGES).write_text(
            json.dumps(["plugin-page"])
        )

    assert compiler.compile_app(app, use_rich=False) is False
    assert "plugin-page" in app._unevaluated_pages
    if with_stateful_marker:
        compile_page.assert_called_once_with("plugin-page", save_page=False)
    else:
        compile_page.assert_any_call("plugin-page", save_page=False)


@pytest.mark.usefixtures("clean_registration_context")
def test_backend_compile_evaluates_all_pages_when_marker_missing(
    tmp_path: Path, mocker: MockerFixture
):
    """A backend dir without a complete marker falls through to evaluating every page.

    Another worker may have created the backend dir but not yet swapped its
    marker into place, so a missing marker must not be mistaken for "no
    stateful pages".
    """
    app = rx.App(enable_state=False)
    app.add_page(lambda: rx.fragment(), route="index")
    mocker.patch.object(app, "_apply_decorated_pages")
    mocker.patch.object(app, "_should_compile", return_value=False)
    compile_page = mocker.patch.object(app, "_compile_page")
    mocker.patch.object(app, "_add_optional_endpoints")
    mocker.patch.object(prerequisites, "get_backend_dir", return_value=tmp_path)
    mocker.patch.object(
        compiler, "get_config", return_value=rx.Config(app_name="testing", plugins=[])
    )

    assert compiler.compile_app(app, use_rich=False) is False

    assert {call.args[0] for call in compile_page.call_args_list} == {
        "index",
        constants.Page404.SLUG,
    }
    assert json.loads((tmp_path / constants.Dirs.STATEFUL_PAGES).read_text()) == []


@pytest.mark.usefixtures("clean_registration_context")
def test_backend_compile_restores_registry_before_initial_state_serialization(
    tmp_path: Path, mocker: MockerFixture
):
    """Backend-only compilation restores frontend metadata before serializing state."""

    class BackendState(rx.State):
        """State used to exercise backend-only compilation."""

    app = rx.App(_state=BackendState)
    mocker.patch.object(app, "_apply_decorated_pages")
    mocker.patch.object(app, "_should_compile", return_value=False)
    mocker.patch.object(app, "_add_optional_endpoints")
    mocker.patch.object(prerequisites, "get_backend_dir", return_value=tmp_path)
    mocker.patch.object(
        compiler, "get_config", return_value=rx.Config(app_name="testing", plugins=[])
    )
    calls = []
    restore = mocker.patch.object(
        utils, "_restore_bundled_libraries", side_effect=lambda: calls.append("restore")
    )
    compile_initial_state = mocker.patch.object(
        utils,
        "_compile_initial_state",
        side_effect=lambda _state: calls.append("initial_state"),
    )

    assert compiler.compile_app(app, use_rich=False) is False

    assert restore.call_args_list == [mocker.call()]
    assert compile_initial_state.call_args_list == [mocker.call(BackendState)]
    assert calls == ["restore", "initial_state"]


@pytest.mark.parametrize("with_stateful_marker", [False, True])
@pytest.mark.parametrize("with_saved_registry", [False, True])
@pytest.mark.parametrize("explicit_radix_plugin", [False, True])
@pytest.mark.usefixtures("clean_registration_context")
def test_backend_compile_derives_bundled_libraries_without_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    explicit_radix_plugin: bool,
    with_saved_registry: bool,
    with_stateful_marker: bool,
):
    """Without a saved registry, backend startup derives the frontend's libraries.

    Args:
        tmp_path: A temporary project directory without a frontend build.
        monkeypatch: Fixture for redirecting frontend and backend artifact paths.
        mocker: Fixture for selecting the backend-only compile path.
        explicit_radix_plugin: Whether rxconfig configures the Radix plugin.
        with_saved_registry: Whether a previous frontend compile left a registry.
        with_stateful_marker: Whether a previous start left a stateful-page marker.
    """
    monkeypatch.chdir(tmp_path)

    class BackendLibrariesState(rx.State):
        """State used to exercise backend bundled-library derivation."""

    def radix_page() -> Component:
        """Render a stateless page that only implicit Radix detection sees.

        Returns:
            A Radix Themes component.
        """
        return rx.text("radix")

    app = rx.App(_state=BackendLibrariesState)
    app.add_page(radix_page, route="/radix")
    mocker.patch.object(app, "_apply_decorated_pages")
    mocker.patch.object(app, "_should_compile", return_value=False)
    mocker.patch.object(app, "_add_optional_endpoints")
    plugins: list[rx.plugins.Plugin] = (
        [rx.plugins.RadixThemesPlugin()] if explicit_radix_plugin else []
    )
    mocker.patch.object(
        compiler,
        "get_config",
        return_value=rx.Config(app_name="testing", plugins=plugins),
    )

    web_dir = tmp_path / "web"
    registry_path = web_dir / constants.Dirs.BUNDLED_LIBRARIES
    if with_saved_registry:
        registry_path.parent.mkdir(parents=True)
        registry_path.write_text(json.dumps(["page-library"]), encoding="utf-8")
    monkeypatch.setattr(utils, "get_web_dir", lambda: web_dir)

    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    monkeypatch.setattr(prerequisites, "get_backend_dir", lambda: backend_dir)
    if with_stateful_marker:
        (backend_dir / constants.Dirs.STATEFUL_PAGES).write_text("[]", encoding="utf-8")

    serialized_libraries: list[list[str]] = []

    def record_libraries(state: type[BaseState]) -> None:
        """Record the libraries registered when the initial state is serialized.

        Args:
            state: The state class being serialized.
        """
        assert state is BackendLibrariesState
        serialized_libraries.append(list(RegistrationContext.get().bundled_libraries))

    mocker.patch.object(utils, "_compile_initial_state", side_effect=record_libraries)

    assert compiler.compile_app(app, use_rich=False) is False

    [libraries] = serialized_libraries
    if with_saved_registry:
        # The registry of a frontend compile is the frontend's exact library set.
        assert "page-library" in libraries
        assert json.loads(registry_path.read_text()) == ["page-library"]
    else:
        assert "@radix-ui/themes" in libraries
        # The derived set is saved so later starts restore it.
        assert json.loads(registry_path.read_text()) == libraries


def _compile_backend_only_app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    plugins: list[rx.plugins.Plugin],
) -> list[str]:
    """Run a backend-only compile with no registry over two Radix pages.

    Args:
        tmp_path: A temporary project directory without a frontend build.
        monkeypatch: Fixture for redirecting frontend and backend artifact paths.
        mocker: Fixture for selecting the backend-only compile path.
        plugins: The plugins configured in rxconfig.

    Returns:
        The routes of the app, in evaluation order.
    """
    monkeypatch.chdir(tmp_path)

    class BackendWalkState(rx.State):
        """State used to exercise backend page walks."""

    def radix_page() -> Component:
        """Render a page with a Radix Themes component.

        Returns:
            A Radix Themes component.
        """
        return rx.text("radix")

    app = rx.App(_state=BackendWalkState)
    app.add_page(radix_page, route="/radix")
    app.add_page(radix_page, route="/radix-2")
    mocker.patch.object(app, "_apply_decorated_pages")
    mocker.patch.object(app, "_should_compile", return_value=False)
    mocker.patch.object(app, "_add_optional_endpoints")
    mocker.patch.object(
        compiler,
        "get_config",
        return_value=rx.Config(app_name="testing", plugins=plugins),
    )
    monkeypatch.setattr(utils, "get_web_dir", lambda: tmp_path / "web")
    monkeypatch.setattr(prerequisites, "get_backend_dir", lambda: tmp_path / "backend")
    mocker.patch.object(utils, "_compile_initial_state")

    assert compiler.compile_app(app, use_rich=False) is False
    return list(app._unevaluated_pages)


@pytest.mark.parametrize(
    ("explicit_radix_plugin", "expected_walks"),
    [(True, 0), (False, 1)],
)
@pytest.mark.usefixtures("clean_registration_context")
def test_backend_compile_stops_walking_pages_once_no_hook_can_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    explicit_radix_plugin: bool,
    expected_walks: int,
):
    """Skip page traversal once an enabled Radix plugin is the only component hook.

    Args:
        tmp_path: A temporary project directory without a frontend build.
        monkeypatch: Fixture for redirecting frontend and backend artifact paths.
        mocker: Fixture for selecting the backend-only compile path.
        explicit_radix_plugin: Whether rxconfig configures the Radix plugin.
        expected_walks: The number of page trees traversed.
    """
    compile_component = mocker.spy(CompilerHooks, "compile_component")
    plugins: list[rx.plugins.Plugin] = (
        [rx.plugins.RadixThemesPlugin()] if explicit_radix_plugin else []
    )

    _compile_backend_only_app(tmp_path, monkeypatch, mocker, plugins)

    assert compile_component.call_count == expected_walks
    assert "@radix-ui/themes" in RegistrationContext.get().bundled_libraries


@pytest.mark.usefixtures("clean_registration_context")
def test_backend_compile_runs_radix_plugin_subclass_hooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
):
    """Keep an enabled Radix plugin subclass and its own hooks in the backend walk.

    Args:
        tmp_path: A temporary project directory without a frontend build.
        monkeypatch: Fixture for redirecting frontend and backend artifact paths.
        mocker: Fixture for selecting the backend-only compile path.
    """
    compiled_routes: list[str] = []

    class RecordingRadixPlugin(rx.plugins.RadixThemesPlugin):
        """A Radix plugin subclass with its own page hook."""

        def compile_page(self, page_ctx: PageContext, /, **kwargs) -> None:
            """Record the compiled route.

            Args:
                page_ctx: The page being compiled.
                kwargs: The compile hook context.
            """
            super().compile_page(page_ctx, **kwargs)
            compiled_routes.append(page_ctx.route)

    routes = _compile_backend_only_app(
        tmp_path, monkeypatch, mocker, [RecordingRadixPlugin()]
    )

    assert compiled_routes == routes


@pytest.mark.usefixtures("clean_registration_context")
def test_backend_compile_gives_page_hooks_the_compile_view(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
):
    """Page hooks see the replaced root and every page, as in a frontend compile.

    Args:
        tmp_path: A temporary project directory without a frontend build.
        monkeypatch: Fixture for redirecting frontend and backend artifact paths.
        mocker: Fixture for selecting the backend-only compile path.
    """
    replacements: dict[str, Component] = {}
    page_roots: dict[str, BaseComponent] = {}
    page_routes: dict[str, list[str]] = {}

    class RootReplacingPlugin(rx.plugins.Plugin):
        """Replace each page root and record what the page hook sees."""

        def enter_component(
            self,
            comp: BaseComponent,
            /,
            *,
            page_context: PageContext,
            compile_context: CompileContext,
            in_prop_tree: bool = False,
        ) -> Component | None:
            """Wrap the page root once.

            Args:
                comp: The component being compiled.
                page_context: The page being compiled.
                compile_context: The compile run.
                in_prop_tree: Whether the component is in a prop subtree.

            Returns:
                The replacement root, or None for other components.
            """
            if page_context.route in replacements:
                return None
            replacements[page_context.route] = rx.box(comp)
            return replacements[page_context.route]

        def compile_page(self, page_ctx: PageContext, /, **kwargs) -> None:
            """Record the page root and the pages of the compile run.

            Args:
                page_ctx: The page being compiled.
                kwargs: The compile hook context.
            """
            page_roots[page_ctx.route] = page_ctx.root_component
            page_routes[page_ctx.route] = [
                page.route for page in kwargs["compile_context"].pages
            ]

    routes = _compile_backend_only_app(
        tmp_path, monkeypatch, mocker, [RootReplacingPlugin()]
    )

    assert page_roots == replacements
    assert page_routes == dict.fromkeys(routes, routes)


@pytest.mark.usefixtures("clean_registration_context")
def test_frontend_compile_emits_bundled_library_registry(mocker: MockerFixture):
    """Frontend compilation emits the registry consumed by backend-only workers."""
    app = rx.App()

    def index():
        """Render an empty page.

        Returns:
            The empty page.
        """
        return rx.el.div()

    app.add_page(index)
    emitted_registry = mocker.patch.object(
        utils,
        "_compile_bundled_libraries",
        return_value=(constants.Dirs.BUNDLED_LIBRARIES, "[]"),
    )

    assert compiler.compile_app(app, dry_run=True, use_rich=False) is True

    emitted_registry.assert_called_once_with()


def test_register_plugin_routes_exposes_app_type_not_mutable_app():
    """The hook can validate the app class without bypassing staged writes."""
    observed: dict[str, object] = {}

    class InspectingPlugin(rx.plugins.Plugin):
        """Plugin recording its route-registration context."""

        def register_route(self, **context):
            """Record the context without contributing a page.

            Args:
                context: The route-registration capabilities.
            """
            observed.update(context)

    app = rx.App()

    compiler._register_plugin_routes(app, [InspectingPlugin()])

    assert observed["app_type"] is type(app)
    assert "app" not in observed


def test_register_plugin_routes_hook_failure_is_atomic():
    """A hook failure leaves no staged pages or dynamic route variables."""

    class PluginRouteState(BaseState):
        """State root isolated from the global state tree in this test."""

    class FirstPlugin(rx.plugins.Plugin):
        """Plugin whose contribution is collected before the failing hook."""

        def register_route(self, *, add_page, **_):
            """Contribute a page before the failing hook runs.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(lambda: rx.el.div(), route="/first-plugin-page")

    class FailingPlugin(rx.plugins.Plugin):
        """Plugin that raises after staging a dynamic route."""

        def register_route(self, *, add_page, **_):
            """Contribute a route and then fail.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.

            Raises:
                RuntimeError: Always after contributing the route.
            """
            add_page(lambda: rx.el.div(), route="/failed/[failed_plugin_arg]")
            msg = "plugin route registration failed"
            raise RuntimeError(msg)

    app = rx.App(_state=PluginRouteState)

    with pytest.raises(RuntimeError, match="plugin route registration failed"):
        compiler._register_plugin_routes(app, [FirstPlugin(), FailingPlugin()])

    assert not app._plugin_routes_registered
    assert "first-plugin-page" not in app._unevaluated_pages
    assert "failed/[failed_plugin_arg]" not in app._unevaluated_pages
    assert "failed_plugin_arg" not in PluginRouteState.computed_vars

    compiler._register_plugin_routes(app, [FirstPlugin()])

    assert app._plugin_routes_registered
    assert "first-plugin-page" in app._unevaluated_pages


def test_register_plugin_routes_rejects_app_route_conflict_atomically():
    """An app-owned route cannot be replaced by a plugin contribution."""

    class ConflictingPlugin(rx.plugins.Plugin):
        """Plugin claiming an app-owned route."""

        def register_route(self, *, add_page, **_):
            """Contribute the conflicting page.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(lambda: rx.el.div("plugin"), route="/shared")

    app = rx.App()
    app.add_page(lambda: rx.el.div("app"), route="/shared")

    with pytest.raises(
        RouteValueError,
        match=r"Plugin ConflictingPlugin.*`shared`.*defined by the app",
    ):
        compiler._register_plugin_routes(app, [ConflictingPlugin()])

    assert not app._plugin_routes_registered
    assert len(app._unevaluated_pages) == 1


def test_register_plugin_routes_rejects_plugin_conflict_atomically():
    """Two plugins cannot silently claim the same route."""

    class FirstPlugin(rx.plugins.Plugin):
        """First owner of the shared route."""

        def register_route(self, *, add_page, **_):
            """Contribute the shared page.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(lambda: rx.el.div("first"), route="/shared")

    class SecondPlugin(rx.plugins.Plugin):
        """Second claimant of the shared route."""

        def register_route(self, *, add_page, **_):
            """Contribute the conflicting shared page.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(lambda: rx.el.div("second"), route="/shared")

    app = rx.App()

    with pytest.raises(
        RouteValueError,
        match=r"Plugin SecondPlugin.*`shared`.*plugin FirstPlugin",
    ):
        compiler._register_plugin_routes(app, [FirstPlugin(), SecondPlugin()])

    assert not app._plugin_routes_registered
    assert "shared" not in app._unevaluated_pages


def test_register_plugin_routes_rejects_structural_app_conflict_atomically():
    """A plugin cannot change a dynamic slug name already owned by the app."""

    class StructuralRouteState(BaseState):
        """State root isolated from the global state tree in this test."""

    class ConflictingPlugin(rx.plugins.Plugin):
        """Plugin contributing a structurally conflicting dynamic route."""

        def register_route(self, *, add_page, **_):
            """Contribute the conflicting route.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(lambda: rx.el.div(), route="/posts/[slug]")

    app = rx.App(_state=StructuralRouteState)
    app.add_page(lambda: rx.el.div(), route="/posts/[id]")

    with pytest.raises(
        RouteValueError,
        match=r"Plugin ConflictingPlugin.*`posts/\[slug\]`.*`posts/\[id\]`.*app",
    ):
        compiler._register_plugin_routes(app, [ConflictingPlugin()])

    assert set(app._unevaluated_pages) == {"posts/[id]"}
    assert not app._plugin_routes_registered


def test_register_plugin_routes_rejects_structural_plugin_conflict_atomically():
    """Two plugins cannot use different slug names for one dynamic path."""

    class FirstPlugin(rx.plugins.Plugin):
        """Plugin owning the first dynamic route."""

        def register_route(self, *, add_page, **_):
            """Contribute the first route.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(lambda: rx.el.div(), route="/posts/[id]")

    class SecondPlugin(rx.plugins.Plugin):
        """Plugin contributing the conflicting route."""

        def register_route(self, *, add_page, **_):
            """Contribute the second route.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(lambda: rx.el.div(), route="/posts/[slug]")

    app = rx.App()

    with pytest.raises(
        RouteValueError,
        match=r"Plugin SecondPlugin.*plugin FirstPlugin.*dynamic segment names",
    ):
        compiler._register_plugin_routes(app, [FirstPlugin(), SecondPlugin()])

    assert app._unevaluated_pages == {}
    assert not app._plugin_routes_registered


def test_register_plugin_routes_has_app_page_excludes_plugin_contributions():
    """The route probe sees app pages but not staged plugin pages."""
    observed: list[tuple[bool, bool]] = []

    class ContributingPlugin(rx.plugins.Plugin):
        """Plugin staging a route before the probing plugin runs."""

        def register_route(self, *, add_page, **_):
            """Contribute a plugin-owned page.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(lambda: rx.el.div(), route="/plugin-page")

    class ProbingPlugin(rx.plugins.Plugin):
        """Plugin observing app and plugin route visibility."""

        def register_route(self, *, has_app_page, **_):
            """Record route-presence results.

            Args:
                has_app_page: The app-owned route probe.
                _: Additional hook context.
            """
            observed.append((
                has_app_page("/app-page/"),
                has_app_page("/plugin-page"),
            ))

    app = rx.App()
    app.add_page(lambda: rx.el.div(), route="/app-page")

    compiler._register_plugin_routes(
        app,
        [ContributingPlugin(), ProbingPlugin()],
    )

    assert observed == [(True, False)]


def test_register_plugin_routes_invalidates_router_cache():
    """Committing a plugin page refreshes a previously cached router."""
    app = rx.App()
    assert app.router("/plugin-page") is None

    compiler._register_plugin_routes(app, [_RoutePlugin()])

    assert app.router("/plugin-page") == "plugin-page"


def test_register_plugin_routes_preflights_missing_component():
    """An invalid contribution fails before the app commit begins."""

    class CountingApp(rx.App):
        """App recording committed prepared pages."""

        commit_calls = 0

        def _commit_page(self, prepared, **kwargs):
            """Record and commit a prepared page.

            Args:
                prepared: The prepared page descriptor.
                kwargs: Commit options.

            Returns:
                The result of the base commit.
            """
            self.commit_calls += 1
            return super()._commit_page(prepared, **kwargs)

    class InvalidPlugin(rx.plugins.Plugin):
        """Plugin omitting the component for a normal page."""

        def register_route(self, *, add_page, **_):
            """Stage the invalid contribution.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(route="/missing-component")

    app = CountingApp()

    with pytest.raises(PageValueError, match="Component must be set"):
        compiler._register_plugin_routes(app, [InvalidPlugin()])

    assert app.commit_calls == 0
    assert not app._plugin_routes_registered


def test_register_plugin_routes_preflights_dynamic_arg_conflicts():
    """Dynamic route conflicts fail before any contribution is committed."""

    class PluginRouteState(BaseState):
        """State with a variable that a plugin route must not shadow."""

        reserved_arg: str = ""

    class CountingApp(rx.App):
        """App recording committed prepared pages."""

        commit_calls = 0

        def _commit_page(self, prepared, **kwargs):
            """Record and commit a prepared page.

            Args:
                prepared: The prepared page descriptor.
                kwargs: Commit options.

            Returns:
                The result of the base commit.
            """
            self.commit_calls += 1
            return super()._commit_page(prepared, **kwargs)

    class InvalidPlugin(rx.plugins.Plugin):
        """Plugin contributing a route that shadows a state variable."""

        def register_route(self, *, add_page, **_):
            """Stage a valid page followed by a conflicting dynamic page.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(lambda: rx.el.div(), route="/valid")
            add_page(lambda: rx.el.div(), route="/[reserved_arg]")

    app = CountingApp(_state=PluginRouteState)

    with pytest.raises(
        DynamicRouteArgShadowsStateVarError,
        match="reserved_arg",
    ):
        compiler._register_plugin_routes(app, [InvalidPlugin()])

    assert app.commit_calls == 0
    assert not app._plugin_routes_registered
    assert app._unevaluated_pages == {}


def test_register_plugin_routes_rejects_inconsistent_dynamic_arg_types():
    """One dynamic argument cannot be both a scalar and a catch-all list."""

    class ScalarPlugin(rx.plugins.Plugin):
        """Plugin contributing the scalar form of a dynamic argument."""

        def register_route(self, *, add_page, **_):
            """Contribute the scalar route.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(lambda: rx.el.div(), route="/one/[splat]")

    class ListPlugin(rx.plugins.Plugin):
        """Plugin contributing the catch-all form of the same argument."""

        def register_route(self, *, add_page, **_):
            """Contribute the catch-all route.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(lambda: rx.el.div(), route="/two/[[...splat]]")

    app = rx.App()

    with pytest.raises(
        RouteValueError,
        match=r"Plugin ListPlugin.*`splat`.*type `list`.*type `single`",
    ):
        compiler._register_plugin_routes(app, [ScalarPlugin(), ListPlugin()])

    assert app._unevaluated_pages == {}
    assert not app._plugin_routes_registered


def test_register_plugin_routes_rejects_stale_dynamic_arg_type_from_prior_app():
    """A fresh app cannot reuse a stale DynamicRouteVar with another type."""

    class RouteState(BaseState):
        """State root deliberately shared by both app instances."""

    class ScalarPlugin(rx.plugins.Plugin):
        """Plugin installing a scalar dynamic argument."""

        def register_route(self, *, add_page, **_):
            """Contribute the scalar route.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(lambda: rx.el.div(), route="/one/[splat]")

    class ListPlugin(rx.plugins.Plugin):
        """Plugin attempting to reuse the argument as a catch-all list."""

        def register_route(self, *, add_page, **_):
            """Contribute the catch-all route.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(lambda: rx.el.div(), route="/two/[[...splat]]")

    first_app = rx.App(_state=RouteState)
    compiler._register_plugin_routes(first_app, [ScalarPlugin()])

    # A context only allows one App; fork (as an app reload does) to create the
    # second one while preserving the shared RouteState registration.
    with RegistrationContext.get().fork():
        second_app = rx.App(_state=RouteState)
        with pytest.raises(
            RouteValueError,
            match=r"Plugin ListPlugin.*`splat`.*type `list`.*already.*type `single`",
        ):
            compiler._register_plugin_routes(second_app, [ListPlugin()])

    assert second_app._unevaluated_pages == {}
    assert not second_app._plugin_routes_registered


def test_register_plugin_routes_uses_concrete_prepare_extension():
    """Staged pages use the concrete app's pure preparation extension."""

    class ExtendedApp(rx.App):
        """App accepting an extra page-registration argument."""

        def _prepare_page(self, component=None, *args, marker=None, **kwargs):
            """Store the custom marker in the prepared page context.

            Args:
                component: The page component.
                args: Base page arguments.
                marker: Custom page metadata.
                kwargs: Base page keyword arguments.

            Returns:
                The prepared page descriptor.
            """
            context = {**(kwargs.pop("context", None) or {}), "marker": marker}
            prepared = super()._prepare_page(
                component,
                *args,
                context=context,
                **kwargs,
            )
            return dataclasses.replace(
                prepared,
                page=dataclasses.replace(
                    prepared.page,
                    _source_module="app_extension",
                ),
            )

    class ExtendedPlugin(rx.plugins.Plugin):
        """Plugin using the concrete app's page extension."""

        def register_route(self, *, add_page, **_):
            """Contribute a page with custom metadata.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(lambda: rx.el.div(), route="/extended", marker="plugin")

    app = ExtendedApp()

    compiler._register_plugin_routes(app, [ExtendedPlugin()])

    assert app._unevaluated_pages["extended"].context == {"marker": "plugin"}
    # The concrete extension's explicit source-module rewrite is preserved.
    assert app._unevaluated_pages["extended"]._source_module == "app_extension"


def test_register_plugin_routes_checks_routes_after_concrete_preparation():
    """Concrete route rewriting cannot turn distinct inputs into last-wins."""

    class RewritingApp(rx.App):
        """App mapping every contributed route to one canonical location."""

        def _prepare_page(self, component=None, route=None, *args, **kwargs):
            """Rewrite the route before base preparation.

            Args:
                component: The page component.
                route: The ignored input route.
                args: Base page arguments.
                kwargs: Base page keyword arguments.

            Returns:
                The prepared page using the canonical route.
            """
            return super()._prepare_page(
                component,
                "/canonical",
                *args,
                **kwargs,
            )

    class RoutePlugin(rx.plugins.Plugin):
        """Plugin contributing a configurable input route."""

        def __init__(self, route: str):
            self.route = route

        def register_route(self, *, add_page, **_):
            """Contribute the input route.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(lambda: rx.el.div(), route=self.route)

    app = RewritingApp()

    with pytest.raises(
        RouteValueError,
        match=r"`canonical`.*plugin RoutePlugin \(plugins\[0\]\)",
    ):
        compiler._register_plugin_routes(
            app,
            [RoutePlugin("/first"), RoutePlugin("/second")],
        )

    assert app._unevaluated_pages == {}


def test_register_plugin_routes_does_not_evaluate_404_during_collection():
    """A later hook failure cannot trigger a staged 404 page callable."""
    calls: list[None] = []

    def not_found_page():
        calls.append(None)
        return rx.el.div("not found")

    class NotFoundPlugin(rx.plugins.Plugin):
        """Plugin contributing a custom 404 callable."""

        def register_route(self, *, add_page, **_):
            """Contribute the custom 404.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(not_found_page, route="/404")

    class FailingPlugin(rx.plugins.Plugin):
        """Plugin aborting the batch after 404 preparation."""

        def register_route(self, **_):
            """Abort route collection.

            Args:
                _: Hook context.

            Raises:
                RuntimeError: Always.
            """
            msg = "abort registration"
            raise RuntimeError(msg)

    app = rx.App()

    with pytest.raises(RuntimeError, match="abort registration"):
        compiler._register_plugin_routes(app, [NotFoundPlugin(), FailingPlugin()])

    assert calls == []
    assert app._unevaluated_pages == {}


def test_register_plugin_routes_uses_framework_commit_implementation():
    """A concrete commit override cannot make the staged batch partial."""

    class OverridingApp(rx.App):
        """App with a commit override that staged registration must bypass."""

        commit_calls = 0

        def _commit_page(self, prepared, **kwargs):
            """Reject direct commits.

            Args:
                prepared: The prepared page descriptor.
                kwargs: Commit options.

            Raises:
                RuntimeError: Always.
            """
            self.commit_calls += 1
            msg = "custom commit rejected page"
            raise RuntimeError(msg)

    app = OverridingApp()

    compiler._register_plugin_routes(app, [_RoutePlugin()])

    assert app.commit_calls == 0
    assert "plugin-page" in app._unevaluated_pages


def test_register_plugin_routes_preserves_component_source_module():
    """A prebuilt Component keeps the plugin hook's source-module provenance."""

    class ComponentPlugin(rx.plugins.Plugin):
        """Plugin contributing a prebuilt component rather than a callable."""

        def register_route(self, *, add_page, **_):
            """Contribute the prebuilt page.

            Args:
                add_page: The staged page-adding capability.
                _: Additional hook context.
            """
            add_page(rx.el.div("component page"), route="/component-page")

    app = rx.App()

    compiler._register_plugin_routes(app, [ComponentPlugin()])

    assert app._unevaluated_pages["component-page"]._source_module == __name__


@pytest.mark.parametrize("disable_owner_stacks", [True, False])
def test_context_template_owner_stack_pin(disable_owner_stacks: bool):
    """The owner-stack pin is emitted only when asked for, and only for the browser.

    The snippet mutates shared React internals, so it must never run in the
    server renderer, and it must disappear entirely when owner stacks are
    requested (REFLEX_REACT_OWNER_STACKS=1) or in production builds.

    Args:
        disable_owner_stacks: Whether the pin should be emitted.
    """
    from reflex_base.compiler.templates import context_template

    rendered = context_template(
        is_dev_mode=True,
        default_color_mode='"light"',
        disable_react_owner_stacks=disable_owner_stacks,
    )

    if not disable_owner_stacks:
        assert "recentlyCreatedOwnerStacks" not in rendered
        # React is only imported for the pin; without it the import is dead weight.
        assert not rendered.startswith("import React,")
        return

    assert "recentlyCreatedOwnerStacks" in rendered
    assert rendered.startswith("import React,")
    # Browser-only: the guard must wrap the mutation, not merely precede it.
    pin_at = rendered.index("recentlyCreatedOwnerStacks")
    guard_at = rendered.index('typeof window !== "undefined"')
    assert guard_at < pin_at
    assert "Object.defineProperty" in rendered
    # The documented escape hatch must be discoverable from the generated code.
    assert "REFLEX_REACT_OWNER_STACKS" in rendered
    # The trade-off must be stated where a reader of the output will see it.
    assert "captureOwnerStack" in rendered


def test_context_template_client_side_component_is_named():
    """``ClientSide`` returns a named component, not an anonymous arrow."""
    from reflex_base.compiler.templates import context_template

    rendered = context_template(is_dev_mode=True, default_color_mode='"light"')

    assert "function ClientSideComponent({ children, ...props })" in rendered
    assert (
        "ClientSideComponent.displayName = name ? `ClientSide(${name})` : "
        '"ClientSide";' in rendered
    )
    assert "return ClientSideComponent;" in rendered


def _render_page_template(route: str = "test/[dynamic]") -> str:
    """Render the page template for ``route``.

    Args:
        route: The route to compile the page for.

    Returns:
        The rendered page module source.
    """
    from reflex_base.compiler.templates import page_template

    return page_template(
        imports=[],
        dynamic_imports=[],
        custom_codes=[],
        hooks={},
        render=rx.el.div("hi").render(),
        route=route,
    )


def test_page_template_display_name_carries_the_route():
    """Every page compiles to ``Component``; its route is in the display name."""
    assert (
        'Component.displayName = "Component(test/[dynamic])";'
        in _render_page_template()
    )


def test_page_template_without_a_route_omits_the_display_name():
    """``route`` is optional so out-of-tree callers of the shipped template work.

    ``page_template`` is a public symbol in ``reflex-base``; a downstream
    compiler plugin that predates the parameter must keep working. Without a
    route there is no name worth showing, so the assignment is skipped entirely
    rather than emitting a contentless ``Component()`` label.
    """
    from reflex_base.compiler.templates import page_template

    rendered = page_template(
        imports=[],
        dynamic_imports=[],
        custom_codes=[],
        hooks={},
        render=rx.el.div("hi").render(),
    )

    assert "displayName" not in rendered
    assert "export default Component;" in rendered


def test_page_template_exports_the_component_binding_separately():
    """The page component is declared and named before it is exported.

    React Router rewrites an exported function *declaration* into a function
    *expression* wrapped in ``UNSAFE_withComponentProps``
    (``decorateComponentExportsWithProps``), which leaves no module-scope
    binding behind. A trailing ``Component.displayName = ...`` would then throw
    ``ReferenceError: Component is not defined`` when the route module loads,
    breaking every page. Exporting the identifier keeps the declaration intact.
    """
    rendered = _render_page_template()

    assert "export default function Component" not in rendered
    assert "\nfunction Component() {" in rendered
    assert rendered.index("Component.displayName") < rendered.index(
        "export default Component;"
    )


def test_compile_page_passes_its_route_to_the_template():
    """The route reaches the template through the legacy page compile path."""
    _, code = compiler.compile_page("about", rx.el.div("hi"))

    assert 'Component.displayName = "Component(about)";' in code


def test_no_ssr_dynamic_import_names_the_client_side_wrapper():
    """A client-only component passes its tag through to the wrapper's name."""
    from reflex_components_plotly.plotly import Plotly

    assert Plotly.create()._get_dynamic_imports().endswith(', "Plot")')


def test_compile_app_drops_event_caches_from_earlier_compiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
):
    """Chains and wrappers cached by an earlier compile do not outlive it.

    Args:
        tmp_path: Directory for compiler output.
        monkeypatch: Fixture for changing the app directory.
        mocker: Fixture for configuring the test app.
    """
    monkeypatch.chdir(tmp_path)
    with RegistrationContext() as context:
        config = rx.Config(app_name="event_cache_test", plugins=[])
        mocker.patch("reflex_base.config._get_config", return_value=config)
        app = rx.App()
        app.add_page(lambda: rx.el.div("hello"), route="/")
        stale = object()
        context._bound_event_chains[0, 0, None] = stale  # pyright: ignore[reportArgumentType]
        context._memoized_event_triggers["on_click", 0] = stale  # pyright: ignore[reportArgumentType]

        compiler.compile_app(app, dry_run=True, use_rich=False)

        assert (0, 0, None) not in context._bound_event_chains
        assert ("on_click", 0) not in context._memoized_event_triggers


@pytest.mark.parametrize(
    ("compile_context", "tier", "configured", "expected"),
    [
        # A deploy keeps an explicit setting whatever the stored login's tier:
        # the hosting CLI enforces the badge from the tier of the deploy token.
        (constants.CompileContext.DEPLOY, "free", False, False),
        (constants.CompileContext.DEPLOY, "team", True, True),
        # An unset setting follows the stored login's tier.
        (constants.CompileContext.DEPLOY, "free", None, True),
        (constants.CompileContext.DEPLOY, "pro", None, False),
        (constants.CompileContext.DEPLOY, "anonymous", None, True),
        # Outside of deploys the badge shows unless the app opts out.
        (constants.CompileContext.EXPORT, "free", None, True),
        (constants.CompileContext.EXPORT, "free", False, False),
        (constants.CompileContext.RUN, "pro", True, True),
    ],
)
def test_compile_app_resolves_show_built_with_reflex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    compile_context: constants.CompileContext,
    tier: str,
    configured: bool | None,
    expected: bool,
):
    """A production compile installs the badge according to the app's setting.

    Args:
        tmp_path: Directory for compiler output.
        monkeypatch: Fixture for changing the app directory and compile context.
        mocker: Fixture for configuring the test app, the user's tier and prod mode.
        compile_context: The context the app is compiled in.
        tier: The tier of the deploying user.
        configured: The app's own show_built_with_reflex setting.
        expected: The setting the compile should resolve to.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(environment.REFLEX_COMPILE_CONTEXT.name, compile_context.value)
    get_user_tier = mocker.patch(
        "reflex.utils.prerequisites.get_user_tier", return_value=tier
    )
    mocker.patch("reflex.compiler.compiler.is_prod_mode", return_value=True)
    with RegistrationContext():
        config = rx.Config(
            app_name="badge_test", plugins=[], show_built_with_reflex=configured
        )
        mocker.patch("reflex_base.config._get_config", return_value=config)
        app = rx.App()
        app.add_page(lambda: rx.el.div("hello"), route="/")

        compiler.compile_app(app, dry_run=True, use_rich=False)

        assert config.show_built_with_reflex is expected
        assert ((0, "StickyBadge") in app.app_wraps) is expected
    # Only an unset setting on a deploy needs the tier.
    assert get_user_tier.called is (
        compile_context == constants.CompileContext.DEPLOY and configured is None
    )


class _RefsDecl(rx.Fragment):
    """A wrapped component whose custom code declares its own ``refs``."""

    def add_custom_code(self) -> list[str]:
        """Declare a module-level ``refs`` binding.

        Returns:
            The declaration.
        """
        return ["const refs = {};"]


_IMPORTS_REFS = re.compile(
    r'^import\s*\{[^}]*\brefs\b[^}]*\}\s*from\s*"\$/utils/state"', re.MULTILINE
)


@pytest.mark.parametrize("auto_memoize", [True, False])
def test_custom_code_may_declare_refs(auto_memoize: bool):
    """Custom code may declare its own module-level ``refs``.

    No page or memo module imports ``refs`` unless a var asks for it, so a
    module never binds the name twice. Code that reads ``refs[...]`` without
    the import resolves the ``globalThis.refs`` that state.js publishes.

    Args:
        auto_memoize: Whether stateful components are auto-memoized.
    """

    @rx.memo
    def refs_decl_memo() -> rx.Component:
        return _RefsDecl.create()

    def page() -> Component:
        return rx.el.div(
            rx.el.input(id="target"),
            rx.el.button(on_click=rx.console_log("clicked")),
            _RefsDecl.create(),
            refs_decl_memo(),
        )

    page_ctx = PageContext(name="page", route="/page", root_component=page())
    hooks = CompilerHooks(plugins=default_page_plugins(auto_memoize=auto_memoize))
    compile_ctx = CompileContext(pages=[], hooks=hooks)
    with compile_ctx, page_ctx:
        page_ctx.root_component = hooks.compile_component(
            page_ctx.root_component,
            page_context=page_ctx,
            compile_context=compile_ctx,
        )
        hooks.compile_page(page_ctx, compile_context=compile_ctx)
        _, page_code = compiler.compile_page_from_context(page_ctx)
        memo_files, _ = compiler.compile_memo_components((
            *compile_ctx.auto_memo_components.values(),
            next(d for d in MEMOS.values() if d.python_name == "refs_decl_memo"),
        ))

    modules = [
        page_code,
        compiler._compile_page(page(), "/page"),
        *(code for _, code in memo_files),
    ]
    assert "const refs = {};" in page_code
    assert any("const refs = {};" in code for _, code in memo_files)
    for code in modules:
        assert not _IMPORTS_REFS.search(code), code


def _notify(message: str) -> rx.event.EventSpec:
    """Send a toast, as a helper an event handler calls.

    Args:
        message: The text of the toast.

    Returns:
        The toast event.
    """
    return rx.toast.info(message)


def _log(message: str) -> None:
    """Do something other than sending a toast.

    Args:
        message: The text to print.
    """
    print(message)


class _Notifier:
    """A class whose method sends a toast."""

    @staticmethod
    def warn(message: str) -> rx.event.EventSpec:
        """Send a warning toast.

        Args:
            message: The text of the toast.

        Returns:
            The toast event.
        """
        return rx.toast.warning(message)


def _closing_over(send: Any) -> Any:
    """Build a function that reaches ``send`` through its closure only.

    Args:
        send: The function to close over.

    Returns:
        A function calling ``send``.
    """

    def inner() -> Any:
        return send("closed over")

    return inner


_send_error = rx.toast.error
_notifier = _Notifier()
_this_module = sys.modules[__name__]
_closes_over_a_toast = _closing_over(rx.toast.success)
_closes_over_print = _closing_over(print)


@pytest.mark.parametrize(
    ("root", "expected"),
    [
        (lambda: rx.toast("direct"), True),
        (lambda: rx.toast.error("a level"), True),
        (lambda: [(lambda text: rx.toast(text))(text) for text in "ab"], True),
        (lambda: _send_error("an alias of a toast function"), True),
        (lambda: _notify("a helper function"), True),
        (lambda: _Notifier.warn("a helper class"), True),
        (lambda: _notifier.warn("an instance of a helper class"), True),
        (lambda: _this_module._notify("a helper reached through its module"), True),
        (_closes_over_a_toast, True),
        (_Notifier, True),
        (staticmethod(_notify), True),
        (rx.event.EventHandler(fn=_notify), True),
        (lambda: _log("no toast"), False),
        (lambda: rx.redirect("/elsewhere"), False),
        (lambda: json.dumps({"module": "of the standard library"}), False),
        (lambda: pytest.fail("an installed distribution is not followed"), False),
        (_closes_over_print, False),
        (dataclasses.dataclass, False),
        ("not code", False),
    ],
)
def test_references_toast(root: Any, expected: bool):
    """A toast is found through the names code refers to, in the app's modules.

    Args:
        root: The function, handler or class to start from.
        expected: Whether it reaches ``rx.toast``.
    """
    assert compiler._references_toast([root]) is expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (__name__, True),
        ("json", False),
        ("reflex.app", False),
        ("reflex_base.event", False),
        ("reflex_components_sonner.toast", False),
        ("pytest", False),
        ("a_module_nothing_imported", False),
    ],
)
def test_is_app_module(name: str, expected: bool):
    """The app's modules are what is neither Reflex, standard nor installed.

    Args:
        name: The dotted name of a module.
        expected: Whether it is the app's own code.
    """
    assert compiler._is_app_module(name) is expected


def _toast_wrap(app: rx.App, page: Component | None = None) -> str | None:
    """Resolve what an app puts in its app wrap to show toasts.

    Args:
        app: The app to resolve the app wraps of.
        page: A page of the app, or None for an app with no toast call in a page.

    Returns:
        "toaster" for the toaster, "plain" for plain notices, None for neither.
    """
    wraps = compiler._resolve_app_wrap_components(
        app, collect_subtree_app_wraps(page) if page is not None else {}
    )
    wrap = wraps.get((44, "ToasterProvider"))
    if wrap is None:
        return None
    if isinstance(wrap, compiler._PlainToast):
        return "plain"
    assert [child.tag for child in wrap.children if isinstance(child, Component)] == [
        memo_paths.mirrored_symbol("MemoizedToastProvider", compiler.__name__)
    ]
    return "toaster"


def _toast_button() -> Component:
    """Build a page that sends a toast from the frontend.

    Returns:
        A button whose click sends a toast.
    """
    return rx.el.button("Notify", on_click=rx.toast("Hello"))


@pytest.mark.usefixtures("clean_registration_context")
def test_toaster_of_an_app_without_state(mocker: MockerFixture):
    """Without state, only a toast call in the frontend can send a toast."""
    mocker.patch(
        "reflex_base.config._get_config", return_value=rx.Config(app_name="testing")
    )
    app = rx.App(enable_state=False)

    assert _toast_wrap(app) is None
    assert _toast_wrap(app, rx.el.div("Static")) is None
    assert _toast_wrap(app, _toast_button()) == "toaster"

    app.extra_app_wraps[1, "Notify"] = lambda _stateful: _toast_button()
    assert _toast_wrap(app) == "toaster"
    del app.extra_app_wraps[1, "Notify"]

    app.add_page(lambda: rx.el.div("Static"), route="/", on_load=rx.toast("Hi"))
    assert _toast_wrap(app) == "toaster"
    app._load_events["index"] = [lambda: _notify("From a function")]
    assert _toast_wrap(app) == "toaster"
    app._load_events["index"] = [lambda: rx.redirect("/elsewhere")]
    assert _toast_wrap(app) is None
    app._load_events.clear()

    app.toaster = rx.toast.provider()
    assert _toast_wrap(app) == "toaster"

    app.toaster = None
    assert _toast_wrap(app) is None
    assert _toast_wrap(app, _toast_button()) is None


@pytest.mark.usefixtures("clean_registration_context")
def test_toaster_of_an_app_whose_handlers_send_no_toast(mocker: MockerFixture):
    """With state and no toast found, toasts and connection errors show plainly."""
    mocker.patch(
        "reflex_base.config._get_config", return_value=rx.Config(app_name="testing")
    )

    class QuietState(rx.State):
        """A state whose handlers send no toast."""

        count: int = 0

        @rx.event
        def increment(self):
            """Count up, then go elsewhere.

            Returns:
                The redirect event.
            """
            self.count += 1
            return rx.redirect("/elsewhere")

    app = rx.App()

    assert _toast_wrap(app) == "plain"
    assert _toast_wrap(app, rx.el.div(QuietState.count)) == "plain"
    assert _toast_wrap(app, _toast_button()) == "toaster"

    app.backend_exception_handler = lambda exception: _notify(str(exception))
    assert _toast_wrap(app) == "toaster"
    app.backend_exception_handler = default_backend_exception_handler

    app.toaster = rx.toast.provider()
    assert _toast_wrap(app) == "toaster"

    app.toaster = None
    assert _toast_wrap(app) is None


@pytest.mark.parametrize("where", ["handler", "helper", "mixin", "substate"])
@pytest.mark.usefixtures("clean_registration_context")
def test_toaster_of_an_app_whose_backend_sends_a_toast(
    where: str, mocker: MockerFixture
):
    """A toast an event handler can send bundles the toaster.

    Args:
        where: The code of the state tree that refers to the toast.
        mocker: Fixture for configuring the test app.
    """
    mocker.patch(
        "reflex_base.config._get_config", return_value=rx.Config(app_name="testing")
    )

    if where == "handler":

        class HandlerState(rx.State):
            """A state whose handler sends a toast."""

            @rx.event
            def notify(self):
                """Send a toast.

                Returns:
                    The toast event.
                """
                return rx.toast("From the handler")

    elif where == "helper":

        class HelperState(rx.State):
            """A state whose handler sends a toast through a method."""

            @rx.event
            def notify(self):
                """Send what the helper method builds.

                Returns:
                    The toast event.
                """
                return self._build()

            def _build(self):
                return _notify("From a helper")

    elif where == "mixin":

        class Mixin(rx.State, mixin=True):
            """A mixin whose handler sends a toast."""

            @rx.event
            def notify(self):
                """Send a toast.

                Returns:
                    The toast event.
                """
                return rx.toast.success("From a mixin")

        class MixedState(Mixin, rx.State):
            """A state that takes its handler from the mixin."""

    else:

        class ParentState(rx.State):
            """A state that sends no toast."""

            @rx.event
            def quiet(self):
                """Do nothing."""

        class ChildState(ParentState):
            """A substate that sends a toast."""

            @rx.event
            def notify(self):
                """Send a toast.

                Returns:
                    The toast event.
                """
                return rx.toast("From a substate")

    assert _toast_wrap(rx.App()) == "toaster"


# What a module with no ``css`` prop calls ``jsx``, and what one with a ``css``
# prop does: only Emotion applies the prop.
REACT_JSX = 'import {Fragment,createElement as jsx,useEffect} from "react"'
EMOTION_JSX = [
    'import {Fragment,useEffect} from "react"',
    'import {jsx} from "@emotion/react"',
]
REACT_JSX_MEMO = 'import {Fragment,createElement as jsx,memo,useEffect} from "react"'
EMOTION_JSX_MEMO = [
    'import {jsx} from "@emotion/react"',
    'import {Fragment,memo,useEffect} from "react"',
]

_MEMO_NAME_HASH = re.compile(r"_[0-9a-f]{32}|_[0-9a-f]{8}\b")


def _module_imports(code: str) -> list[str]:
    """Get the import statements of a generated module.

    Args:
        code: The source of the module.

    Returns:
        Its import statements in order, with the hashes that name memos
        replaced by a placeholder.
    """
    return [
        _MEMO_NAME_HASH.sub("_<hash>", line)
        for line in code.splitlines()
        if line.startswith("import ")
    ]


class JsxImportState(BaseState):
    """What the pages of the ``jsx`` import tests are bound to."""

    color: str = "red"
    items: list[str] = ["a"]
    on: bool = True


class ThirdPartyPlain(Component):
    """A component of another package, with no style of its own."""

    library = "third-party"
    tag = "Plain"

    fallback: Var[Component]


class ThirdPartyThemed(ThirdPartyPlain):
    """A component of another package that adds a ``css`` prop as it renders."""

    tag = "Themed"

    def _render(self, props: dict[str, Any] | None = None):
        return super()._render(props).add_props(css=Var(_js_expr="theme"))


THIRD_PARTY_PLAIN = 'import {Plain} from "third-party"'

_RED = {"color": "red"}


@pytest.mark.parametrize(
    ("page", "style", "expected"),
    [
        pytest.param(lambda: rx.el.div("x"), None, [REACT_JSX], id="no_style"),
        pytest.param(lambda: rx.el.div("x", style=_RED), None, EMOTION_JSX, id="style"),
        pytest.param(
            lambda: rx.box("x", color="red"),
            None,
            ['import {Box as RadixThemesBox} from "@radix-ui/themes"', *EMOTION_JSX],
            id="style_keyword",
        ),
        pytest.param(
            lambda: rx.el.div("x"), {rx.el.div: _RED}, EMOTION_JSX, id="app_style"
        ),
        pytest.param(
            lambda: rx.el.div("x"),
            {rx.el.span: _RED},
            [REACT_JSX],
            id="app_style_of_another_component",
        ),
        pytest.param(
            lambda: ThirdPartyPlain.create(),
            None,
            [THIRD_PARTY_PLAIN, REACT_JSX],
            id="third_party",
        ),
        pytest.param(
            lambda: ThirdPartyThemed.create(),
            None,
            ['import {Themed} from "third-party"', *EMOTION_JSX],
            id="third_party_css_added_in_render",
        ),
        pytest.param(
            lambda: ThirdPartyPlain.create(custom_attrs={"css": _RED}),
            None,
            [THIRD_PARTY_PLAIN, *EMOTION_JSX],
            id="css_as_custom_attribute",
        ),
        pytest.param(
            lambda: ThirdPartyPlain.create(fallback=rx.el.span("a", style=_RED)),
            None,
            [
                THIRD_PARTY_PLAIN,
                'import {jsx} from "@emotion/react"',
                'import {Fragment,useEffect} from "react"',
                'import {pyOr} from "$/utils/state"',
            ],
            id="style_in_a_component_prop",
        ),
        pytest.param(
            lambda: ThirdPartyPlain.create(fallback=rx.el.span("a")),
            None,
            [THIRD_PARTY_PLAIN, REACT_JSX, 'import {pyOr} from "$/utils/state"'],
            id="component_prop",
        ),
        pytest.param(
            # A component that reaches the page as code carries no imports.
            lambda: ThirdPartyPlain.create(
                custom_attrs={"render": Var(f"() => {rx.el.i('a', style=_RED)!s}")}
            ),
            None,
            [
                THIRD_PARTY_PLAIN,
                'import {Fragment,useEffect} from "react"',
                'import {jsx} from "@emotion/react"',
            ],
            id="style_in_code_without_imports",
        ),
    ],
)
def test_page_imports_emotion_only_for_a_css_prop(
    page, style, expected: list[str], compile_page
):
    """A page calls React's ``createElement`` unless something in it has a ``css`` prop."""
    code = compile_page(page, style=style).compiled_pages["/"].output_code
    assert _module_imports(code) == expected


@pytest.mark.parametrize(
    ("page", "expected_page", "expected_memo"),
    [
        pytest.param(
            # The branches of a condition stay in the page.
            lambda: rx.el.div(
                rx.cond(JsxImportState.on, rx.el.span("a", style=_RED), rx.el.span("b"))
            ),
            [
                'import {Fragment,useEffect} from "react"',
                'import {Cond_comp_<hash>} from "$/utils/components/Cond_comp_<hash>"',
                'import {jsx} from "@emotion/react"',
            ],
            [
                'import {isTrue} from "$/utils/state"',
                'import {useStateContext} from "$/utils/context-registry"',
                REACT_JSX_MEMO,
            ],
            id="cond_with_style",
        ),
        pytest.param(
            lambda: rx.el.div(
                rx.cond(JsxImportState.on, rx.el.span("a"), rx.el.span("b"))
            ),
            [
                REACT_JSX,
                'import {Cond_comp_<hash>} from "$/utils/components/Cond_comp_<hash>"',
            ],
            [
                'import {isTrue} from "$/utils/state"',
                'import {useStateContext} from "$/utils/context-registry"',
                REACT_JSX_MEMO,
            ],
            id="cond",
        ),
        pytest.param(
            # The body of a loop moves into the module of the loop.
            lambda: rx.el.div(
                rx.foreach(JsxImportState.items, lambda i: rx.el.span(i, style=_RED))
            ),
            [
                'import {Foreach_comp_<hash>} from "$/utils/components/Foreach_comp_<hash>"',
                REACT_JSX,
            ],
            [
                'import {isTrue} from "$/utils/state"',
                'import {useStateContext} from "$/utils/context-registry"',
                *EMOTION_JSX_MEMO,
            ],
            id="foreach_with_style",
        ),
        pytest.param(
            lambda: rx.el.div(
                rx.foreach(JsxImportState.items, lambda i: rx.el.span(i))
            ),
            [
                'import {Foreach_comp_<hash>} from "$/utils/components/Foreach_comp_<hash>"',
                REACT_JSX,
            ],
            [
                'import {isTrue} from "$/utils/state"',
                'import {useStateContext} from "$/utils/context-registry"',
                REACT_JSX_MEMO,
            ],
            id="foreach",
        ),
        pytest.param(
            # An element bound to state moves into a module of its own, and
            # takes Emotion with it: the page it leaves no longer needs it.
            lambda: rx.el.div(
                rx.el.span("a", style={"color": JsxImportState.color}), rx.el.p("p")
            ),
            [
                'import {Span_span_<hash>} from "$/utils/components/Span_span_<hash>"',
                REACT_JSX,
            ],
            [
                'import {isTrue,mergeSlotProps} from "$/utils/state"',
                'import {useStateContext} from "$/utils/context-registry"',
                *EMOTION_JSX_MEMO,
            ],
            id="style_bound_to_state",
        ),
    ],
)
def test_auto_memo_module_imports_emotion_only_for_a_css_prop(
    page, expected_page: list[str], expected_memo: list[str], compile_page
):
    """The rule is applied to each generated module on its own."""
    ctx = compile_page(page)
    assert _module_imports(ctx.compiled_pages["/"].output_code) == expected_page
    ((_, memo_module),) = compiler.compile_memo_components(
        tuple(ctx.auto_memo_components.values())
    )[0]
    assert _module_imports(memo_module) == expected_memo


def test_rx_memo_module_imports_emotion_only_for_a_css_prop(
    compile_page, preserve_memo_registries: None
):
    """A memo with a ``css`` prop imports Emotion: the page that calls it does not."""

    @rx.memo
    def jsx_styled_memo() -> rx.Component:
        return rx.el.div("m", style=_RED)

    @rx.memo
    def jsx_plain_memo() -> rx.Component:
        return rx.el.div("m")

    def memo_imports(name: str) -> list[str]:
        ((_, code),) = compiler.compile_memo_components((
            next(memo for memo in MEMOS.values() if memo.python_name == name),
        ))[0]
        return _module_imports(code)

    assert memo_imports("jsx_styled_memo") == [
        'import {isTrue} from "$/utils/state"',
        *EMOTION_JSX_MEMO,
    ]
    assert memo_imports("jsx_plain_memo") == [
        'import {isTrue} from "$/utils/state"',
        REACT_JSX_MEMO,
    ]
    page = compile_page(lambda: rx.el.div(jsx_styled_memo(), jsx_plain_memo()))
    assert _module_imports(page.compiled_pages["/"].output_code) == [
        (
            "import {JsxPlainMemo_<hash>,JsxStyledMemo_<hash>} "
            'from "$/app_components/tests/units/compiler/test_compiler"'
        ),
        REACT_JSX,
    ]


@pytest.mark.parametrize(
    "component",
    [
        pytest.param(lambda: rx.el.div("x"), id="no_style"),
        pytest.param(lambda: rx.el.div("x", style=_RED), id="style"),
    ],
)
def test_module_built_from_the_imports_of_a_component_ships_emotion(component):
    """A plugin that writes a module of its own keeps the ``jsx`` that applies ``css``.

    It collects the imports of the components it renders and adds the common
    ones. Only a template of the compiler, which sees the code of the module,
    can tell that Emotion is not needed: imports alone always name it.
    """
    imports = component()._get_all_imports()
    compiler._apply_common_imports(imports)
    assert utils.compile_imports(imports) == [
        {"lib": "@emotion/react", "default": "", "rest": ["jsx"]},
        {"lib": "react", "default": "", "rest": ["Fragment", "useEffect"]},
    ]
