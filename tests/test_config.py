import os

import pytest

import reflex as rx
from reflex.config import get_config


def test_requires_app_name():
    """Test that a config requires an app_name."""
    with pytest.raises(ValueError):
        rx.Config()


def test_set_app_name(base_config_values):
    """Test that the app name is set to the value passed in.

    Args:
        base_config_values: Config values.
    """
    config = rx.Config(**base_config_values)
    assert config.app_name == base_config_values["app_name"]


@pytest.mark.parametrize(
    "param",
    [
        "db_config",
        "admin_dash",
        "env_path",
    ],
)
def test_deprecated_params(base_config_values, param):
    """Test that deprecated params are removed from the config.

    Args:
        base_config_values: Config values.
        param: The deprecated param.
    """
    with pytest.raises(ValueError):
        rx.Config(**base_config_values, **{param: "test"})


@pytest.mark.parametrize(
    "env_var, value",
    [
        ("APP_NAME", "my_test_app"),
        ("FRONTEND_PORT", 3001),
        ("BACKEND_PORT", 8001),
        ("API_URL", "https://mybackend.com:8000"),
        ("DEPLOY_URL", "https://myfrontend.com"),
        ("BACKEND_HOST", "127.0.0.1"),
        ("DB_URL", "postgresql://user:pass@localhost:5432/db"),
        ("REDIS_URL", "redis://localhost:6379"),
        ("TIMEOUT", 600),
    ],
)
def test_update_from_env(base_config_values, monkeypatch, env_var, value):
    """Test that environment variables override config values.

    Args:
        base_config_values: Config values.
        monkeypatch: The pytest monkeypatch object.
        env_var: The environment variable name.
        value: The environment variable value.
    """
    monkeypatch.setenv(env_var, value)
    assert os.environ.get(env_var) == str(value)
    config = rx.Config(**base_config_values)
    assert getattr(config, env_var.lower()) == value


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"app_name": "test_app", "api_url": "http://example.com"}, "/event"),
        ({"app_name": "test_app", "api_url": "http://example.com/api"}, "/api/event"),
        ({"app_name": "test_app", "event_namespace": "/event"}, "/event"),
        ({"app_name": "test_app", "event_namespace": "event"}, "/event"),
        ({"app_name": "test_app", "event_namespace": "event/"}, "/event"),
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

    config = get_config()
    assert config.get_event_namespace() == expected
