import multiprocessing
import os
from pathlib import Path
from typing import Any, Dict

import pytest

import reflex as rx
import reflex.config
from reflex.config import (
    EnvVar,
    env_var,
    environment,
    interpret_boolean_env,
    interpret_enum_env,
    interpret_int_env,
)
from reflex.constants import Endpoint, Env


def test_requires_app_name():
    """Test that a config requires an app_name."""
    with pytest.raises(ValueError):
        rx.Config()  # type: ignore


def test_set_app_name(base_config_values):
    """Test that the app name is set to the value passed in.

    Args:
        base_config_values: Config values.
    """
    config = rx.Config(**base_config_values)
    assert config.app_name == base_config_values["app_name"]


@pytest.mark.parametrize(
    "env_var, value",
    [
        ("APP_NAME", "my_test_app"),
        ("FRONTEND_PORT", 3001),
        ("FRONTEND_PATH", "/test"),
        ("BACKEND_PORT", 8001),
        ("API_URL", "https://mybackend.com:8000"),
        ("DEPLOY_URL", "https://myfrontend.com"),
        ("BACKEND_HOST", "127.0.0.1"),
        ("DB_URL", "postgresql://user:pass@localhost:5432/db"),
        ("REDIS_URL", "redis://localhost:6379"),
        ("TIMEOUT", 600),
        ("TELEMETRY_ENABLED", False),
        ("TELEMETRY_ENABLED", True),
    ],
)
def test_update_from_env(
    base_config_values: Dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    env_var: str,
    value: Any,
):
    """Test that environment variables override config values.

    Args:
        base_config_values: Config values.
        monkeypatch: The pytest monkeypatch object.
        env_var: The environment variable name.
        value: The environment variable value.
    """
    monkeypatch.setenv(env_var, str(value))
    assert os.environ.get(env_var) == str(value)
    config = rx.Config(**base_config_values)
    assert getattr(config, env_var.lower()) == value


def test_update_from_env_path(
    base_config_values: Dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """Test that environment variables override config values.

    Args:
        base_config_values: Config values.
        monkeypatch: The pytest monkeypatch object.
        tmp_path: The pytest tmp_path fixture object.
    """
    monkeypatch.setenv("BUN_PATH", "/test")
    assert os.environ.get("BUN_PATH") == "/test"
    with pytest.raises(ValueError):
        rx.Config(**base_config_values)

    monkeypatch.setenv("BUN_PATH", str(tmp_path))
    assert os.environ.get("BUN_PATH") == str(tmp_path)
    config = rx.Config(**base_config_values)
    assert config.bun_path == tmp_path


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        (
            {"app_name": "test_app", "api_url": "http://example.com"},
            f"{Endpoint.EVENT}",
        ),
        (
            {"app_name": "test_app", "api_url": "http://example.com/api"},
            f"/api{Endpoint.EVENT}",
        ),
    ],
)
def test_event_namespace(mocker, kwargs, expected):
    """Test the event namespace.

    Args:
        mocker: The pytest mock object.
        kwargs: The Config kwargs.
        expected: Expected namespace
    """
    conf = rx.Config(**kwargs)
    mocker.patch("reflex.config.get_config", return_value=conf)

    config = reflex.config.get_config()
    assert conf == config
    assert config.get_event_namespace() == expected


DEFAULT_CONFIG = rx.Config(app_name="a")


@pytest.mark.parametrize(
    ("config_kwargs", "env_vars", "set_persistent_vars", "exp_config_values"),
    [
        (
            {},
            {},
            {},
            {
                "api_url": DEFAULT_CONFIG.api_url,
                "backend_port": DEFAULT_CONFIG.backend_port,
                "deploy_url": DEFAULT_CONFIG.deploy_url,
                "frontend_port": DEFAULT_CONFIG.frontend_port,
            },
        ),
        # Ports set in config kwargs
        (
            {"backend_port": 8001, "frontend_port": 3001},
            {},
            {},
            {
                "api_url": "http://localhost:8001",
                "backend_port": 8001,
                "deploy_url": "http://localhost:3001",
                "frontend_port": 3001,
            },
        ),
        # Ports set in environment take precedence
        (
            {"backend_port": 8001, "frontend_port": 3001},
            {"BACKEND_PORT": 8002},
            {},
            {
                "api_url": "http://localhost:8002",
                "backend_port": 8002,
                "deploy_url": "http://localhost:3001",
                "frontend_port": 3001,
            },
        ),
        # Ports set on the command line take precedence
        (
            {"backend_port": 8001, "frontend_port": 3001},
            {"BACKEND_PORT": 8002},
            {"frontend_port": "3005"},
            {
                "api_url": "http://localhost:8002",
                "backend_port": 8002,
                "deploy_url": "http://localhost:3005",
                "frontend_port": 3005,
            },
        ),
        # api_url / deploy_url already set should not be overridden
        (
            {"api_url": "http://foo.bar:8900", "deploy_url": "http://foo.bar:3001"},
            {"BACKEND_PORT": 8002},
            {"frontend_port": "3005"},
            {
                "api_url": "http://foo.bar:8900",
                "backend_port": 8002,
                "deploy_url": "http://foo.bar:3001",
                "frontend_port": 3005,
            },
        ),
    ],
)
def test_replace_defaults(
    monkeypatch,
    config_kwargs,
    env_vars,
    set_persistent_vars,
    exp_config_values,
):
    """Test that the config replaces defaults with values from the environment.

    Args:
        monkeypatch: The pytest monkeypatch object.
        config_kwargs: The config kwargs.
        env_vars: The environment variables.
        set_persistent_vars: The values passed to config._set_persistent variables.
        exp_config_values: The expected config values.
    """
    mock_os_env = os.environ.copy()
    monkeypatch.setattr(reflex.config.os, "environ", mock_os_env)  # type: ignore
    mock_os_env.update({k: str(v) for k, v in env_vars.items()})
    c = rx.Config(app_name="a", **config_kwargs)
    c._set_persistent(**set_persistent_vars)
    for key, value in exp_config_values.items():
        assert getattr(c, key) == value


def reflex_dir_constant() -> Path:
    return environment.REFLEX_DIR.get()


def test_reflex_dir_env_var(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test that the REFLEX_DIR environment variable is used to set the Reflex.DIR constant.

    Args:
        monkeypatch: The pytest monkeypatch object.
        tmp_path: The pytest tmp_path object.
    """
    monkeypatch.setenv("REFLEX_DIR", str(tmp_path))

    mp_ctx = multiprocessing.get_context(method="spawn")
    assert reflex_dir_constant() == tmp_path
    with mp_ctx.Pool(processes=1) as pool:
        assert pool.apply(reflex_dir_constant) == tmp_path


def test_interpret_enum_env() -> None:
    assert interpret_enum_env(Env.PROD.value, Env, "REFLEX_ENV") == Env.PROD


def test_interpret_int_env() -> None:
    assert interpret_int_env("3001", "FRONTEND_PORT") == 3001


@pytest.mark.parametrize("value, expected", [("true", True), ("false", False)])
def test_interpret_bool_env(value: str, expected: bool) -> None:
    assert interpret_boolean_env(value, "TELEMETRY_ENABLED") == expected


def test_env_var():
    class TestEnv:
        BLUBB: EnvVar[str] = env_var("default")
        INTERNAL: EnvVar[str] = env_var("default", internal=True)
        BOOLEAN: EnvVar[bool] = env_var(False)

    assert TestEnv.BLUBB.get() == "default"
    assert TestEnv.BLUBB.name == "BLUBB"
    TestEnv.BLUBB.set("new")
    assert os.environ.get("BLUBB") == "new"
    assert TestEnv.BLUBB.get() == "new"
    TestEnv.BLUBB.set(None)
    assert "BLUBB" not in os.environ

    assert TestEnv.INTERNAL.get() == "default"
    assert TestEnv.INTERNAL.name == "__INTERNAL"
    TestEnv.INTERNAL.set("new")
    assert os.environ.get("__INTERNAL") == "new"
    assert TestEnv.INTERNAL.get() == "new"
    assert TestEnv.INTERNAL.getenv() == "new"
    TestEnv.INTERNAL.set(None)
    assert "__INTERNAL" not in os.environ

    assert TestEnv.BOOLEAN.get() is False
    assert TestEnv.BOOLEAN.name == "BOOLEAN"
    TestEnv.BOOLEAN.set(True)
    assert os.environ.get("BOOLEAN") == "True"
    assert TestEnv.BOOLEAN.get() is True
    TestEnv.BOOLEAN.set(False)
    assert os.environ.get("BOOLEAN") == "False"
    assert TestEnv.BOOLEAN.get() is False
    TestEnv.BOOLEAN.set(None)
    assert "BOOLEAN" not in os.environ
