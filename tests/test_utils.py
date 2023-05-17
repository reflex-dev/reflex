import os
import typing
from pathlib import Path
from typing import Any, List, Union

import pytest
from packaging import version

from pynecone import Env
from pynecone.constants import CONFIG_FILE, DB_URL
from pynecone.utils import build, format, imports, prerequisites, types
from pynecone.vars import Var

V055 = version.parse("0.5.5")
V059 = version.parse("0.5.9")
V056 = version.parse("0.5.6")
V062 = version.parse("0.6.2")


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


@pytest.mark.parametrize(
    "bun_version,is_valid, prompt_input",
    [
        (V055, False, "yes"),
        (V059, True, None),
        (V062, False, "yes"),
    ],
)
def test_bun_validate_and_install(mocker, bun_version, is_valid, prompt_input):
    """Test that the bun version on host system is validated properly. Also test that
    the required bun version is installed should the user opt for it.

    Args:
        mocker: Pytest mocker object.
        bun_version: The bun version.
        is_valid: Whether bun version is valid for running pynecone.
        prompt_input: The input from user on whether to install bun.
    """
    mocker.patch(
        "pynecone.utils.prerequisites.get_bun_version", return_value=bun_version
    )
    mocker.patch("pynecone.utils.prerequisites.console.ask", return_value=prompt_input)

    bun_install = mocker.patch("pynecone.utils.prerequisites.install_bun")
    remove_existing_bun_installation = mocker.patch(
        "pynecone.utils.prerequisites.remove_existing_bun_installation"
    )

    prerequisites.validate_and_install_bun()
    if not is_valid:
        remove_existing_bun_installation.assert_called_once()
    bun_install.assert_called_once()


def test_bun_validation_exception(mocker):
    """Test that an exception is thrown and program exists when user selects no when asked
    whether to install bun or not.

    Args:
        mocker: Pytest mocker.
    """
    mocker.patch("pynecone.utils.prerequisites.get_bun_version", return_value=V056)
    mocker.patch("pynecone.utils.prerequisites.console.ask", return_value="no")

    with pytest.raises(RuntimeError):
        prerequisites.validate_and_install_bun()


def test_remove_existing_bun_installation(mocker, tmp_path):
    """Test that existing bun installation is removed.

    Args:
        mocker: Pytest mocker.
        tmp_path: test path.
    """
    bun_location = tmp_path / ".bun"
    bun_location.mkdir()

    mocker.patch(
        "pynecone.utils.prerequisites.get_package_manager",
        return_value=str(bun_location),
    )
    mocker.patch(
        "pynecone.utils.prerequisites.os.path.expandvars",
        return_value=str(bun_location),
    )

    prerequisites.remove_existing_bun_installation()

    assert not bun_location.exists()


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
    mocker.patch("pynecone.utils.build.set_pynecone_upload_endpoint")

    build.setup_frontend(tmp_path, disable_telemetry=False)
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


@pytest.fixture
def tmp_working_dir(tmp_path):
    """Create a temporary directory and chdir to it.

    After the test executes, chdir back to the original working directory.

    Args:
        tmp_path: pytest tmp_path fixture creates per-test temp dir

    Yields:
        subdirectory of tmp_path which is now the current working directory.
    """
    old_pwd = Path(".").resolve()
    working_dir = tmp_path / "working_dir"
    working_dir.mkdir()
    os.chdir(working_dir)
    yield working_dir
    os.chdir(old_pwd)


def test_create_config_e2e(tmp_working_dir):
    """Create a new config file, exec it, and make assertions about the config.

    Args:
        tmp_working_dir: a new directory that is the current working directory
            for the duration of the test.
    """
    app_name = "e2e"
    prerequisites.create_config(app_name)
    eval_globals = {}
    exec((tmp_working_dir / CONFIG_FILE).read_text(), eval_globals)
    config = eval_globals["config"]
    assert config.app_name == app_name
    assert config.db_url == DB_URL
    assert config.env == Env.DEV


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
