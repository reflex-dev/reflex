import typing
from typing import Any, List, Union

import pytest

from pynecone.utils import build, format, imports, prerequisites, types
from pynecone.var import Var


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
    assert format.to_snake_case(input) == output


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
    assert format.to_camel_case(input) == output


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
    assert format.to_title_case(input) == output


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
    assert format.get_close_char(input) == output


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
    assert format.is_wrapped(text, open) == expected


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
    assert format.wrap(text, open, check_first=check_first, num=num) == expected


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
def test_indent(text: str, indent_level: int, expected: str, windows_platform: bool):
    """Test indenting a string.

    Args:
        text: The text to indent.
        indent_level: The number of spaces to indent by.
        expected: The expected output string.
        windows_platform: Whether the system is windows.
    """
    assert format.indent(text, indent_level) == (
        expected.replace("\n", "\r\n") if windows_platform else expected
    )


@pytest.mark.parametrize(
    "condition,true_value,false_value,expected",
    [
        ("cond", "<C1>", '""', '{isTrue(cond) ? <C1> : ""}'),
        ("cond", "<C1>", "<C2>", "{isTrue(cond) ? <C1> : <C2>}"),
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
    assert format.format_cond(condition, true_value, false_value) == expected


def test_merge_imports():
    """Test that imports are merged correctly."""
    d1 = {"react": {"Component"}}
    d2 = {"react": {"Component"}, "react-dom": {"render"}}
    d = imports.merge_imports(d1, d2)
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
        (List, True),
        (List[int], True),
    ],
)
def test_is_generic_alias(cls: type, expected: bool):
    """Test checking if a class is a GenericAlias.

    Args:
        cls: The class to check.
        expected: Whether the class is a GenericAlias.
    """
    assert types.is_generic_alias(cls) == expected


@pytest.mark.parametrize(
    "route,expected",
    [
        ("", "index"),
        ("/", "index"),
        ("custom-route", "custom-route"),
        ("custom-route/", "custom-route"),
        ("/custom-route", "custom-route"),
    ],
)
def test_format_route(route: str, expected: bool):
    """Test formatting a route.

    Args:
        route: The route to format.
        expected: The expected formatted route.
    """
    assert format.format_route(route) == expected


def test_setup_frontend(tmp_path, mocker):
    """Test checking if assets content have been
    copied into the .web/public folder.

    Args:
        tmp_path: root path of test case data directory
        mocker: mocker object to allow mocking
    """
    web_folder = tmp_path / ".web"
    web_public_folder = web_folder / "public"
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "favicon.ico").touch()

    assert str(web_folder) == prerequisites.create_web_directory(tmp_path)

    mocker.patch("pynecone.utils.prerequisites.install_frontend_packages")

    build.setup_frontend(tmp_path)
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
    assert types.is_backend_variable(input) == output


@pytest.mark.parametrize(
    "cls, cls_check, expected",
    [
        (int, int, True),
        (int, float, False),
        (int, Union[int, float], True),
        (float, Union[int, float], True),
        (str, Union[int, float], False),
        (List[int], List[int], True),
        (List[int], List[float], True),
        (Union[int, float], Union[int, float], False),
        (Union[int, Var[int]], Var[int], False),
        (int, Any, True),
        (Any, Any, True),
        (Union[int, float], Any, True),
    ],
)
def test_issubclass(cls: type, cls_check: type, expected: bool):
    assert types._issubclass(cls, cls_check) == expected


def test_format_sub_state_event(upload_sub_state_event_spec):
    """Test formatting an upload event spec of substate.

    Args:
        upload_sub_state_event_spec: The event spec fixture.
    """
    assert (
        format.format_upload_event(upload_sub_state_event_spec)
        == "uploadFiles(base_state, result, setResult, base_state.files, "
        '"base_state.sub_upload_state.handle_upload",UPLOAD)'
    )


def test_format_upload_event(upload_event_spec):
    """Test formatting an upload event spec.

    Args:
        upload_event_spec: The event spec fixture.
    """
    assert (
        format.format_upload_event(upload_event_spec)
        == "uploadFiles(upload_state, result, setResult, "
        'upload_state.files, "upload_state.handle_upload1",'
        "UPLOAD)"
    )


@pytest.mark.parametrize(
    "app_name,expected_config_name",
    [
        ("appname", "AppnameConfig"),
        ("app_name", "AppnameConfig"),
        ("app-name", "AppnameConfig"),
        ("appname2.io", "AppnameioConfig"),
    ],
)
def test_create_config(app_name, expected_config_name, mocker):
    """Test templates.PCCONFIG is formatted with correct app name and config class name.

    Args:
        app_name: App name.
        expected_config_name: Expected config name.
        mocker: Mocker object.
    """
    mocker.patch("builtins.open")
    tmpl_mock = mocker.patch("pynecone.compiler.templates.PCCONFIG")
    prerequisites.create_config(app_name)
    tmpl_mock.render.assert_called_with(
        app_name=app_name, config_name=expected_config_name
    )


@pytest.mark.parametrize(
    "name,expected",
    [
        ("input1", "ref_input1"),
        ("input 1", "ref_input_1"),
        ("input-1", "ref_input_1"),
        ("input_1", "ref_input_1"),
        ("a long test?1! name", "ref_a_long_test_1_name"),
    ],
)
def test_format_ref(name, expected):
    """Test formatting a ref.

    Args:
        name: The name to format.
        expected: The expected formatted name.
    """
    assert format.format_ref(name) == expected


class DataFrame:
    """A Fake pandas DataFrame class."""

    pass


@pytest.mark.parametrize(
    "class_type,expected",
    [
        (list, False),
        (int, False),
        (dict, False),
        (DataFrame, True),
        (typing.Any, False),
        (typing.List, False),
    ],
)
def test_is_dataframe(class_type, expected):
    """Test that a type name is DataFrame.

    Args:
        class_type: the class type.
        expected: whether type name is DataFrame
    """
    assert types.is_dataframe(class_type) == expected
