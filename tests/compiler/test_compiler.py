import os
from typing import List, Set

import pytest

from reflex.compiler import compiler, utils
from reflex.utils import imports
from reflex.vars import ImportVar


@pytest.mark.parametrize(
    "fields,test_default,test_rest",
    [
        (
            {ImportVar(tag="axios", is_default=True)},
            "axios",
            set(),
        ),
        (
            {ImportVar(tag="foo"), ImportVar(tag="bar")},
            "",
            {"foo", "bar"},
        ),
        (
            {
                ImportVar(tag="axios", is_default=True),
                ImportVar(tag="foo"),
                ImportVar(tag="bar"),
            },
            "axios",
            {"foo", "bar"},
        ),
    ],
)
def test_compile_import_statement(
    fields: Set[ImportVar], test_default: str, test_rest: str
):
    """Test the compile_import_statement function.

    Args:
        fields: The fields to import.
        test_default: The expected output of default library.
        test_rest: The expected output rest libraries.
    """
    default, rest = utils.compile_import_statement(fields)
    assert default == test_default
    assert rest == test_rest


@pytest.mark.parametrize(
    "import_dict,test_dicts",
    [
        ({}, []),
        (
            {"axios": {ImportVar(tag="axios", is_default=True)}},
            [{"lib": "axios", "default": "axios", "rest": set()}],
        ),
        (
            {"axios": {ImportVar(tag="foo"), ImportVar(tag="bar")}},
            [{"lib": "axios", "default": "", "rest": {"foo", "bar"}}],
        ),
        (
            {
                "axios": {
                    ImportVar(tag="axios", is_default=True),
                    ImportVar(tag="foo"),
                    ImportVar(tag="bar"),
                },
                "react": {ImportVar(tag="react", is_default=True)},
            },
            [
                {"lib": "axios", "default": "axios", "rest": {"foo", "bar"}},
                {"lib": "react", "default": "react", "rest": set()},
            ],
        ),
        (
            {"": {ImportVar(tag="lib1.js"), ImportVar(tag="lib2.js")}},
            [
                {"lib": "lib1.js", "default": "", "rest": set()},
                {"lib": "lib2.js", "default": "", "rest": set()},
            ],
        ),
        (
            {
                "": {ImportVar(tag="lib1.js"), ImportVar(tag="lib2.js")},
                "axios": {ImportVar(tag="axios", is_default=True)},
            },
            [
                {"lib": "lib1.js", "default": "", "rest": set()},
                {"lib": "lib2.js", "default": "", "rest": set()},
                {"lib": "axios", "default": "axios", "rest": set()},
            ],
        ),
    ],
)
def test_compile_imports(import_dict: imports.ImportDict, test_dicts: List[dict]):
    """Test the compile_imports function.

    Args:
        import_dict: The import dictionary.
        test_dicts: The expected output.
    """
    imports = utils.compile_imports(import_dict)
    for import_dict, test_dict in zip(imports, test_dicts):
        assert import_dict["lib"] == test_dict["lib"]
        assert import_dict["default"] == test_dict["default"]
        assert import_dict["rest"] == test_dict["rest"]


def test_compile_stylesheets(tmp_path, mocker):
    """Test that stylesheets compile correctly.

    Args:
        tmp_path: The test directory.
        mocker: Pytest mocker object.
    """
    project = tmp_path / "test_project"
    project.mkdir()

    assets_dir = project / "assets"
    assets_dir.mkdir()

    (assets_dir / "styles.css").touch()

    mocker.patch("reflex.compiler.compiler.Path.cwd", return_value=project)

    stylesheets = [
        "https://fonts.googleapis.com/css?family=Sofia&effect=neon|outline|emboss|shadow-multiple",
        "https://cdn.jsdelivr.net/npm/bootstrap@3.3.7/dist/css/bootstrap.min.css",
        "/styles.css",
        "https://cdn.jsdelivr.net/npm/bootstrap@3.3.7/dist/css/bootstrap-theme.min.css",
    ]

    assert compiler.compile_root_stylesheet(stylesheets) == (
        ".web/styles/styles.css",
        f"@import url('./tailwind.css'); {os.linesep}"
        f"@import url('https://fonts.googleapis.com/css?family=Sofia&effect=neon|outline|emboss|shadow-multiple'); {os.linesep}"
        f"@import url('https://cdn.jsdelivr.net/npm/bootstrap@3.3.7/dist/css/bootstrap.min.css'); {os.linesep}"
        f"@import url('../public/styles.css'); {os.linesep}"
        f"@import url('https://cdn.jsdelivr.net/npm/bootstrap@3.3.7/dist/css/bootstrap-theme.min.css'); {os.linesep}",
    )


def test_compile_nonexistent_stylesheet(tmp_path, mocker):
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

    stylesheets = ["/styles.css"]

    with pytest.raises(FileNotFoundError):
        compiler.compile_root_stylesheet(stylesheets)
