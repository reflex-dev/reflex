import os
import typing
from pathlib import Path
from typing import Any, List, Union

import pytest
import typer
from packaging import version

from reflex import Env, constants
from reflex.base import Base
from reflex.utils import build, format, imports, prerequisites, types
from reflex.vars import Var


def get_above_max_version():
    """Get the 1 version above the max required bun version.

    Returns:
        max bun version plus one.

    """
    semantic_version_list = constants.BUN_VERSION.split(".")
    semantic_version_list[-1] = str(int(semantic_version_list[-1]) + 1)  # type: ignore
    return ".".join(semantic_version_list)


V055 = version.parse("0.5.5")
V059 = version.parse("0.5.9")
V056 = version.parse("0.5.6")
VMAXPLUS1 = version.parse(get_above_max_version())


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
        (VMAXPLUS1, False, "yes"),
    ],
)
def test_initialize_bun(mocker, bun_version, is_valid, prompt_input):
    """Test that the bun version on host system is validated properly. Also test that
    the required bun version is installed should the user opt for it.

    Args:
        mocker: Pytest mocker object.
        bun_version: The bun version.
        is_valid: Whether bun version is valid for running reflex.
        prompt_input: The input from user on whether to install bun.
    """
    mocker.patch("reflex.utils.prerequisites.get_bun_version", return_value=bun_version)
    mocker.patch("reflex.utils.prerequisites.IS_WINDOWS", False)

    bun_install = mocker.patch("reflex.utils.prerequisites.install_bun")
    remove_existing_bun_installation = mocker.patch(
        "reflex.utils.prerequisites.remove_existing_bun_installation"
    )

    prerequisites.initialize_bun()
    if not is_valid:
        remove_existing_bun_installation.assert_called_once()
    bun_install.assert_called_once()


def test_remove_existing_bun_installation(mocker):
    """Test that existing bun installation is removed.

    Args:
        mocker: Pytest mocker.
    """
    mocker.patch("reflex.utils.prerequisites.os.path.exists", return_value=True)
    rm = mocker.patch("reflex.utils.prerequisites.path_ops.rm", mocker.Mock())

    prerequisites.remove_existing_bun_installation()
    rm.assert_called_once()


def test_setup_frontend(tmp_path, mocker):
    """Test checking if assets content have been
    copied into the .web/public folder.

    Args:
        tmp_path: root path of test case data directory
        mocker: mocker object to allow mocking
    """
    web_public_folder = tmp_path / ".web" / "public"
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "favicon.ico").touch()

    mocker.patch("reflex.utils.prerequisites.install_frontend_packages")
    mocker.patch("reflex.utils.build.set_environment_variables")

    build.setup_frontend(tmp_path, disable_telemetry=False)
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
    """Test templates.RXCONFIG is formatted with correct app name and config class name.

    Args:
        app_name: App name.
        expected_config_name: Expected config name.
        mocker: Mocker object.
    """
    mocker.patch("builtins.open")
    tmpl_mock = mocker.patch("reflex.compiler.templates.RXCONFIG")
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
    exec((tmp_working_dir / constants.CONFIG_FILE).read_text(), eval_globals)
    config = eval_globals["config"]
    assert config.app_name == app_name
    assert config.db_url == constants.DB_URL
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


@pytest.mark.parametrize("gitignore_exists", [True, False])
def test_initialize_non_existent_gitignore(tmp_path, mocker, gitignore_exists):
    """Test that the generated .gitignore_file file on reflex init contains the correct file
    names with correct formatting.

    Args:
        tmp_path: The root test path.
        mocker: The mock object.
        gitignore_exists: Whether a gitignore file exists in the root dir.
    """
    expected = constants.DEFAULT_GITIGNORE.copy()
    mocker.patch("reflex.constants.GITIGNORE_FILE", tmp_path / ".gitignore")

    gitignore_file = tmp_path / ".gitignore"

    if gitignore_exists:
        gitignore_file.touch()
        gitignore_file.write_text(
            """*.db
        __pycache__/
        """
        )

    prerequisites.initialize_gitignore()

    assert gitignore_file.exists()
    file_content = [
        line.strip() for line in gitignore_file.open().read().splitlines() if line
    ]
    assert set(file_content) - expected == set()


def test_app_default_name(tmp_path, mocker):
    """Test that an error is raised if the app name is reflex.

    Args:
        tmp_path: Test working dir.
        mocker: Pytest mocker object.
    """
    reflex = tmp_path / "reflex"
    reflex.mkdir()

    mocker.patch("reflex.utils.prerequisites.os.getcwd", return_value=str(reflex))

    with pytest.raises(typer.Exit):
        prerequisites.get_default_app_name()


def test_node_install_windows(mocker):
    """Require user to install node manually for windows if node is not installed.

    Args:
        mocker: Pytest mocker object.
    """
    mocker.patch("reflex.utils.prerequisites.IS_WINDOWS", True)
    mocker.patch("reflex.utils.prerequisites.check_node_version", return_value=False)

    with pytest.raises(typer.Exit):
        prerequisites.initialize_node()


def test_node_install_unix(tmp_path, mocker):
    nvm_root_path = tmp_path / ".reflex" / ".nvm"

    mocker.patch("reflex.utils.prerequisites.constants.NVM_DIR", nvm_root_path)
    mocker.patch("reflex.utils.prerequisites.IS_WINDOWS", False)

    class Resp(Base):
        status_code = 200
        text = "test"

    mocker.patch("httpx.get", return_value=Resp())
    download = mocker.patch("reflex.utils.prerequisites.download_and_run")
    mocker.patch("reflex.utils.processes.new_process")
    mocker.patch("reflex.utils.processes.stream_logs")

    prerequisites.install_node()

    assert nvm_root_path.exists()
    download.assert_called()
    download.call_count = 2


def test_bun_install_without_unzip(mocker):
    """Test that an error is thrown when installing bun with unzip not installed.

    Args:
        mocker: Pytest mocker object.
    """
    mocker.patch("reflex.utils.path_ops.which", return_value=None)
    mocker.patch("os.path.exists", return_value=False)
    mocker.patch("reflex.utils.prerequisites.IS_WINDOWS", False)

    with pytest.raises(FileNotFoundError):
        prerequisites.install_bun()


# from
@pytest.mark.parametrize("is_windows", [True, False])
def test_create_reflex_dir(mocker, is_windows):
    """Test that a reflex directory is created on initializing frontend
    dependencies.

    Args:
        mocker: Pytest mocker object.
        is_windows: Whether platform is windows.
    """
    mocker.patch("reflex.utils.prerequisites.IS_WINDOWS", is_windows)
    mocker.patch("reflex.utils.prerequisites.processes.run_concurrently", mocker.Mock())
    mocker.patch("reflex.utils.prerequisites.initialize_web_directory", mocker.Mock())
    create_cmd = mocker.patch(
        "reflex.utils.prerequisites.path_ops.mkdir", mocker.Mock()
    )

    prerequisites.initialize_frontend_dependencies()

    if is_windows:
        assert not create_cmd.called
    else:
        assert create_cmd.called
