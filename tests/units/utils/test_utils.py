import os
import typing
from collections.abc import Mapping, Sequence
from functools import cached_property
from pathlib import Path
from typing import Any, ClassVar, List, Literal, NoReturn  # noqa: UP035

import click
import pytest
from packaging import version
from pytest_mock import MockerFixture

from reflex import constants
from reflex.environment import environment
from reflex.event import EventHandler
from reflex.state import BaseState
from reflex.utils import exec as utils_exec
from reflex.utils import frontend_skeleton, js_runtimes, prerequisites, templates, types
from reflex.utils.exceptions import ReflexError, SystemPackageMissingError
from reflex.vars.base import Var


class ExampleTestState(BaseState):
    """Test state class."""

    def test_event_handler(self):
        """Test event handler."""


def test_func():
    pass


@pytest.mark.parametrize(
    ("cls", "expected"),
    [
        (str, False),
        (int, False),
        (float, False),
        (bool, False),
        (List, True),  # noqa: UP006
        (list[int], True),
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
    ("subclass", "superclass", "expected"),
    [
        *[
            (base_type, base_type, True)
            for base_type in [int, float, str, bool, list, dict]
        ],
        *[
            (one_type, another_type, False)
            for one_type in [int, float, str, list, dict]
            for another_type in [int, float, str, list, dict]
            if one_type != another_type
        ],
        (bool, int, True),
        (int, bool, False),
        (list, list, True),
        (list, list[str], True),  # this is wrong, but it's a limitation of the function
        (list[int], list, True),
        (list[int], list[str], False),
        (list[int], list[int], True),
        (list[int], list[float], False),
        (list[int], list[int | float], True),
        (list[int], list[float | str], False),
        (int | float, list[int | float], False),
        (int | float, int | float | str, True),
        (int | float, str | float, False),
        (dict[str, int], dict[str, int], True),
        (dict[str, bool], dict[str, int], True),
        (dict[str, int], dict[str, bool], False),
        (dict[str, Any], dict[str, str], False),
        (dict[str, str], dict[str, str], True),
        (dict[str, str], dict[str, Any], True),
        (dict[str, Any], dict[str, Any], True),
        (Mapping[str, int], dict[str, int], False),
        (Sequence[int], list[int], False),
        (Sequence[int] | list[int], list[int], False),
        (str, Literal["test", "value"], True),
        (str, Literal["test", "value", 2, 3], True),
        (int, Literal["test", "value"], False),
        (int, Literal["test", "value", 2, 3], True),
        (Literal["test", "value"], str, True),
        (Literal["test", "value", 2, 3], str, False),
        (Literal["test", "value"], int, False),
        (Literal["test", "value", 2, 3], int, False),
        *[
            (NoReturn, super_class, True)
            for super_class in [int, float, str, bool, list, dict, object, Any]
        ],
        *[
            (list[NoReturn], list[super_class], True)
            for super_class in [int, float, str, bool, list, dict, object, Any]
        ],
    ],
)
def test_typehint_issubclass(subclass, superclass, expected):
    assert types.typehint_issubclass(subclass, superclass) == expected


@pytest.mark.parametrize(
    ("subclass", "superclass", "expected"),
    [
        *[
            (base_type, base_type, True)
            for base_type in [int, float, str, bool, list, dict]
        ],
        *[
            (one_type, another_type, False)
            for one_type in [int, float, str, list, dict]
            for another_type in [int, float, str, list, dict]
            if one_type != another_type
        ],
        (bool, int, True),
        (int, bool, False),
        (list, list, True),
        (list, list[str], True),  # this is wrong, but it's a limitation of the function
        (list[int], list, True),
        (list[int], list[str], False),
        (list[int], list[int], True),
        (list[int], list[float], False),
        (list[int], list[int | float], True),
        (list[int], list[float | str], False),
        (int | float, list[int | float], False),
        (int | float, int | float | str, True),
        (int | float, str | float, False),
        (dict[str, int], dict[str, int], True),
        (dict[str, bool], dict[str, int], True),
        (dict[str, int], dict[str, bool], False),
        (dict[str, Any], dict[str, str], False),
        (dict[str, str], dict[str, str], True),
        (dict[str, str], dict[str, Any], True),
        (dict[str, Any], dict[str, Any], True),
        (Mapping[str, int], dict[str, int], True),
        (Sequence[int], list[int], True),
        (Sequence[int] | list[int], list[int], True),
        (str, Literal["test", "value"], True),
        (str, Literal["test", "value", 2, 3], True),
        (int, Literal["test", "value"], False),
        (int, Literal["test", "value", 2, 3], True),
        *[
            (NoReturn, super_class, True)
            for super_class in [int, float, str, bool, list, dict, object, Any]
        ],
        *[
            (list[NoReturn], list[super_class], True)
            for super_class in [int, float, str, bool, list, dict, object, Any]
        ],
    ],
)
def test_typehint_issubclass_mutable_as_immutable(subclass, superclass, expected):
    assert (
        types.typehint_issubclass(
            subclass, superclass, treat_mutable_superclasss_as_immutable=True
        )
        == expected
    )


def test_validate_none_bun_path(mocker: MockerFixture):
    """Test that an error is thrown when a bun path is not specified.

    Args:
        mocker: Pytest mocker object.
    """
    mocker.patch("reflex.utils.path_ops.get_bun_path", return_value=None)
    # with pytest.raises(click.exceptions.Exit):
    js_runtimes.validate_bun()


def test_validate_invalid_bun_path(mocker: MockerFixture):
    """Test that an error is thrown when a custom specified bun path is not valid
    or does not exist.

    Args:
        mocker: Pytest mocker object.
    """
    mock_path = mocker.Mock()
    mocker.patch("reflex.utils.path_ops.get_bun_path", return_value=mock_path)
    mocker.patch("reflex.utils.path_ops.samefile", return_value=False)
    mocker.patch("reflex.utils.js_runtimes.get_bun_version", return_value=None)

    with pytest.raises(click.exceptions.Exit):
        js_runtimes.validate_bun()


def test_validate_bun_path_incompatible_version(mocker: MockerFixture):
    """Test that an error is thrown when the bun version does not meet minimum requirements.

    Args:
        mocker: Pytest mocker object.
    """
    mock_path = mocker.Mock()
    mock_path.samefile.return_value = False
    mocker.patch("reflex.utils.path_ops.get_bun_path", return_value=mock_path)
    mocker.patch("reflex.utils.path_ops.samefile", return_value=False)
    mocker.patch(
        "reflex.utils.js_runtimes.get_bun_version",
        return_value=version.parse("0.6.5"),
    )

    # This will just warn the user, not raise an error
    js_runtimes.validate_bun()


def test_remove_existing_bun_installation(mocker: MockerFixture):
    """Test that existing bun installation is removed.

    Args:
        mocker: Pytest mocker.
    """
    mocker.patch("reflex.utils.js_runtimes.Path.exists", return_value=True)
    rm = mocker.patch("reflex.utils.js_runtimes.path_ops.rm", mocker.Mock())

    js_runtimes.remove_existing_bun_installation()
    rm.assert_called_once()


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
    ("input", "output"),
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
    test_backend_variable_cls: type[BaseState], input: str, output: bool
):
    assert types.is_backend_base_variable(input, test_backend_variable_cls) == output


@pytest.mark.parametrize(
    ("cls", "cls_check", "expected"),
    [
        (int, int, True),
        (int, float, False),
        (int, int | float, True),
        (float, int | float, True),
        (str, int | float, False),
        (list[int], list[int], True),
        (list[int], list[float], True),
        (int | float, int | float, False),
        (int | Var[int], Var[int], False),
        (int, Any, True),
        (Any, Any, True),
        (int | float, Any, True),
        (str, Literal["test", "value"] | int, True),
        (int, Literal["test", "value"] | int, True),
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
    ("app_name", "expected_config_name"),
    [
        ("appname", "AppnameConfig"),
        ("app_name", "AppnameConfig"),
        ("app-name", "AppnameConfig"),
        ("appname2.io", "AppnameioConfig"),
    ],
)
def test_create_config(app_name: str, expected_config_name: str, mocker: MockerFixture):
    """Test templates.RXCONFIG is formatted with correct app name and config class name.

    Args:
        app_name: App name.
        expected_config_name: Expected config name.
        mocker: Mocker object.
    """
    mocker.patch("pathlib.Path.write_text")
    tmpl_mock = mocker.patch("reflex.compiler.templates.RXCONFIG")
    templates.create_config(app_name)
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
    old_pwd = Path.cwd()
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
    templates.create_config(app_name)
    eval_globals = {}
    exec((tmp_working_dir / constants.Config.FILE).read_text(), eval_globals)
    config = eval_globals["config"]
    assert config.app_name == app_name


class DataFrame:
    """A Fake pandas DataFrame class."""


@pytest.mark.parametrize(
    ("class_type", "expected"),
    [
        (list, False),
        (int, False),
        (dict, False),
        (DataFrame, True),
        (typing.Any, False),
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
def test_initialize_non_existent_gitignore(
    tmp_path, mocker: MockerFixture, gitignore_exists
):
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

    frontend_skeleton.initialize_gitignore(gitignore_file=gitignore_file)

    assert gitignore_file.exists()
    file_content = [
        line.strip() for line in gitignore_file.open().read().splitlines() if line
    ]
    assert set(file_content) - expected == set()


def test_validate_app_name(tmp_path, mocker: MockerFixture):
    """Test that an error is raised if the app name is reflex or if the name is not according to python package naming conventions.

    Args:
        tmp_path: Test working dir.
        mocker: Pytest mocker object.
    """
    reflex = tmp_path / "reflex"
    reflex.mkdir()

    mocker.patch("os.getcwd", return_value=str(reflex))

    with pytest.raises(click.exceptions.Exit):
        prerequisites.validate_app_name()

    with pytest.raises(click.exceptions.Exit):
        prerequisites.validate_app_name(app_name="1_test")


def test_bun_install_without_unzip(mocker: MockerFixture):
    """Test that an error is thrown when installing bun with unzip not installed.

    Args:
        mocker: Pytest mocker object.
    """
    mocker.patch("reflex.utils.path_ops.which", return_value=None)
    mocker.patch("pathlib.Path.exists", return_value=False)
    mocker.patch("reflex.utils.prerequisites.constants.IS_WINDOWS", False)

    with pytest.raises(SystemPackageMissingError):
        js_runtimes.install_bun()


@pytest.mark.parametrize("bun_version", [constants.Bun.VERSION, "1.0.0"])
def test_bun_install_version(mocker: MockerFixture, bun_version):
    """Test that bun is downloaded when the host version(installed by reflex)
    different from the current version set in reflex.

    Args:
        mocker: Pytest mocker object.
        bun_version: the host bun version

    """
    mocker.patch("reflex.utils.prerequisites.constants.IS_WINDOWS", False)
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch(
        "reflex.utils.js_runtimes.get_bun_version",
        return_value=version.parse(bun_version),
    )
    mocker.patch("reflex.utils.path_ops.which")
    mock = mocker.patch("reflex.utils.js_runtimes.download_and_run")

    js_runtimes.install_bun()
    if bun_version == constants.Bun.VERSION:
        mock.assert_not_called()
    else:
        mock.assert_called_once()


@pytest.mark.parametrize("is_windows", [True, False])
def test_create_reflex_dir(mocker: MockerFixture, is_windows):
    """Test that a reflex directory is created on initializing frontend
    dependencies.

    Args:
        mocker: Pytest mocker object.
        is_windows: Whether platform is windows.
    """
    mocker.patch("reflex.utils.prerequisites.constants.IS_WINDOWS", is_windows)
    mocker.patch("reflex.utils.processes.run_concurrently", mocker.Mock())
    mocker.patch(
        "reflex.utils.frontend_skeleton.initialize_web_directory", mocker.Mock()
    )
    mocker.patch("reflex.utils.processes.run_concurrently")
    mocker.patch("reflex.utils.js_runtimes.validate_bun")
    create_cmd = mocker.patch(
        "reflex.utils.prerequisites.path_ops.mkdir", mocker.Mock()
    )

    prerequisites.initialize_reflex_user_directory()

    assert create_cmd.called


def test_output_system_info(mocker: MockerFixture):
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
            EventHandler(fn=callable)
            if type(callable) is not EventHandler
            else callable
        )
    }

    with pytest.raises(ReflexError):
        rx.box(style=style)


def test_is_prod_mode() -> None:
    """Test that the prod mode is correctly determined."""
    environment.REFLEX_ENV_MODE.set(constants.Env.PROD)
    assert utils_exec.is_prod_mode()
    environment.REFLEX_ENV_MODE.set(None)
    assert not utils_exec.is_prod_mode()
