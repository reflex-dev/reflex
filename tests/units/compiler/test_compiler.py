import importlib.util
import os
import re
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from reflex_base import constants
from reflex_base.compiler.templates import vite_config_template
from reflex_base.components.dynamic import bundle_library, reset_bundled_libraries
from reflex_base.constants.compiler import PageNames
from reflex_base.utils.imports import ImportVar, ParsedImportDict
from reflex_base.vars.base import Var
from reflex_base.vars.sequence import LiteralStringVar
from reflex_components_core.base import document
from reflex_components_core.base.document import Links, Scripts
from reflex_components_core.el.elements.metadata import Head, Link, Meta
from reflex_components_core.el.elements.other import Html

import reflex as rx
from reflex.compiler import compiler, utils


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


def test_compile_app_root_includes_radix_window_library_when_bundled():
    """Bundled Radix libraries are exposed to window.__reflex via named imports
    derived from the app's actual static usage (so Rolldown can tree-shake).
    """
    from reflex_base.utils.imports import ImportVar

    reset_bundled_libraries()
    try:
        bundle_library("@radix-ui/themes@3.3.0")

        window_library_imports = compiler.collect_window_library_imports([
            {"@radix-ui/themes@3.3.0": [ImportVar(tag="Theme")]},
        ])
        _, code = compiler.compile_app_root(rx.el.div("hello"), window_library_imports)

        assert 'from "@radix-ui/themes"' in code
        assert '"@radix-ui/themes":' in code
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


class TestGetRadixThemesStylesheets:
    """Tests for the granular Radix Themes stylesheet selection."""

    def test_no_roots_falls_back_to_monolith(self):
        """When no roots are provided, use the monolithic stylesheet."""
        assert compiler.get_radix_themes_stylesheets(None) == [
            "@radix-ui/themes/styles.css"
        ]

    def test_literal_accent_emits_granular_imports(self):
        """A literal accent_color emits only the needed granular imports."""
        import reflex as rx

        sheets = compiler.get_radix_themes_stylesheets([rx.theme(accent_color="blue")])
        assert sheets == [
            "@radix-ui/themes/tokens/base.css",
            # blue's natural gray pairing is slate
            "@radix-ui/themes/tokens/colors/slate.css",
            "@radix-ui/themes/tokens/colors/blue.css",
            "@radix-ui/themes/components.css",
            "@radix-ui/themes/utilities.css",
        ]

    def test_explicit_gray_overrides_auto_pairing(self):
        """An explicit gray_color replaces the accent's auto-paired gray."""
        import reflex as rx

        sheets = compiler.get_radix_themes_stylesheets([
            rx.theme(accent_color="red", gray_color="mauve")
        ])
        assert "@radix-ui/themes/tokens/colors/mauve.css" in sheets
        assert "@radix-ui/themes/tokens/colors/red.css" in sheets
        # The default auto pairing for red is also mauve, so no extra colors.
        color_sheets = [s for s in sheets if "/colors/" in s]
        assert len(color_sheets) == 2

    def test_nested_themes_union_colors(self):
        """Nested Theme components contribute the union of their colors."""
        import reflex as rx

        root = rx.box(
            rx.theme(accent_color="green"),
            rx.theme(accent_color="pink"),
        )
        sheets = compiler.get_radix_themes_stylesheets([root])
        color_sheets = {s for s in sheets if "/colors/" in s}
        assert "@radix-ui/themes/tokens/colors/green.css" in color_sheets
        assert "@radix-ui/themes/tokens/colors/pink.css" in color_sheets

    def test_dynamic_color_falls_back_to_monolith(self):
        """A state-driven Theme color forces the monolithic stylesheet."""
        from typing import Literal

        import reflex as rx

        class _S(rx.State):
            color: Literal["red", "blue"] = "red"

        sheets = compiler.get_radix_themes_stylesheets([
            rx.theme(accent_color=_S.color)
        ])
        assert sheets == ["@radix-ui/themes/styles.css"]


class TestCollectWindowLibraryImports:
    """Tests for the import collection that drives window.__reflex."""

    @pytest.fixture(autouse=True)
    def _isolate_dynamic_imports(self):
        from reflex_base.components.dynamic import reset_dynamic_component_imports

        reset_dynamic_component_imports()
        # Radix Themes is opt-in (RadixThemesPlugin); bundle it explicitly so
        # tests that exercise Radix tag collection have it in scope.
        reset_bundled_libraries()
        bundle_library("@radix-ui/themes@3.3.0")
        yield
        reset_dynamic_component_imports()
        reset_bundled_libraries()

    def test_internal_modules_always_star_imported(self):
        """Internal Reflex modules map to None (star import) so dynamic
        components / plugins reading window.__reflex find what they need
        even when the app has no static external references.
        """
        result = compiler.collect_window_library_imports([{}])
        assert result["$/utils/state"] is None
        assert "@radix-ui/themes" not in result

    def test_external_lib_uses_named_imports_from_static_usage(self):
        """External library exposure on window.__reflex uses named imports
        so Rolldown can tree-shake unused exports.
        """
        from reflex_base.utils.imports import ImportVar

        sources = [
            {"$/utils/state": [ImportVar(tag="evalReactComponent")]},
            {
                "@radix-ui/themes@3.3.0": [
                    ImportVar(tag="Theme"),
                    ImportVar(tag="Button"),
                ]
            },
        ]
        result = compiler.collect_window_library_imports(sources)
        assert result["@radix-ui/themes"] == {"Theme", "Button"}

    def test_unions_dynamic_component_tags(self):
        """Tags captured during dynamic-Component serialization are unioned
        into the named-import surface so runtime-eval'd code finds them on
        window.__reflex.
        """
        from reflex_base.components.dynamic import dynamic_component_imports
        from reflex_base.utils.imports import ImportVar

        sources = [{"@radix-ui/themes@3.3.0": [ImportVar(tag="Theme")]}]
        dynamic_component_imports["@radix-ui/themes@3.3.0"] = {ImportVar(tag="Flex")}

        result = compiler.collect_window_library_imports(sources)
        assert result["@radix-ui/themes"] == {"Theme", "Flex"}


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


class TestViteConfigChunking:
    """Tests for Vite config chunk splitting strategy."""

    def _generate_vite_config(self) -> str:
        return vite_config_template(
            base="/",
            hmr=True,
            force_full_reload=False,
            experimental_hmr=False,
            sourcemap=False,
        )

    def test_no_monolithic_radix_ui_chunk(self):
        """Radix-ui packages must not be grouped into a single monolithic chunk.

        A single 'radix-ui' chunk forces every page to download ALL radix code
        even when it only uses a fraction, wasting 55+ KB on typical pages.
        """
        config = self._generate_vite_config()

        # There should be no chunk rule that matches ALL @radix-ui/* packages
        # under a single name like "radix-ui".
        monolithic_radix = re.search(r"""name:\s*["']radix-ui["']""", config)
        assert monolithic_radix is None, (
            "Vite config must not group all @radix-ui/* packages into a single "
            "'radix-ui' chunk. This forces pages to download unused radix code. "
            "Remove the monolithic radix-ui chunk rule and let Vite split per-route."
        )

    def test_vendor_chunks_exist_for_large_libraries(self):
        """Key vendor libraries should still have dedicated chunks for caching."""
        config = self._generate_vite_config()

        # These libraries are large and benefit from dedicated chunks for
        # cross-page cache reuse.
        for lib_name in ["socket-io", "mantine", "recharts"]:
            assert re.search(rf"""name:\s*["']{lib_name}["']""", config), (
                f"Expected dedicated chunk for '{lib_name}'"
            )

    def test_reflex_env_chunk_exists(self):
        """The env.json chunk should always exist for config isolation."""
        config = self._generate_vite_config()
        assert re.search(r"""name:\s*["']reflex-env["']""", config)
