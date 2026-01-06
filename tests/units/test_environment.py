"""Tests for the environment module."""

import enum
import os
import tempfile
from pathlib import Path
from typing import Annotated
from unittest.mock import patch

import pytest

from reflex import constants
from reflex.environment import (
    EnvironmentVariables,
    EnvVar,
    ExecutorType,
    ExistingPath,
    PerformanceMode,
    SequenceOptions,
    _load_dotenv_from_files,
    _paths_from_env_files,
    _paths_from_environment,
    env_var,
    environment,
    get_default_value_for_field,
    get_type_hints_environment,
    interpret_boolean_env,
    interpret_enum_env,
    interpret_env_var_value,
    interpret_existing_path_env,
    interpret_int_env,
    interpret_path_env,
    interpret_plugin_env,
)
from reflex.plugins import Plugin
from reflex.utils.exceptions import EnvironmentVarValueError


class TestPlugin(Plugin):
    """Test plugin for testing purposes."""


class _TestEnum(enum.Enum):
    """Test enum for testing purposes."""

    VALUE1 = "value1"
    VALUE2 = "value2"


class TestInterpretFunctions:
    """Test the interpret functions."""

    def test_interpret_boolean_env_true_values(self):
        """Test boolean interpretation with true values."""
        true_values = ["true", "1", "yes", "y", "TRUE", "True", "YES", "Y"]
        for value in true_values:
            assert interpret_boolean_env(value, "TEST_FIELD") is True

    def test_interpret_boolean_env_false_values(self):
        """Test boolean interpretation with false values."""
        false_values = ["false", "0", "no", "n", "FALSE", "False", "NO", "N"]
        for value in false_values:
            assert interpret_boolean_env(value, "TEST_FIELD") is False

    def test_interpret_boolean_env_invalid_value(self):
        """Test boolean interpretation with invalid values."""
        with pytest.raises(EnvironmentVarValueError, match="Invalid boolean value"):
            interpret_boolean_env("invalid", "TEST_FIELD")

    def test_interpret_int_env_valid(self):
        """Test integer interpretation with valid values."""
        assert interpret_int_env("42", "TEST_FIELD") == 42
        assert interpret_int_env("-10", "TEST_FIELD") == -10
        assert interpret_int_env("0", "TEST_FIELD") == 0

    def test_interpret_int_env_invalid(self):
        """Test integer interpretation with invalid values."""
        with pytest.raises(EnvironmentVarValueError, match="Invalid integer value"):
            interpret_int_env("not_a_number", "TEST_FIELD")

    def test_interpret_path_env(self):
        """Test path interpretation."""
        result = interpret_path_env("/some/path", "TEST_FIELD")
        assert isinstance(result, Path)
        assert str(result) == str(Path("/some/path"))

    def test_interpret_existing_path_env_valid(self):
        """Test existing path interpretation with valid path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = interpret_existing_path_env(temp_dir, "TEST_FIELD")
            assert isinstance(result, Path)
            assert result.exists()

    def test_interpret_existing_path_env_invalid(self):
        """Test existing path interpretation with non-existent path."""
        with pytest.raises(EnvironmentVarValueError, match="Path does not exist"):
            interpret_existing_path_env("/non/existent/path", "TEST_FIELD")

    def test_interpret_plugin_env_valid(self):
        """Test plugin interpretation with valid plugin."""
        result = interpret_plugin_env(
            "tests.units.test_environment.TestPlugin", "TEST_FIELD"
        )
        assert isinstance(result, TestPlugin)

    def test_interpret_plugin_env_invalid_format(self):
        """Test plugin interpretation with invalid format."""
        with pytest.raises(EnvironmentVarValueError, match="Invalid plugin value"):
            interpret_plugin_env("invalid_format", "TEST_FIELD")

    def test_interpret_plugin_env_import_error(self):
        """Test plugin interpretation with import error."""
        with pytest.raises(EnvironmentVarValueError, match="Failed to import module"):
            interpret_plugin_env("non.existent.module.Plugin", "TEST_FIELD")

    def test_interpret_plugin_env_missing_class(self):
        """Test plugin interpretation with missing class."""
        with pytest.raises(EnvironmentVarValueError, match="Invalid plugin class"):
            interpret_plugin_env(
                "tests.units.test_environment.NonExistentPlugin", "TEST_FIELD"
            )

    def test_interpret_plugin_env_invalid_class(self):
        """Test plugin interpretation with invalid class."""
        with pytest.raises(EnvironmentVarValueError, match="Invalid plugin class"):
            interpret_plugin_env("tests.units.test_environment.TestEnum", "TEST_FIELD")

    def test_interpret_enum_env_valid(self):
        """Test enum interpretation with valid values."""
        result = interpret_enum_env("value1", _TestEnum, "TEST_FIELD")
        assert result == _TestEnum.VALUE1

    def test_interpret_enum_env_invalid(self):
        """Test enum interpretation with invalid values."""
        with pytest.raises(EnvironmentVarValueError, match="Invalid enum value"):
            interpret_enum_env("invalid_value", _TestEnum, "TEST_FIELD")


class TestInterpretEnvVarValue:
    """Test the interpret_env_var_value function."""

    def test_interpret_string(self):
        """Test string interpretation."""
        result = interpret_env_var_value("  test  ", str, "TEST_FIELD")
        assert result == "test"

    def test_interpret_boolean(self):
        """Test boolean interpretation."""
        result = interpret_env_var_value("true", bool, "TEST_FIELD")
        assert result is True

    def test_interpret_int(self):
        """Test integer interpretation."""
        result = interpret_env_var_value("42", int, "TEST_FIELD")
        assert result == 42

    def test_interpret_path(self):
        """Test path interpretation."""
        result = interpret_env_var_value("/test/path", Path, "TEST_FIELD")
        assert isinstance(result, Path)

    def test_interpret_existing_path(self):
        """Test existing path interpretation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = interpret_env_var_value(temp_dir, ExistingPath, "TEST_FIELD")
            assert isinstance(result, Path)

    def test_interpret_plugin(self):
        """Test plugin interpretation."""
        result = interpret_env_var_value(
            "tests.units.test_environment.TestPlugin", Plugin, "TEST_FIELD"
        )
        assert isinstance(result, TestPlugin)

    def test_interpret_list(self):
        """Test list interpretation."""
        result = interpret_env_var_value("1:2:3", list[int], "TEST_FIELD")
        assert result == [1, 2, 3]

    def test_interpret_annotated_sequence(self):
        """Test annotated sequence interpretation."""
        annotated_type = Annotated[
            list[str], SequenceOptions(delimiter=",", strip=True)
        ]
        result = interpret_env_var_value("a, b, c ", annotated_type, "TEST_FIELD")
        assert result == ["a", "b", "c"]

    def test_interpret_enum(self):
        """Test enum interpretation."""
        result = interpret_env_var_value("value1", _TestEnum, "TEST_FIELD")
        assert result == _TestEnum.VALUE1

    def test_interpret_union_error(self):
        """Test that union types raise an error."""
        with pytest.raises(ValueError, match="Union types are not supported"):
            interpret_env_var_value("test", int | str, "TEST_FIELD")

    def test_interpret_unsupported_type(self):
        """Test unsupported type raises an error."""
        with pytest.raises(ValueError, match="Invalid type for environment variable"):
            interpret_env_var_value("test", dict, "TEST_FIELD")

    def test_interpret_optional_type(self):
        """Test optional type interpretation."""
        # This should work by extracting the inner type
        result = interpret_env_var_value("42", int | None, "TEST_FIELD")
        assert result == 42


class TestEnvVar:
    """Test the EnvVar class."""

    def test_init(self):
        """Test EnvVar initialization."""
        env_var_instance = EnvVar("TEST_VAR", "default", str)
        assert env_var_instance.name == "TEST_VAR"
        assert env_var_instance.default == "default"
        assert env_var_instance.type_ is str

    def test_interpret(self):
        """Test EnvVar interpret method."""
        env_var_instance = EnvVar("TEST_VAR", 0, int)
        result = env_var_instance.interpret("42")
        assert result == 42

    def test_getenv_set(self, monkeypatch):
        """Test getenv when environment variable is set.

        Args:
            monkeypatch: pytest monkeypatch fixture.
        """
        monkeypatch.setenv("TEST_VAR", "test_value")
        env_var_instance = EnvVar("TEST_VAR", "default", str)
        result = env_var_instance.getenv()
        assert result == "test_value"

    def test_getenv_not_set(self):
        """Test getenv when environment variable is not set."""
        env_var_instance = EnvVar("NONEXISTENT_VAR", "default", str)
        result = env_var_instance.getenv()
        assert result is None

    def test_getenv_empty_string(self, monkeypatch):
        """Test getenv with empty string value.

        Args:
            monkeypatch: pytest monkeypatch fixture.
        """
        monkeypatch.setenv("TEST_VAR", "")
        env_var_instance = EnvVar("TEST_VAR", "default", str)
        result = env_var_instance.getenv()
        assert result is None

    def test_getenv_whitespace_only(self, monkeypatch):
        """Test getenv with whitespace-only value.

        Args:
            monkeypatch: pytest monkeypatch fixture.
        """
        monkeypatch.setenv("TEST_VAR", "   ")
        env_var_instance = EnvVar("TEST_VAR", "default", str)
        result = env_var_instance.getenv()
        assert result is None

    def test_is_set_true(self, monkeypatch):
        """Test is_set when variable is set.

        Args:
            monkeypatch: pytest monkeypatch fixture.
        """
        monkeypatch.setenv("TEST_VAR", "value")
        env_var_instance = EnvVar("TEST_VAR", "default", str)
        assert env_var_instance.is_set() is True

    def test_is_set_false(self):
        """Test is_set when variable is not set."""
        env_var_instance = EnvVar("NONEXISTENT_VAR", "default", str)
        assert env_var_instance.is_set() is False

    def test_is_set_empty_string(self, monkeypatch):
        """Test is_set with empty string.

        Args:
            monkeypatch: pytest monkeypatch fixture.
        """
        monkeypatch.setenv("TEST_VAR", "")
        env_var_instance = EnvVar("TEST_VAR", "default", str)
        assert env_var_instance.is_set() is False

    def test_get_with_env_value(self, monkeypatch):
        """Test get method when environment variable is set.

        Args:
            monkeypatch: pytest monkeypatch fixture.
        """
        monkeypatch.setenv("TEST_VAR", "env_value")
        env_var_instance = EnvVar("TEST_VAR", "default", str)
        result = env_var_instance.get()
        assert result == "env_value"

    def test_get_with_default(self):
        """Test get method when environment variable is not set."""
        env_var_instance = EnvVar("NONEXISTENT_VAR", "default", str)
        result = env_var_instance.get()
        assert result == "default"

    def test_set_string_value(self):
        """Test setting a string value."""
        env_var_instance = EnvVar("TEST_VAR", "default", str)
        env_var_instance.set("new_value")  # type: ignore[arg-type]
        assert os.environ.get("TEST_VAR") == "new_value"
        # Clean up
        del os.environ["TEST_VAR"]

    def test_set_none_value(self, monkeypatch):
        """Test setting None value removes the environment variable.

        Args:
            monkeypatch: pytest monkeypatch fixture.
        """
        monkeypatch.setenv("TEST_VAR", "value")
        env_var_instance = EnvVar("TEST_VAR", "default", str)
        env_var_instance.set(None)
        assert "TEST_VAR" not in os.environ

    def test_set_enum_value(self):
        """Test setting an enum value."""
        env_var_instance = EnvVar("TEST_VAR", _TestEnum.VALUE1, _TestEnum)
        env_var_instance.set(_TestEnum.VALUE2)  # type: ignore[arg-type]
        assert os.environ.get("TEST_VAR") == "value2"
        # Clean up
        del os.environ["TEST_VAR"]

    def test_set_list_value(self):
        """Test setting a list value."""
        env_var_instance = EnvVar("TEST_VAR", [], list[int])
        env_var_instance.set([1, 2, 3])  # type: ignore[arg-type]
        assert os.environ.get("TEST_VAR") == "1:2:3"
        # Clean up
        del os.environ["TEST_VAR"]


class TestEnvVarDescriptor:
    """Test the env_var descriptor."""

    def test_descriptor_get_normal(self):
        """Test getting EnvVar from descriptor."""

        class TestEnv:
            TEST_VAR: EnvVar[str] = env_var("default")

        env_var_instance = TestEnv.TEST_VAR
        assert isinstance(env_var_instance, EnvVar)
        assert env_var_instance.name == "TEST_VAR"
        assert env_var_instance.default == "default"

    def test_descriptor_get_internal(self):
        """Test getting internal EnvVar from descriptor."""

        class TestEnv:
            INTERNAL_VAR: EnvVar[str] = env_var("default", internal=True)

        env_var_instance = TestEnv.INTERNAL_VAR
        assert isinstance(env_var_instance, EnvVar)
        assert env_var_instance.name == "__INTERNAL_VAR"
        assert env_var_instance.default == "default"


class TestExecutorType:
    """Test the ExecutorType enum and related functionality."""

    def test_executor_type_values(self):
        """Test ExecutorType enum values."""
        assert ExecutorType.THREAD.value == "thread"
        assert ExecutorType.PROCESS.value == "process"
        assert ExecutorType.MAIN_THREAD.value == "main_thread"

    def test_get_executor_main_thread_mode(self):
        """Test executor selection in main thread mode."""
        with (
            patch.object(
                environment.REFLEX_COMPILE_EXECUTOR,
                "get",
                return_value=ExecutorType.MAIN_THREAD,
            ),
            patch.object(
                environment.REFLEX_COMPILE_PROCESSES, "get", return_value=None
            ),
            patch.object(environment.REFLEX_COMPILE_THREADS, "get", return_value=None),
        ):
            executor = ExecutorType.get_executor_from_environment()

            # Test the main thread executor functionality
            with executor:
                future = executor.submit(lambda x: x * 2, 5)
                assert future.result() == 10

    def test_get_executor_returns_executor(self):
        """Test that get_executor_from_environment returns an executor."""
        # Test with default values - should return some kind of executor
        executor = ExecutorType.get_executor_from_environment()
        assert executor is not None

        # Test that we can use it as a context manager
        with executor:
            future = executor.submit(lambda: "test")
            assert future.result() == "test"


class TestUtilityFunctions:
    """Test utility functions."""

    def test_get_type_hints_environment(self):
        """Test get_type_hints_environment function."""

        class TestClass:
            var1: str
            var2: int

        hints = get_type_hints_environment(TestClass)
        assert "var1" in hints
        assert "var2" in hints
        assert hints["var1"] is str
        assert hints["var2"] is int

    def test_paths_from_env_files(self):
        """Test _paths_from_env_files function."""
        env_files = "/path/one" + os.pathsep + "/path/two" + os.pathsep + "/path/three"
        result = _paths_from_env_files(env_files)

        # Should be reversed order
        expected = [Path("/path/three"), Path("/path/two"), Path("/path/one")]
        assert result == expected

    def test_paths_from_env_files_with_spaces(self):
        """Test _paths_from_env_files with spaces."""
        env_files = (
            " /path/one " + os.pathsep + " /path/two " + os.pathsep + " /path/three "
        )
        result = _paths_from_env_files(env_files)

        expected = [Path("/path/three"), Path("/path/two"), Path("/path/one")]
        assert result == expected

    def test_paths_from_env_files_empty(self):
        """Test _paths_from_env_files with empty string."""
        result = _paths_from_env_files("")
        assert result == []

    def test_paths_from_environment_set(self, monkeypatch):
        """Test _paths_from_environment when REFLEX_ENV_FILE is set.

        Args:
            monkeypatch: pytest monkeypatch fixture.
        """
        monkeypatch.setenv("REFLEX_ENV_FILE", "/path/one" + os.pathsep + "/path/two")
        result = _paths_from_environment()
        expected = [Path("/path/two"), Path("/path/one")]
        assert result == expected

    def test_paths_from_environment_not_set(self):
        """Test _paths_from_environment when REFLEX_ENV_FILE is not set."""
        # Ensure the env var is not set
        if "REFLEX_ENV_FILE" in os.environ:
            del os.environ["REFLEX_ENV_FILE"]

        result = _paths_from_environment()
        assert result == []

    @patch("reflex.environment.load_dotenv")
    def test_load_dotenv_from_files_with_dotenv(self, mock_load_dotenv):
        """Test _load_dotenv_from_files when dotenv is available.

        Args:
            mock_load_dotenv: Mock for the load_dotenv function.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            file1 = Path(temp_dir) / "file1.env"
            file2 = Path(temp_dir) / "file2.env"
            file1.touch()
            file2.touch()

            _load_dotenv_from_files([file1, file2])

            assert mock_load_dotenv.call_count == 2
            mock_load_dotenv.assert_any_call(file1, override=True)
            mock_load_dotenv.assert_any_call(file2, override=True)

    @patch("reflex.environment.load_dotenv", None)
    @patch("reflex.utils.console")
    def test_load_dotenv_from_files_without_dotenv(self, mock_console):
        """Test _load_dotenv_from_files when dotenv is not available.

        Args:
            mock_console: Mock for the console object.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            file1 = Path(temp_dir) / "file1.env"
            file1.touch()

            _load_dotenv_from_files([file1])
            mock_console.error.assert_called_once()

    def test_load_dotenv_from_files_empty_list(self):
        """Test _load_dotenv_from_files with empty file list."""
        # Should not raise any errors
        _load_dotenv_from_files([])

    @patch("reflex.environment.load_dotenv")
    def test_load_dotenv_from_files_nonexistent_file(self, mock_load_dotenv):
        """Test _load_dotenv_from_files with non-existent file.

        Args:
            mock_load_dotenv: Mock for the load_dotenv function.
        """
        nonexistent_file = Path("/non/existent/file.env")
        _load_dotenv_from_files([nonexistent_file])

        # Should not call load_dotenv for non-existent files
        mock_load_dotenv.assert_not_called()


class TestEnvironmentVariables:
    """Test the EnvironmentVariables class and its instances."""

    def test_environment_instance_exists(self):
        """Test that the environment instance exists and is properly typed."""
        assert isinstance(environment, EnvironmentVariables)

    def test_environment_variables_have_correct_types(self):
        """Test that environment variables have the correct types."""
        # Test a few key environment variables
        assert isinstance(environment.REFLEX_USE_NPM, EnvVar)
        assert isinstance(environment.REFLEX_USE_GRANIAN, EnvVar)
        assert isinstance(environment.REFLEX_WEB_WORKDIR, EnvVar)
        assert isinstance(environment.REFLEX_FRONTEND_PORT, EnvVar)
        assert isinstance(environment.REFLEX_BACKEND_PORT, EnvVar)

    def test_environment_variables_defaults(self):
        """Test that environment variables have the expected defaults."""
        assert environment.REFLEX_USE_NPM.get() is False
        assert environment.REFLEX_USE_GRANIAN.get() is False
        assert environment.REFLEX_USE_SYSTEM_BUN.get() is False
        assert environment.REFLEX_WEB_WORKDIR.get() == Path(constants.Dirs.WEB)
        assert environment.REFLEX_STATES_WORKDIR.get() == Path(constants.Dirs.STATES)

    def test_internal_environment_variables(self):
        """Test internal environment variables have correct names."""
        assert environment.REFLEX_COMPILE_CONTEXT.name == "__REFLEX_COMPILE_CONTEXT"
        assert environment.REFLEX_SKIP_COMPILE.name == "__REFLEX_SKIP_COMPILE"

    def test_performance_mode_enum(self):
        """Test PerformanceMode enum."""
        assert PerformanceMode.WARN.value == "warn"
        assert PerformanceMode.RAISE.value == "raise"
        assert PerformanceMode.OFF.value == "off"

        # Test that the default is WARN
        assert environment.REFLEX_PERF_MODE.get() == PerformanceMode.WARN


class TestGetDefaultValueForField:
    """Test the get_default_value_for_field function."""

    def test_get_default_value_for_field_with_default(self):
        """Test field with default value."""
        import dataclasses

        @dataclasses.dataclass
        class TestClass:
            field: str = "default_value"

        field = dataclasses.fields(TestClass)[0]
        result = get_default_value_for_field(field)
        assert result == "default_value"

    def test_get_default_value_for_field_with_default_factory(self):
        """Test field with default factory."""
        import dataclasses

        @dataclasses.dataclass
        class TestClass:
            field: list = dataclasses.field(default_factory=list)

        field = dataclasses.fields(TestClass)[0]
        result = get_default_value_for_field(field)
        assert result == []

    def test_get_default_value_for_field_without_default(self):
        """Test field without default value or factory."""
        import dataclasses

        @dataclasses.dataclass
        class TestClass:
            field: str

        field = dataclasses.fields(TestClass)[0]
        with pytest.raises(ValueError, match="Missing value for environment variable"):
            get_default_value_for_field(field)


@pytest.fixture(autouse=True)
def cleanup_env_vars():
    """Clean up test environment variables after each test.

    Yields:
        None: Fixture yields control back to the test.
    """
    test_vars = [
        "TEST_VAR",
        "NONEXISTENT_VAR",
        "BLUBB",
        "__INTERNAL",
        "BOOLEAN",
        "LIST",
        "__INTERNAL_VAR",
    ]

    yield

    for var in test_vars:
        if var in os.environ:
            print(var)
            del os.environ[var]
