import importlib.util
import os
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from reflex import constants
from reflex.compiler import compiler, utils
from reflex.components.base import document
from reflex.components.el.elements.metadata import Link
from reflex.constants.compiler import PageNames
from reflex.utils.imports import ImportVar, ParsedImportDict
from reflex.vars.base import Var
from reflex.vars.sequence import LiteralStringVar


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
        "@layer __reflex_base;\n"
        "@import url('./__reflex_style_reset.css');\n"
        "@import url('@radix-ui/themes/styles.css');\n"
        "@import url('https://fonts.googleapis.com/css?family=Sofia&effect=neon|outline|emboss|shadow-multiple');\n"
        "@import url('https://cdn.jsdelivr.net/npm/bootstrap@3.3.7/dist/css/bootstrap.min.css');\n"
        "@import url('https://cdn.jsdelivr.net/npm/bootstrap@3.3.7/dist/css/bootstrap-theme.min.css');\n"
        "@import url('./style.css');",
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
        "@layer __reflex_base;\n"
        "@import url('./__reflex_style_reset.css');\n"
        "@import url('@radix-ui/themes/styles.css');\n"
        "@import url('./style.css');\n"
        f"@import url('./{Path('preprocess') / Path('styles_a.css')!s}');\n"
        f"@import url('./{Path('preprocess') / Path('styles_b.css')!s}');",
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
        "@layer __reflex_base;\n"
        "@import url('./__reflex_style_reset.css');\n"
        "@import url('@radix-ui/themes/styles.css');\n"
        "@import url('./style.css');\n"
        f"@import url('./{Path('preprocess') / Path('styles_a.css')!s}');\n"
        f"@import url('./{Path('preprocess') / Path('styles_b.css')!s}');",
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
        "@layer __reflex_base;\n@import url('./__reflex_style_reset.css');\n@import url('@radix-ui/themes/styles.css');\n@import url('./style.css');",
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
        "@layer __reflex_base;\n@import url('@radix-ui/themes/styles.css');\n@import url('./style.css');",
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


def test_create_document_root():
    """Test that the document root is created correctly."""
    # Test with no components.
    root = utils.create_document_root()
    root.render()
    assert isinstance(root, utils.Html)
    assert isinstance(root.children[0], utils.Head)
    # Default language.
    lang = root.lang  # pyright: ignore [reportAttributeAccessIssue]
    assert isinstance(lang, LiteralStringVar)
    assert lang.equals(Var.create("en"))
    # No children in head.
    assert len(root.children[0].children) == 6
    assert isinstance(root.children[0].children[1], utils.Meta)
    char_set = root.children[0].children[1].char_set  # pyright: ignore [reportAttributeAccessIssue]
    assert isinstance(char_set, LiteralStringVar)
    assert char_set.equals(Var.create("utf-8"))
    assert isinstance(root.children[0].children[2], utils.Meta)
    name = root.children[0].children[2].name  # pyright: ignore [reportAttributeAccessIssue]
    assert isinstance(name, LiteralStringVar)
    assert name.equals(Var.create("viewport"))
    assert isinstance(root.children[0].children[3], document.Meta)
    assert isinstance(root.children[0].children[4], Link)
    assert isinstance(root.children[0].children[5], document.Links)


def test_create_document_root_with_scripts():
    # Test with components.
    comps = [
        utils.Scripts.create(src="foo.js"),
        utils.Scripts.create(src="bar.js"),
    ]
    root = utils.create_document_root(
        head_components=comps,
        html_lang="rx",
        html_custom_attrs={"project": "reflex"},
    )
    assert isinstance(root, utils.Html)
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
        utils.Meta.create(char_set="cp1252"),
    ]
    root = utils.create_document_root(
        head_components=comps,
    )
    assert isinstance(root, utils.Html)
    assert len(root.children[0].children) == 6
    names = [c.tag for c in root.children[0].children]
    assert names == ["script", "meta", "meta", "Meta", "link", "Links"]
    assert str(root.children[0].children[1].char_set) == '"cp1252"'  # pyright: ignore [reportAttributeAccessIssue]


def test_create_document_root_with_meta_viewport():
    # Test with components.
    comps = [
        utils.Meta.create(http_equiv="refresh", content="5"),
        utils.Meta.create(name="viewport", content="foo"),
    ]
    root = utils.create_document_root(
        head_components=comps,
    )
    assert isinstance(root, utils.Html)
    assert len(root.children[0].children) == 7
    names = [c.tag for c in root.children[0].children]
    assert names == ["script", "meta", "meta", "meta", "Meta", "link", "Links"]
    assert str(root.children[0].children[1].http_equiv) == '"refresh"'  # pyright: ignore [reportAttributeAccessIssue]
    assert str(root.children[0].children[2].name) == '"viewport"'  # pyright: ignore [reportAttributeAccessIssue]
    assert str(root.children[0].children[2].content) == '"foo"'  # pyright: ignore [reportAttributeAccessIssue]
    assert str(root.children[0].children[3].char_set) == '"utf-8"'  # pyright: ignore [reportAttributeAccessIssue]
