import typing

import pytest

from pynecone import utils


@pytest.mark.parametrize(
    "input,output",
    [
        ("", ""),
        ("hello", "hello"),
        ("Hello", "hello"),
        ("camelCase", "camel_case"),
        ("camelTwoHumps", "camel_two_humps"),
        ("_start_with_underscore", "_start_with_underscore"),
        ("__start_with_double_underscore", "__start_with_double_underscore"),
    ],
)
def test_to_snake_case(input: str, output: str):
    """Test converting strings to snake case.

    Args:
        input: The input string.
        output: The expected output string.
    """
    assert utils.to_snake_case(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        ("", ""),
        ("hello", "hello"),
        ("Hello", "Hello"),
        ("snake_case", "snakeCase"),
        ("snake_case_two", "snakeCaseTwo"),
    ],
)
def test_to_camel_case(input: str, output: str):
    """Test converting strings to camel case.

    Args:
        input: The input string.
        output: The expected output string.
    """
    assert utils.to_camel_case(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        ("", ""),
        ("hello", "Hello"),
        ("Hello", "Hello"),
        ("snake_case", "SnakeCase"),
        ("snake_case_two", "SnakeCaseTwo"),
    ],
)
def test_to_title_case(input: str, output: str):
    """Test converting strings to title case.

    Args:
        input: The input string.
        output: The expected output string.
    """
    assert utils.to_title_case(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        ("{", "}"),
        ("(", ")"),
        ("[", "]"),
        ("<", ">"),
        ('"', '"'),
        ("'", "'"),
    ],
)
def test_get_close_char(input: str, output: str):
    """Test getting the close character for a given open character.

    Args:
        input: The open character.
        output: The expected close character.
    """
    assert utils.get_close_char(input) == output


@pytest.mark.parametrize(
    "text,open,expected",
    [
        ("", "{", False),
        ("{wrap}", "{", True),
        ("{wrap", "{", False),
        ("{wrap}", "(", False),
        ("(wrap)", "(", True),
    ],
)
def test_is_wrapped(text: str, open: str, expected: bool):
    """Test checking if a string is wrapped in the given open and close characters.

    Args:
        text: The text to check.
        open: The open character.
        expected: Whether the text is wrapped.
    """
    assert utils.is_wrapped(text, open) == expected


@pytest.mark.parametrize(
    "text,open,check_first,num,expected",
    [
        ("", "{", True, 1, "{}"),
        ("wrap", "{", True, 1, "{wrap}"),
        ("wrap", "(", True, 1, "(wrap)"),
        ("wrap", "(", True, 2, "((wrap))"),
        ("(wrap)", "(", True, 1, "(wrap)"),
        ("{wrap}", "{", True, 2, "{wrap}"),
        ("(wrap)", "{", True, 1, "{(wrap)}"),
        ("(wrap)", "(", False, 1, "((wrap))"),
    ],
)
def test_wrap(text: str, open: str, expected: str, check_first: bool, num: int):
    """Test wrapping a string.

    Args:
        text: The text to wrap.
        open: The open character.
        expected: The expected output string.
        check_first: Whether to check if the text is already wrapped.
        num: The number of times to wrap the text.
    """
    assert utils.wrap(text, open, check_first=check_first, num=num) == expected


@pytest.mark.parametrize(
    "text,indent_level,expected",
    [
        ("", 2, ""),
        ("hello", 2, "hello"),
        ("hello\nworld", 2, "  hello\n  world\n"),
        ("hello\nworld", 4, "    hello\n    world\n"),
        ("  hello\n  world", 2, "    hello\n    world\n"),
    ],
)
def test_indent(text: str, indent_level: int, expected: str):
    """Test indenting a string.

    Args:
        text: The text to indent.
        indent_level: The number of spaces to indent by.
        expected: The expected output string.
    """
    assert utils.indent(text, indent_level) == expected


@pytest.mark.parametrize(
    "condition,true_value,false_value,expected",
    [
        ("cond", "<C1>", '""', '{cond ? <C1> : ""}'),
        ("cond", "<C1>", "<C2>", "{cond ? <C1> : <C2>}"),
    ],
)
def test_format_cond(condition: str, true_value: str, false_value: str, expected: str):
    """Test formatting a cond.

    Args:
        condition: The condition to check.
        true_value: The value to return if the condition is true.
        false_value: The value to return if the condition is false.
        expected: The expected output string.
    """
    assert utils.format_cond(condition, true_value, false_value) == expected


def test_merge_imports():
    """Test that imports are merged correctly."""
    d1 = {"react": {"Component"}}
    d2 = {"react": {"Component"}, "react-dom": {"render"}}
    d = utils.merge_imports(d1, d2)
    assert set(d.keys()) == {"react", "react-dom"}
    assert set(d["react"]) == {"Component"}
    assert set(d["react-dom"]) == {"render"}


@pytest.mark.parametrize(
    "cls,expected",
    [
        (str, False),
        (int, False),
        (float, False),
        (bool, False),
        (typing.List, True),
        (typing.List[int], True),
    ],
)
def test_is_generic_alias(cls: type, expected: bool):
    """Test checking if a class is a GenericAlias.

    Args:
        cls: The class to check.
        expected: Whether the class is a GenericAlias.
    """
    assert utils.is_generic_alias(cls) == expected


def test_setup_frontend(tmp_path, mocker):
    """Test checking if assets content have been
    copied into the .web/public folder

    Args:
        tmp_path: root path of test case data directory
        mocker: mocker object to allow mocking
    """
    web_folder = tmp_path / ".web"
    web_public_folder = web_folder / "public"
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "favicon.ico").touch()

    mocker.patch("pynecone.utils.install_frontend_packages")

    utils.setup_frontend(tmp_path)
    assert web_folder.exists()
    assert web_public_folder.exists()
    assert (web_public_folder / "favicon.ico").exists()


@pytest.mark.parametrize(
    "input, output",
    [
        ("_hidden", True),
        ("not_hidden", False),
        ("__dundermethod__", False),
    ],
)
def test_is_backend_variable(input, output):
    assert utils.is_backend_variable(input) == output
