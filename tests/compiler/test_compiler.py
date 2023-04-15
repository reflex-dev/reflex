from typing import List, Set

import pytest

from pynecone.compiler import utils
from pynecone.utils import imports


@pytest.mark.parametrize(
    "lib,fields,output_default,output_rest",
    [
        ("axios", {"axios"}, 'axios', set()),
        ("axios", {"foo", "bar"}, '', {"foo", "bar"}),
        ("axios", {"axios", "foo", "bar"}, 'axios', {"foo", "bar"}),
    ],
)
def test_compile_import_statement(lib: str, fields: Set[str], output_default:str, output_rest: str):
    """Test the compile_import_statement function.

    Args:
        lib: The library name.
        fields: The fields to import.
        output_default: The expected output of default library.
        output_rest: The expected output rest libraries.
    """
    default, rest = utils.compile_import_statement(lib, fields)
    assert default == output_default
    assert rest == output_rest

@pytest.mark.parametrize(
    "import_dict,test_dicts",
    [
        ({}, []),
        ({"axios": {"axios"}}, [{"lib": "axios", "default": "axios", "rest": set()}]),
        ({"axios": {"foo", "bar"}}, [{"lib": "axios", "default": "", "rest": {"foo", "bar"}}]),
        (
            {"axios": {"axios", "foo", "bar"}, "react": {"react"}},
            [
                {"lib": "axios", "default": "axios", "rest": {"foo", "bar"}},
                {"lib": "react", "default": "react", "rest": set()},
            ]
        ),
        (
            {"": {"lib1.js", "lib2.js"}}, 
            [
                {"lib": "lib1.js", "default": "", "rest": set()},
                {"lib": "lib2.js", "default": "", "rest": set()}
            ]
        ),
        (
            {"": {"lib1.js", "lib2.js"}, "axios": {"axios"}},
            [
                {"lib": "lib1.js", "default": "", "rest": set()},
                {"lib": "lib2.js", "default": "", "rest": set()},
                {"lib": "axios", "default": "axios", "rest": set()}
            ]
        ),
    ],
)
def test_compile_imports(
    import_dict: imports.ImportDict, test_dicts: List[dict]
):
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
