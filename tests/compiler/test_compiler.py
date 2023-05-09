from typing import List, Set

import pytest

from pynecone.compiler import utils
from pynecone.utils import imports
from pynecone.vars import ImportVar


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


# @pytest.mark.parametrize(
#     "name,value,output",
#     [
#         ("foo", "bar", 'const foo = "bar"'),
#         ("num", 1, "const num = 1"),
#         ("check", False, "const check = false"),
#         ("arr", [1, 2, 3], "const arr = [1, 2, 3]"),
#         ("obj", {"foo": "bar"}, 'const obj = {"foo": "bar"}'),
#     ],
# )
# def test_compile_constant_declaration(name: str, value: str, output: str):
#     """Test the compile_constant_declaration function.

#     Args:
#         name: The name of the constant.
#         value: The value of the constant.
#         output: The expected output.
#     """
#     assert utils.compile_constant_declaration(name, value) == output
