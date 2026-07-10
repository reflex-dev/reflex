import dataclasses
import importlib.util
import json
import os
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from reflex_base import constants
from reflex_base.components.dynamic import bundle_library, reset_bundled_libraries
from reflex_base.constants.compiler import PageNames
from reflex_base.utils.exceptions import (
    DynamicRouteArgShadowsStateVarError,
    PageValueError,
    RouteValueError,
)
from reflex_base.utils.imports import ImportVar, ParsedImportDict
from reflex_base.vars.base import Var
from reflex_base.vars.sequence import LiteralStringVar
from reflex_components_core.base import document
from reflex_components_core.base.document import Links, Scripts
from reflex_components_core.el.elements.metadata import Head, Link, Meta
from reflex_components_core.el.elements.other import Html

import reflex as rx
from reflex.compiler import compiler, utils
from reflex.state import BaseState


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
            f"@import url('./{Path('preprocess') / Path('styles_a.css')!s}');\n"
            f"@import url('./{Path('preprocess') / Path('styles_b.css')!s}');"
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
            f"@import url('./{Path('preprocess') / Path('styles_a.css')!s}');\n"
            f"@import url('./{Path('preprocess') / Path('styles_b.css')!s}');"
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


def test_compile_app_root_includes_radix_window_library_when_bundled():
    """Bundled Radix libraries should be exposed to window.__reflex."""
    reset_bundled_libraries()
    try:
        bundle_library("@radix-ui/themes@3.3.0")

        _, code = compiler.compile_app_root(rx.el.div("hello"))

        assert 'import * as radix_ui_themes from "@radix-ui/themes";' in code
        assert '"@radix-ui/themes": radix_ui_themes' in code
    finally:
        reset_bundled_libraries()


def test_compile_contexts_has_default_color_mode_context():
    """ColorModeContext should have a safe fallback value without Radix."""
    _, code = compiler.compile_contexts(None, None)

    assert "createContext({" in code
    assert 'resolvedColorMode: defaultColorMode === "dark" ? "dark" : "light"' in code


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
    mocker.patch.object(
        compiler.prerequisites, "get_backend_dir", return_value=tmp_path
    )
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
        compile_page.assert_not_called()


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
