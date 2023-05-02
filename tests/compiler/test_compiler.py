from typing import Set

import pytest

from pynecone.compiler import utils
from pynecone.utils import imports
from pynecone.var import ImportVar


@pytest.mark.parametrize(
    "lib,fields,output",
    [
        (
            "axios",
            {ImportVar(tag="axios", is_default=True)},
            'import axios from "axios"',
        ),
        (
            "axios",
            {ImportVar(tag="foo"), ImportVar(tag="bar")},
            'import {bar, foo} from "axios"',
        ),
        (
            "axios",
            {
                ImportVar(tag="axios", is_default=True),
                ImportVar(tag="foo"),
                ImportVar(tag="bar"),
            },
            "import " "axios, " "{bar, " "foo} from " '"axios"',
        ),
    ],
)
def test_compile_import_statement(lib: str, fields: Set[ImportVar], output: str):
    """Test the compile_import_statement function.

    Args:
        lib: The library name.
        fields: The fields to import.
        output: The expected output.
    """
    assert utils.compile_import_statement(lib, fields) == output


@pytest.mark.parametrize(
    "import_dict,output",
    [
        ({}, ""),
        (
            {"axios": {ImportVar(tag="axios", is_default=True)}},
            'import axios from "axios"',
        ),
        (
            {"axios": {ImportVar(tag="foo"), ImportVar(tag="bar")}},
            'import {bar, foo} from "axios"',
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
            'import axios, {bar, foo} from "axios"\nimport react from "react"',
        ),
        (
            {"": {ImportVar(tag="lib1.js"), ImportVar(tag="lib2.js")}},
            'import "lib1.js"\nimport "lib2.js"',
        ),
        (
            {
                "": {ImportVar(tag="lib1.js"), ImportVar(tag="lib2.js")},
                "axios": {ImportVar(tag="axios", is_default=True)},
            },
            'import "lib1.js"\nimport "lib2.js"\nimport axios from "axios"',
        ),
    ],
)
def test_compile_imports(
    import_dict: imports.ImportDict, output: str, windows_platform: bool
):
    """Test the compile_imports function.

    Args:
        import_dict: The import dictionary.
        output: The expected output.
        windows_platform: whether system is windows.
    """
    assert utils.compile_imports(import_dict) == (
        output.replace("\n", "\r\n") if windows_platform else output
    )


@pytest.mark.parametrize(
    "name,value,output",
    [
        ("foo", "bar", 'const foo = "bar"'),
        ("num", 1, "const num = 1"),
        ("check", False, "const check = false"),
        ("arr", [1, 2, 3], "const arr = [1, 2, 3]"),
        ("obj", {"foo": "bar"}, 'const obj = {"foo": "bar"}'),
    ],
)
def test_compile_constant_declaration(name: str, value: str, output: str):
    """Test the compile_constant_declaration function.

    Args:
        name: The name of the constant.
        value: The value of the constant.
        output: The expected output.
    """
    assert utils.compile_constant_declaration(name, value) == output
