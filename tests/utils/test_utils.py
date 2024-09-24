import os
import typing
from functools import cached_property
from pathlib import Path
from typing import Any, ClassVar, List, Literal, Type, Union

import pytest
import typer
from packaging import version

from reflex import constants
from reflex.base import Base
from reflex.event import EventHandler
from reflex.state import BaseState
from reflex.utils import (
    build,
    prerequisites,
    types,
)
from reflex.utils import exec as utils_exec
from reflex.utils.exceptions import ReflexError
from reflex.vars.base import Var


def mock_event(arg):
    pass


def get_above_max_version():
    """Get the 1 version above the max required bun version.

    Returns:
        max bun version plus one.

    """
    semantic_version_list = constants.Bun.VERSION.split(".")
    semantic_version_list[-1] = str(int(semantic_version_list[-1]) + 1)  # type: ignore
    return ".".join(semantic_version_list)


V055 = version.parse("0.5.5")
V059 = version.parse("0.5.9")
V056 = version.parse("0.5.6")
VMAXPLUS1 = version.parse(get_above_max_version())


class ExampleTestState(BaseState):
    """Test state class."""

    def test_event_handler(self):
        """Test event handler."""
        pass


def test_func():
    pass


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


def test_validate_invalid_bun_path(mocker):
    """Test that an error is thrown when a custom specified bun path is not valid
    or does not exist.

    Args:
        mocker: Pytest mocker object.
    """
    mock = mocker.Mock()
    mocker.patch.object(mock, "bun_path", return_value="/mock/path")
    mocker.patch("reflex.utils.prerequisites.get_config", mock)
    mocker.patch("reflex.utils.prerequisites.get_bun_version", return_value=None)

    with pytest.raises(typer.Exit):
        prerequisites.validate_bun()


def test_validate_bun_path_incompatible_version(mocker):
    """Test that an error is thrown when the bun version does not meet minimum requirements.

    Args:
        mocker: Pytest mocker object.
    """
    mock = mocker.Mock()
    mocker.patch.object(mock, "bun_path", return_value="/mock/path")
    mocker.patch("reflex.utils.prerequisites.get_config", mock)
    mocker.patch(
        "reflex.utils.prerequisites.get_bun_version",
        return_value=version.parse("0.6.5"),
    )

    with pytest.raises(typer.Exit):
        prerequisites.validate_bun()


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
    mocker.patch("reflex.utils.build.set_env_json")

    build.setup_frontend(tmp_path, disable_telemetry=False)
    assert web_public_folder.exists()
    assert (web_public_folder / "favicon.ico").exists()


@pytest.fixture
def test_backend_variable_cls():
    class TestBackendVariable(BaseState):
        """Test backend variable."""

        _classvar: ClassVar[int] = 0
        _hidden: int = 0
        not_hidden: int = 0
        __dunderattr__: int = 0

        @classmethod
        def _class_method(cls):
            pass

        def _hidden_method(self):
            pass

        @property
        def _hidden_property(self):
            pass

        @cached_property
        def _cached_hidden_property(self):
            pass

    return TestBackendVariable


@pytest.mark.parametrize(
    "input, output",
    [
        ("_classvar", False),
        ("_class_method", False),
        ("_hidden_method", False),
        ("_hidden", True),
        ("not_hidden", False),
        ("__dundermethod__", False),
        ("_hidden_property", False),
        ("_cached_hidden_property", False),
    ],
)
def test_is_backend_base_variable(
    test_backend_variable_cls: Type[BaseState], input: str, output: bool
):
    assert types.is_backend_base_variable(input, test_backend_variable_cls) == output


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
        (str, Union[Literal["test", "value"], int], True),
        (int, Union[Literal["test", "value"], int], True),
        (str, Literal["test", "value"], True),
        (int, Literal["test", "value"], False),
    ],
)
def test_issubclass(cls: type, cls_check: type, expected: bool):
    assert types._issubclass(cls, cls_check) == expected


@pytest.mark.parametrize("cls", [Literal["test", 1], Literal[1, "test"]])
def test_unsupported_literals(cls: type):
    with pytest.raises(TypeError):
        types.get_base_class(cls)


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
    exec((tmp_working_dir / constants.Config.FILE).read_text(), eval_globals)
    config = eval_globals["config"]
    assert config.app_name == app_name


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
    expected = constants.GitIgnore.DEFAULTS.copy()
    mocker.patch("reflex.constants.GitIgnore.FILE", tmp_path / ".gitignore")

    gitignore_file = tmp_path / ".gitignore"

    if gitignore_exists:
        gitignore_file.touch()
        gitignore_file.write_text(
            """*.db
        __pycache__/
        """
        )

    prerequisites.initialize_gitignore(gitignore_file=gitignore_file)

    assert gitignore_file.exists()
    file_content = [
        line.strip() for line in gitignore_file.open().read().splitlines() if line
    ]
    assert set(file_content) - expected == set()


def test_validate_app_name(tmp_path, mocker):
    """Test that an error is raised if the app name is reflex or if the name is not according to python package naming conventions.

    Args:
        tmp_path: Test working dir.
        mocker: Pytest mocker object.
    """
    reflex = tmp_path / "reflex"
    reflex.mkdir()

    mocker.patch("reflex.utils.prerequisites.os.getcwd", return_value=str(reflex))

    with pytest.raises(typer.Exit):
        prerequisites.validate_app_name()

    with pytest.raises(typer.Exit):
        prerequisites.validate_app_name(app_name="1_test")


def test_node_install_windows(tmp_path, mocker):
    """Require user to install node manually for windows if node is not installed.

    Args:
        tmp_path: Test working dir.
        mocker: Pytest mocker object.
    """
    fnm_root_path = tmp_path / "reflex" / "fnm"
    fnm_exe = fnm_root_path / "fnm.exe"

    mocker.patch("reflex.utils.prerequisites.constants.Fnm.DIR", fnm_root_path)
    mocker.patch("reflex.utils.prerequisites.constants.Fnm.EXE", fnm_exe)
    mocker.patch("reflex.utils.prerequisites.constants.IS_WINDOWS", True)
    mocker.patch("reflex.utils.processes.new_process")
    mocker.patch("reflex.utils.processes.stream_logs")

    class Resp(Base):
        status_code = 200
        text = "test"

    mocker.patch("httpx.stream", return_value=Resp())
    download = mocker.patch("reflex.utils.prerequisites.download_and_extract_fnm_zip")
    mocker.patch("reflex.utils.prerequisites.zipfile.ZipFile")
    mocker.patch("reflex.utils.prerequisites.path_ops.rm")

    prerequisites.install_node()

    assert fnm_root_path.exists()
    download.assert_called_once()


@pytest.mark.parametrize(
    "machine, system",
    [
        ("x64", "Darwin"),
        ("arm64", "Darwin"),
        ("x64", "Windows"),
        ("arm64", "Windows"),
        ("armv7", "Linux"),
        ("armv8-a", "Linux"),
        ("armv8.1-a", "Linux"),
        ("armv8.2-a", "Linux"),
        ("armv8.3-a", "Linux"),
        ("armv8.4-a", "Linux"),
        ("aarch64", "Linux"),
        ("aarch32", "Linux"),
    ],
)
def test_node_install_unix(tmp_path, mocker, machine, system):
    fnm_root_path = tmp_path / "reflex" / "fnm"
    fnm_exe = fnm_root_path / "fnm"

    mocker.patch("reflex.utils.prerequisites.constants.Fnm.DIR", fnm_root_path)
    mocker.patch("reflex.utils.prerequisites.constants.Fnm.EXE", fnm_exe)
    mocker.patch("reflex.utils.prerequisites.constants.IS_WINDOWS", False)
    mocker.patch("reflex.utils.prerequisites.platform.machine", return_value=machine)
    mocker.patch("reflex.utils.prerequisites.platform.system", return_value=system)

    class Resp(Base):
        status_code = 200
        text = "test"

    mocker.patch("httpx.stream", return_value=Resp())
    download = mocker.patch("reflex.utils.prerequisites.download_and_extract_fnm_zip")
    process = mocker.patch("reflex.utils.processes.new_process")
    chmod = mocker.patch("reflex.utils.prerequisites.os.chmod")
    mocker.patch("reflex.utils.processes.stream_logs")

    prerequisites.install_node()

    assert fnm_root_path.exists()
    download.assert_called_once()
    if system == "Darwin" and machine == "arm64":
        process.assert_called_with(
            [
                fnm_exe,
                "install",
                "--arch=arm64",
                constants.Node.VERSION,
                "--fnm-dir",
                fnm_root_path,
            ]
        )
    else:
        process.assert_called_with(
            [fnm_exe, "install", constants.Node.VERSION, "--fnm-dir", fnm_root_path]
        )
    chmod.assert_called_once()


def test_bun_install_without_unzip(mocker):
    """Test that an error is thrown when installing bun with unzip not installed.

    Args:
        mocker: Pytest mocker object.
    """
    mocker.patch("reflex.utils.path_ops.which", return_value=None)
    mocker.patch("os.path.exists", return_value=False)
    mocker.patch("reflex.utils.prerequisites.constants.IS_WINDOWS", False)

    with pytest.raises(FileNotFoundError):
        prerequisites.install_bun()


@pytest.mark.parametrize("bun_version", [constants.Bun.VERSION, "1.0.0"])
def test_bun_install_version(mocker, bun_version):
    """Test that bun is downloaded when the host version(installed by reflex)
    different from the current version set in reflex.

    Args:
        mocker: Pytest mocker object.
        bun_version: the host bun version

    """
    mocker.patch("reflex.utils.prerequisites.constants.IS_WINDOWS", False)
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch(
        "reflex.utils.prerequisites.get_bun_version",
        return_value=version.parse(bun_version),
    )
    mocker.patch("reflex.utils.path_ops.which")
    mock = mocker.patch("reflex.utils.prerequisites.download_and_run")

    prerequisites.install_bun()
    if bun_version == constants.Bun.VERSION:
        mock.assert_not_called()
    else:
        mock.assert_called_once()


@pytest.mark.parametrize("is_windows", [True, False])
def test_create_reflex_dir(mocker, is_windows):
    """Test that a reflex directory is created on initializing frontend
    dependencies.

    Args:
        mocker: Pytest mocker object.
        is_windows: Whether platform is windows.
    """
    mocker.patch("reflex.utils.prerequisites.constants.IS_WINDOWS", is_windows)
    mocker.patch("reflex.utils.prerequisites.processes.run_concurrently", mocker.Mock())
    mocker.patch("reflex.utils.prerequisites.initialize_web_directory", mocker.Mock())
    mocker.patch("reflex.utils.processes.run_concurrently")
    mocker.patch("reflex.utils.prerequisites.validate_bun")
    create_cmd = mocker.patch(
        "reflex.utils.prerequisites.path_ops.mkdir", mocker.Mock()
    )

    prerequisites.initialize_reflex_user_directory()

    assert create_cmd.called


def test_output_system_info(mocker):
    """Make sure reflex does not crash dumping system info.

    Args:
        mocker: Pytest mocker object.

    This test makes no assertions about the output, other than it executes
    without crashing.
    """
    mocker.patch("reflex.utils.console._LOG_LEVEL", constants.LogLevel.DEBUG)
    utils_exec.output_system_info()


@pytest.mark.parametrize(
    "callable", [ExampleTestState.test_event_handler, test_func, lambda x: x]
)
def test_style_prop_with_event_handler_value(callable):
    """Test that a type error is thrown when a style prop has a
    callable as value.

    Args:
        callable: The callable function or event handler.

    """
    import reflex as rx

    style = {
        "color": (
            EventHandler(fn=callable) if type(callable) != EventHandler else callable
        )
    }

    with pytest.raises(ReflexError):
        rx.box(
            style=style,  # type: ignore
        )
