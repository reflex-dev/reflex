import importlib
import importlib.util
import logging
import multiprocessing
import os
import sys
import textwrap
import threading
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import reflex_base.config
from pytest_mock import MockerFixture
from reflex_base.constants import Endpoint, Env
from reflex_base.plugins import Plugin
from reflex_base.plugins.sitemap import SitemapPlugin
from reflex_base.utils.exceptions import ConfigError, InvalidPluginConfigError

import reflex as rx
from reflex.environment import (
    EnvVar,
    env_var,
    environment,
    interpret_boolean_env,
    interpret_enum_env,
    interpret_int_env,
)

CONFIG_MODULE = "rxconfig"
STATE_MODULE = "config_reload_state_module"
DEPENDENCY_MODULE = "config_reload_dependency"
PACKAGE_NAME = "config_reload_package"
PACKAGE_STATE_MODULE = f"{PACKAGE_NAME}.state"
PACKAGE_SETTINGS_MODULE = f"{PACKAGE_NAME}.settings"


def test_requires_app_name():
    """Test that a config requires an app_name."""
    with pytest.raises(TypeError):
        rx.Config()  # pyright: ignore[reportCallIssue]


def test_set_app_name(base_config_values):
    """Test that the app name is set to the value passed in.

    Args:
        base_config_values: Config values.
    """
    config = rx.Config(**base_config_values)
    assert config.app_name == base_config_values["app_name"]


def test_default_color_mode_default(base_config_values):
    """Test that default_color_mode defaults to "system".

    Args:
        base_config_values: Config values.
    """
    config = rx.Config(**base_config_values)
    assert config.default_color_mode == "system"


def test_frozen_lockfile_default(base_config_values):
    """Test that frozen_lockfile defaults to True (lockfile enforcement on).

    Args:
        base_config_values: Config values.
    """
    config = rx.Config(**base_config_values)
    assert config.frozen_lockfile is True


@pytest.mark.parametrize(
    ("env_var", "value"),
    [
        ("REFLEX_APP_NAME", "my_test_app"),
        ("REFLEX_FRONTEND_PORT", 3001),
        ("REFLEX_FRONTEND_PATH", "/test"),
        ("REFLEX_BACKEND_PORT", 8001),
        ("REFLEX_BACKEND_PATH", "/api"),
        ("REFLEX_API_URL", "https://mybackend.com:8000"),
        ("REFLEX_DEPLOY_URL", "https://myfrontend.com"),
        ("REFLEX_BACKEND_HOST", "127.0.0.1"),
        ("REFLEX_DB_URL", "postgresql://user:pass@localhost:5432/db"),
        ("REFLEX_REDIS_URL", "redis://localhost:6379"),
        ("REFLEX_TELEMETRY_ENABLED", False),
        ("REFLEX_TELEMETRY_ENABLED", True),
        ("REFLEX_FROZEN_LOCKFILE", False),
        ("REFLEX_FROZEN_LOCKFILE", True),
        ("REFLEX_DEFAULT_COLOR_MODE", "dark"),
    ],
)
def test_update_from_env(
    base_config_values: dict[str, Any],
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
    # Remove REFLEX_ prefix to get the actual field name
    field_name = env_var.removeprefix("REFLEX_").lower()
    assert getattr(config, field_name) == value


def test_update_from_env_path(
    base_config_values: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """Test that environment variables override config values.

    Args:
        base_config_values: Config values.
        monkeypatch: The pytest monkeypatch object.
        tmp_path: The pytest tmp_path fixture object.
    """
    monkeypatch.setenv("REFLEX_BUN_PATH", "/test")
    assert os.environ.get("REFLEX_BUN_PATH") == "/test"
    with pytest.raises(ValueError):
        rx.Config(**base_config_values)

    monkeypatch.setenv("REFLEX_BUN_PATH", str(tmp_path))
    assert os.environ.get("REFLEX_BUN_PATH") == str(tmp_path)
    config = rx.Config(**base_config_values)
    assert config.bun_path == tmp_path


def test_update_from_env_cors(
    base_config_values: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """Test that environment variables override config values.

    Args:
        base_config_values: Config values.
        monkeypatch: The pytest monkeypatch object.
        tmp_path: The pytest tmp_path fixture object.
    """
    config = rx.Config(**base_config_values)
    assert config.cors_allowed_origins == ("*",)

    monkeypatch.setenv("REFLEX_CORS_ALLOWED_ORIGINS", "")
    config = rx.Config(**base_config_values)
    assert config.cors_allowed_origins == ("*",)

    monkeypatch.setenv("REFLEX_CORS_ALLOWED_ORIGINS", "https://foo.example.com")
    config = rx.Config(**base_config_values)
    assert config.cors_allowed_origins == [
        "https://foo.example.com",
    ]

    monkeypatch.setenv(
        "REFLEX_CORS_ALLOWED_ORIGINS", "http://example.com, http://another.com "
    )
    config = rx.Config(**base_config_values)
    assert config.cors_allowed_origins == [
        "http://example.com",
        "http://another.com",
    ]


def test_update_from_env_frontend_compression_formats(
    base_config_values: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
):
    """Test comma-delimited frontend compression formats from the environment."""
    monkeypatch.setenv(
        "REFLEX_FRONTEND_COMPRESSION_FORMATS", "gzip, brotli , zstd, gzip"
    )
    config = rx.Config(**base_config_values)
    assert config.frontend_compression_formats == ["gzip", "brotli", "zstd"]


def test_invalid_frontend_compression_formats(base_config_values: dict[str, Any]):
    """Test that unsupported frontend compression formats raise config errors."""
    with pytest.raises(
        ConfigError,
        match="frontend_compression_formats contains unsupported format",
    ):
        rx.Config(
            **base_config_values,
            frontend_compression_formats=["gzip", "snappy"],
        )


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (
            {"app_name": "test_app", "api_url": "http://example.com"},
            f"{Endpoint.EVENT}",
        ),
        (
            {"app_name": "test_app", "api_url": "http://example.com/api"},
            f"/api{Endpoint.EVENT}",
        ),
        (
            {
                "app_name": "test_app",
                "api_url": "http://example.com",
                "backend_path": "/api",
            },
            f"/api{Endpoint.EVENT}",
        ),
        (
            {
                "app_name": "test_app",
                "api_url": "http://example.com",
                "backend_path": "api/",
            },
            f"/api{Endpoint.EVENT}",
        ),
        (
            {
                "app_name": "test_app",
                "api_url": "http://example.com",
                "backend_path": "/api/v1",
            },
            f"/api/v1{Endpoint.EVENT}",
        ),
    ],
)
def test_event_namespace(mocker: MockerFixture, kwargs, expected):
    """Test the event namespace.

    Args:
        mocker: The pytest mock object.
        kwargs: The Config kwargs.
        expected: Expected namespace
    """
    conf = rx.Config(**kwargs)
    mocker.patch("reflex_base.config.get_config", return_value=conf)

    config = reflex_base.config.get_config()
    assert conf == config
    assert config.get_event_namespace() == expected


@pytest.mark.parametrize(
    ("backend_path", "path", "expected"),
    [
        ("", "/ping", "/ping"),
        ("/api", "/ping", "/api/ping"),
        ("api", "/ping", "/api/ping"),
        ("/api/", "/ping", "/api/ping"),
        ("/api", "", ""),
        ("/api", "relative/path", "relative/path"),
        ("/api/v1", "/ping", "/api/v1/ping"),
        ("api/v1/", "/ping", "/api/v1/ping"),
        ("/api/v1", "", ""),
        ("/api/v1", "relative/path", "relative/path"),
    ],
)
def test_prepend_backend_path(backend_path: str, path: str, expected: str):
    """Test that prepend_backend_path normalizes and prefixes paths correctly.

    Args:
        backend_path: The configured backend_path.
        path: The input path to prefix.
        expected: The expected output.
    """
    config = rx.Config(app_name="test_app", backend_path=backend_path)
    assert config.prepend_backend_path(path) == expected


@pytest.mark.parametrize("backend_path", ["", "/api", "api/", "/api/v1"])
@pytest.mark.parametrize("endpoint", list(Endpoint))
def test_endpoint_get_url_with_backend_path(
    mocker: MockerFixture, backend_path: str, endpoint: Endpoint
):
    """Endpoint.get_url() includes backend_path; WS protocol swap still works for EVENT.

    Args:
        mocker: The pytest mock object.
        backend_path: The configured backend_path.
        endpoint: The endpoint to generate a URL for.
    """
    conf = rx.Config(
        app_name="test_app",
        api_url="http://example.com",
        backend_path=backend_path,
    )
    mocker.patch("reflex_base.config.get_config", return_value=conf)

    url = endpoint.get_url()
    prefix = f"/{backend_path.strip('/')}" if backend_path.strip("/") else ""
    if endpoint is Endpoint.EVENT:
        assert url == f"ws://example.com{prefix}{endpoint}"
    else:
        assert url == f"http://example.com{prefix}{endpoint}"


def test_get_event_namespace_matches_mount_path(mocker: MockerFixture):
    """Socket.IO namespace must equal the HTTP mount path for EVENT.

    Args:
        mocker: The pytest mock object.
    """
    conf = rx.Config(
        app_name="test_app",
        api_url="http://example.com",
        backend_path="/api",
    )
    mocker.patch("reflex_base.config.get_config", return_value=conf)

    assert conf.get_event_namespace() == conf.prepend_backend_path(str(Endpoint.EVENT))


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
            {"REFLEX_BACKEND_PORT": 8002},
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
            {"REFLEX_BACKEND_PORT": 8002},
            {"frontend_port": 3005},
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
            {"REFLEX_BACKEND_PORT": 8002},
            {"frontend_port": 3005},
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
    monkeypatch.setattr(reflex_base.config.os, "environ", mock_os_env)  # pyright: ignore[reportPrivateImportUsage]
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


@pytest.mark.parametrize(("value", "expected"), [("true", True), ("false", False)])
def test_interpret_bool_env(value: str, expected: bool) -> None:
    assert interpret_boolean_env(value, "TELEMETRY_ENABLED") == expected


def test_env_var():
    class TestEnv:
        BLUBB: EnvVar[str] = env_var("default")
        INTERNAL: EnvVar[str] = env_var("default", internal=True)
        BOOLEAN: EnvVar[bool] = env_var(False)
        LIST: EnvVar[list[int]] = env_var([1, 2, 3])

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

    assert TestEnv.LIST.get() == [1, 2, 3]
    assert TestEnv.LIST.name == "LIST"
    TestEnv.LIST.set([4, 5, 6])
    assert os.environ.get("LIST") == "4:5:6"
    assert TestEnv.LIST.get() == [4, 5, 6]
    TestEnv.LIST.set(None)
    assert "LIST" not in os.environ


@pytest.fixture
def restore_env():
    """Fixture to restore the environment variables after the test.

    Yields:
        None: Placeholder for the test to run.
    """
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.mark.usefixtures("restore_env")
@pytest.mark.parametrize(
    ("file_map", "env_file", "exp_env_vars"),
    [
        (
            {
                ".env": "APP_NAME=my_test_app\nFRONTEND_PORT=3001\nBACKEND_PORT=8001\n",
            },
            "{path}/.env",
            {
                "APP_NAME": "my_test_app",
                "FRONTEND_PORT": "3001",
                "BACKEND_PORT": "8001",
            },
        ),
        (
            {
                ".env": "FRONTEND_PORT=4001",
            },
            "{path}/.env{sep}{path}/.env.local",
            {
                "FRONTEND_PORT": "4001",
            },
        ),
        (
            {
                ".env": "APP_NAME=my_test_app\nFRONTEND_PORT=3001\nBACKEND_PORT=8001\n",
                ".env.local": "FRONTEND_PORT=3002\n",
            },
            "{path}/.env.local{sep}{path}/.env",
            {
                "APP_NAME": "my_test_app",
                "FRONTEND_PORT": "3002",  # Overrides .env
                "BACKEND_PORT": "8001",
            },
        ),
    ],
)
def test_env_file(
    tmp_path: Path,
    file_map: dict[str, str],
    env_file: str,
    exp_env_vars: dict[str, str],
) -> None:
    """Test that the env_file method loads environment variables from a file.

    Args:
        tmp_path: The pytest tmp_path object.
        file_map: A mapping of file names to their contents.
        env_file: The path to the environment file to load.
        exp_env_vars: The expected environment variables after loading the file.
    """
    for filename, content in file_map.items():
        (tmp_path / filename).write_text(content)

    _ = rx.Config(
        app_name="test_env_file",
        env_file=env_file.format(path=tmp_path, sep=os.pathsep),
    )
    for key, value in exp_env_vars.items():
        assert os.environ.get(key) == value


class TestDisablePlugins:
    """Tests for the disable_plugins config option."""

    def test_disable_with_plugin_class(self):
        """Test disabling a plugin by passing the class (type)."""
        config = rx.Config(app_name="test", disable_plugins=[SitemapPlugin])
        assert not any(isinstance(p, SitemapPlugin) for p in config.plugins)

    def test_disable_with_plugin_instance_backward_compat(self):
        """Test disabling a plugin by passing an instance (deprecated)."""
        config = rx.Config(app_name="test", disable_plugins=[SitemapPlugin()])  # pyright: ignore[reportArgumentType]
        assert not any(isinstance(p, SitemapPlugin) for p in config.plugins)

    def test_disable_with_string_backward_compat(self):
        """Test disabling a plugin by passing a string (deprecated)."""
        config = rx.Config(
            app_name="test",
            disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],  # pyright: ignore[reportArgumentType]
        )
        assert not any(isinstance(p, SitemapPlugin) for p in config.plugins)

    def test_disable_plugins_normalized_to_classes(self):
        """Test that disable_plugins entries are normalized to Plugin subclasses."""
        config = rx.Config(app_name="test", disable_plugins=[SitemapPlugin])
        assert all(
            isinstance(dp, type) and issubclass(dp, Plugin)
            for dp in config.disable_plugins
        )

    def test_disable_instance_normalized_to_class(self):
        """Test that a Plugin instance in disable_plugins is normalized to its class."""
        config = rx.Config(app_name="test", disable_plugins=[SitemapPlugin()])  # pyright: ignore[reportArgumentType]
        assert config.disable_plugins == [SitemapPlugin]

    def test_disable_string_normalized_to_class(self):
        """Test that a string in disable_plugins is normalized to the class."""
        config = rx.Config(
            app_name="test",
            disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],  # pyright: ignore[reportArgumentType]
        )
        assert config.disable_plugins == [SitemapPlugin]

    def test_disable_and_plugins_conflict_warns(self):
        """Test that a warning is issued when a plugin is both enabled and disabled."""
        config = rx.Config(
            app_name="test",
            plugins=[SitemapPlugin()],
            disable_plugins=[SitemapPlugin],
        )
        # Plugin should still be in plugins list (just warned)
        assert any(isinstance(p, SitemapPlugin) for p in config.plugins)

    def test_no_disable_adds_builtin(self):
        """Test that builtin plugins are added when not disabled."""
        config = rx.Config(app_name="test")
        assert any(isinstance(p, SitemapPlugin) for p in config.plugins)

    def test_disable_non_builtin_plugin_does_not_warn(
        self, caplog: pytest.LogCaptureFixture
    ):
        """Disabling a non-builtin plugin emits no warning.

        Non-builtin plugins (e.g. ones added via REFLEX_EXTRA_PLUGINS) can be
        disabled through this same mechanism, so disabling a plugin that is not
        enabled-by-default must not warn.
        """

        class CustomPlugin(Plugin): ...

        rx.Config(app_name="test", disable_plugins=[CustomPlugin])
        assert not any(
            "not a built-in plugin" in r.getMessage() for r in caplog.records
        )


def test_plugins_instance_passthrough():
    """A Plugin instance is kept as-is (issue #6440)."""
    instance = SitemapPlugin()
    config = rx.Config(app_name="test", plugins=[instance])
    assert instance in config.plugins


def test_plugins_class_auto_instantiated():
    """A Plugin subclass is auto-instantiated rather than raising deep in the compiler (issue #6440)."""
    config = rx.Config(app_name="test", plugins=[SitemapPlugin])  # pyright: ignore[reportArgumentType]
    instances = [p for p in config.plugins if isinstance(p, SitemapPlugin)]
    assert len(instances) == 1
    # And it must be an instance, not the class itself.
    assert not isinstance(instances[0], type)


def test_plugins_invalid_value_raises_config_error():
    """A non-Plugin value raises ConfigError naming the entry, not a deep TypeError (issue #6440)."""
    with pytest.raises(ConfigError, match=r"reflex\.Config\.plugins"):
        rx.Config(app_name="test", plugins=["not-a-plugin"])  # pyright: ignore[reportArgumentType]


def test_plugins_class_requiring_args_raises_config_error():
    """A Plugin subclass that needs constructor args raises a clear ConfigError (issue #6440)."""

    class NeedsArgs(Plugin):
        def __init__(self, required):
            self.required = required

    with pytest.raises(ConfigError, match="NeedsArgs"):
        rx.Config(app_name="test", plugins=[NeedsArgs])  # pyright: ignore[reportArgumentType]


# Module-level plugins so REFLEX_EXTRA_PLUGINS can resolve them by import path.
class ExtraPluginA(Plugin):
    """First plugin used to exercise REFLEX_EXTRA_PLUGINS."""


class ExtraPluginB(Plugin):
    """Second plugin used to exercise REFLEX_EXTRA_PLUGINS."""


# Records every instantiation so tests can assert a disabled plugin is never built.
_extra_plugin_instantiations: list[str] = []


class TrackedExtraPlugin(Plugin):
    """Plugin that records when its constructor runs."""

    def __init__(self):
        """Record that this plugin was instantiated."""
        _extra_plugin_instantiations.append(type(self).__name__)


class NeedsArgsExtraPlugin(Plugin):
    """Plugin whose constructor requires an argument, so it cannot be auto-built."""

    def __init__(self, required):
        """Initialize, requiring an argument.

        Args:
            required: A required positional argument.
        """
        self.required = required


_EXTRA_PLUGIN_A = "tests.units.test_config.ExtraPluginA"
_EXTRA_PLUGIN_B = "tests.units.test_config.ExtraPluginB"
_TRACKED_EXTRA_PLUGIN = "tests.units.test_config.TrackedExtraPlugin"
_NEEDS_ARGS_EXTRA_PLUGIN = "tests.units.test_config.NeedsArgsExtraPlugin"
_BAD_PLUGIN_SPEC = "tests.units.test_config.NoSuchPlugin"


def test_extra_plugins_appends_single_plugin(monkeypatch: pytest.MonkeyPatch):
    """A single extra plugin is appended to the plugins list."""
    monkeypatch.setenv("REFLEX_EXTRA_PLUGINS", _EXTRA_PLUGIN_A)
    config = rx.Config(app_name="test")
    assert any(isinstance(p, ExtraPluginA) for p in config.plugins)


def test_extra_plugins_appends_multiple_plugins(monkeypatch: pytest.MonkeyPatch):
    """Multiple colon-separated extra plugins are all appended."""
    monkeypatch.setenv("REFLEX_EXTRA_PLUGINS", f"{_EXTRA_PLUGIN_A}:{_EXTRA_PLUGIN_B}")
    config = rx.Config(app_name="test")
    assert any(isinstance(p, ExtraPluginA) for p in config.plugins)
    assert any(isinstance(p, ExtraPluginB) for p in config.plugins)


def test_extra_plugins_preserves_config_plugins(monkeypatch: pytest.MonkeyPatch):
    """Extra plugins are appended without replacing plugins from the config."""
    monkeypatch.setenv("REFLEX_EXTRA_PLUGINS", _EXTRA_PLUGIN_B)
    instance = ExtraPluginA()
    config = rx.Config(app_name="test", plugins=[instance])
    # The config-provided instance is preserved...
    assert instance in config.plugins
    # ...and the extra plugin from the env var is appended.
    assert any(isinstance(p, ExtraPluginB) for p in config.plugins)


def test_extra_plugins_unset_appends_nothing(monkeypatch: pytest.MonkeyPatch):
    """When unset, no extra plugins leak into the plugins list."""
    monkeypatch.delenv("REFLEX_EXTRA_PLUGINS", raising=False)
    config = rx.Config(app_name="test")
    assert not any(isinstance(p, (ExtraPluginA, ExtraPluginB)) for p in config.plugins)


def test_extra_plugins_does_not_duplicate_existing_type(
    monkeypatch: pytest.MonkeyPatch,
):
    """An extra plugin whose type is already configured is not added twice."""
    monkeypatch.setenv("REFLEX_EXTRA_PLUGINS", _EXTRA_PLUGIN_A)
    config = rx.Config(app_name="test", plugins=[ExtraPluginA()])
    instances = [p for p in config.plugins if isinstance(p, ExtraPluginA)]
    assert len(instances) == 1


def test_extra_plugins_respects_disable_plugins(monkeypatch: pytest.MonkeyPatch):
    """An extra plugin disabled via disable_plugins is not appended."""
    monkeypatch.setenv("REFLEX_EXTRA_PLUGINS", _EXTRA_PLUGIN_A)
    config = rx.Config(app_name="test", disable_plugins=[ExtraPluginA])
    assert not any(isinstance(p, ExtraPluginA) for p in config.plugins)


def test_extra_plugins_does_not_replace_like_reflex_plugins(
    monkeypatch: pytest.MonkeyPatch,
):
    """REFLEX_PLUGINS replaces config plugins, unlike REFLEX_EXTRA_PLUGINS."""
    monkeypatch.setenv("REFLEX_PLUGINS", _EXTRA_PLUGIN_A)
    config = rx.Config(app_name="test", plugins=[ExtraPluginB()])
    # The config plugin is dropped by the REFLEX_PLUGINS replacement.
    assert not any(isinstance(p, ExtraPluginB) for p in config.plugins)
    assert any(isinstance(p, ExtraPluginA) for p in config.plugins)


def test_extra_plugins_appends_on_top_of_reflex_plugins(
    monkeypatch: pytest.MonkeyPatch,
):
    """REFLEX_EXTRA_PLUGINS appends on top of the REFLEX_PLUGINS replacement."""
    monkeypatch.setenv("REFLEX_PLUGINS", _EXTRA_PLUGIN_A)
    monkeypatch.setenv("REFLEX_EXTRA_PLUGINS", _EXTRA_PLUGIN_B)
    config = rx.Config(app_name="test", plugins=[SitemapPlugin()])
    assert any(isinstance(p, ExtraPluginA) for p in config.plugins)
    assert any(isinstance(p, ExtraPluginB) for p in config.plugins)


def test_extra_plugins_enabled_is_instantiated(monkeypatch: pytest.MonkeyPatch):
    """A non-disabled extra plugin has its constructor run exactly once."""
    _extra_plugin_instantiations.clear()
    monkeypatch.setenv("REFLEX_EXTRA_PLUGINS", _TRACKED_EXTRA_PLUGIN)
    config = rx.Config(app_name="test")
    assert any(isinstance(p, TrackedExtraPlugin) for p in config.plugins)
    assert _extra_plugin_instantiations == ["TrackedExtraPlugin"]


def test_extra_plugins_disabled_is_never_instantiated(monkeypatch: pytest.MonkeyPatch):
    """A disabled extra plugin is imported but its constructor never runs."""
    _extra_plugin_instantiations.clear()
    monkeypatch.setenv("REFLEX_EXTRA_PLUGINS", _TRACKED_EXTRA_PLUGIN)
    config = rx.Config(app_name="test", disable_plugins=[TrackedExtraPlugin])
    assert not any(isinstance(p, TrackedExtraPlugin) for p in config.plugins)
    # The constructor must never have run for the disabled plugin.
    assert _extra_plugin_instantiations == []


def test_extra_plugins_bad_spec_warns_and_keeps_valid(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """A bad REFLEX_EXTRA_PLUGINS entry warns but valid entries are still added."""
    monkeypatch.setenv("REFLEX_EXTRA_PLUGINS", f"{_BAD_PLUGIN_SPEC}:{_EXTRA_PLUGIN_A}")
    config = rx.Config(app_name="test")
    # The valid entry survives despite the bad one (no all-or-nothing failure).
    assert any(isinstance(p, ExtraPluginA) for p in config.plugins)
    assert any(
        "REFLEX_EXTRA_PLUGINS" in r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING
    )


def test_extra_plugins_uninstantiable_warns_and_skips(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """An extra plugin that cannot be instantiated warns and is skipped, not fatal."""
    monkeypatch.setenv("REFLEX_EXTRA_PLUGINS", _NEEDS_ARGS_EXTRA_PLUGIN)
    config = rx.Config(app_name="test")
    assert not any(isinstance(p, NeedsArgsExtraPlugin) for p in config.plugins)
    assert any(
        "could not be instantiated" in r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING
    )


def test_plugins_bad_env_spec_raises_invalid_plugin_config_error(
    monkeypatch: pytest.MonkeyPatch,
):
    """An invalid REFLEX_PLUGINS import path raises InvalidPluginConfigError.

    The dedicated subclass lets error tracking catch plugin-load failures
    specifically, while still subclassing ConfigError for existing handlers.
    """
    monkeypatch.setenv("REFLEX_PLUGINS", _BAD_PLUGIN_SPEC)
    with pytest.raises(InvalidPluginConfigError, match="could not be loaded"):
        rx.Config(app_name="test")
    assert issubclass(InvalidPluginConfigError, ConfigError)


def test_disable_plugins_bad_env_spec_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """An invalid REFLEX_DISABLE_PLUGINS import path warns but does not crash."""
    monkeypatch.setenv("REFLEX_DISABLE_PLUGINS", _BAD_PLUGIN_SPEC)
    rx.Config(app_name="test")
    assert any(
        "REFLEX_DISABLE_PLUGINS" in r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING
    )


def test_get_config_loads_once_for_shared_context(monkeypatch: pytest.MonkeyPatch):
    """Concurrent first access to a shared context loads the config exactly once.

    Threads sharing one RegistrationContext (e.g. a threadpool serving requests
    under the app's context) must all observe the same Config instance, with
    rxconfig loaded a single time.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    from reflex_base.registry import RegistrationContext

    n_threads = 8
    load_count = 0
    count_lock = threading.Lock()

    def slow_load() -> rx.Config:
        nonlocal load_count
        with count_lock:
            load_count += 1
        # Widen the check-to-set window so an unserialized load path races.
        time.sleep(0.05)
        return rx.Config(app_name="shared")

    monkeypatch.setattr(reflex_base.config, "_get_config", slow_load)

    ctx = RegistrationContext()
    barrier = threading.Barrier(n_threads)
    results: list[rx.Config | None] = [None] * n_threads

    def worker(i: int) -> None:
        RegistrationContext._context_var.set(ctx)
        barrier.wait()
        results[i] = reflex_base.config.get_config()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert load_count == 1
    assert all(config is results[0] for config in results)


class _RaceGate:
    """Events an rxconfig.py under test uses to hand control back mid-load."""

    def __init__(self) -> None:
        """Create the gate with both events unset."""
        self.in_load = threading.Event()
        self.release = threading.Event()


@pytest.fixture
def race_gate(monkeypatch: pytest.MonkeyPatch) -> _RaceGate:
    """Install a module an rxconfig.py under test can import to pause itself.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The gate: `in_load` is set once rxconfig.py is running, and it blocks
        on `release` until the test lets it finish.
    """
    gate = _RaceGate()
    monkeypatch.setitem(sys.modules, "_config_race_gate", gate)  # pyright: ignore[reportArgumentType]
    return gate


def test_get_config_keeps_sys_path_usable_for_other_threads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    race_gate: _RaceGate,
    clean_config_modules: None,
):
    """Importing an unrelated module while rxconfig loads must succeed.

    The loader used to clear sys.path down to the cwd for the duration of
    the rxconfig import, so any concurrent first-time import in another
    thread (e.g. the lazy granian import when the backend starts) failed
    with ModuleNotFoundError.

    Args:
        tmp_path: The pytest tmp_path fixture.
        monkeypatch: The pytest monkeypatch fixture.
        race_gate: Handle to pause the load inside rxconfig.py.
        clean_config_modules: Cleanup for modules left behind by the load.
    """
    (tmp_path / "rxconfig.py").write_text(
        textwrap.dedent(
            """
            import _config_race_gate
            import reflex as rx

            _config_race_gate.in_load.set()
            _config_race_gate.release.wait(timeout=5)
            config = rx.Config(app_name="racer")
            """
        )
    )
    monkeypatch.chdir(tmp_path)
    # A stdlib module that nothing imports by default; drop it so the import
    # below walks sys.path again.
    monkeypatch.delitem(sys.modules, "colorsys", raising=False)
    sys_path_before = sys.path.copy()

    loader = threading.Thread(target=reflex_base.config._get_config)
    loader.start()
    try:
        assert race_gate.in_load.wait(timeout=5)
        import colorsys  # noqa: F401
    finally:
        race_gate.release.set()
        loader.join(timeout=5)
    assert not loader.is_alive()
    # The temporarily prepended cwd entry was removed again.
    assert sys.path == sys_path_before


def test_get_config_keeps_caller_owned_cwd_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_config_modules: None
):
    """A pre-existing cwd entry survives even if rxconfig removes one itself.

    The cleanup must only take back the entry the loader prepended, not a
    caller-owned equal entry.

    Args:
        tmp_path: The pytest tmp_path fixture.
        monkeypatch: The pytest monkeypatch fixture.
        clean_config_modules: Cleanup for modules left behind by the load.
    """
    (tmp_path / "rxconfig.py").write_text(
        textwrap.dedent(
            """
            import os
            import sys

            import reflex as rx

            sys.path.remove(os.getcwd())
            config = rx.Config(app_name="pathological")
            """
        )
    )
    monkeypatch.chdir(tmp_path)
    cwd = str(Path.cwd())
    monkeypatch.setattr(sys, "path", [cwd, *sys.path])
    caller_owned = sys.path.count(cwd)

    assert reflex_base.config._get_config().app_name == "pathological"
    assert sys.path.count(cwd) == caller_owned


def test_get_config_accepts_explicit_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_config_modules: None
):
    """An explicit project_root loads that project whatever the cwd is.

    Args:
        tmp_path: The pytest tmp_path fixture.
        monkeypatch: The pytest monkeypatch fixture.
        clean_config_modules: Cleanup for modules left behind by the load.
    """
    project = tmp_path / "project"
    project.mkdir()
    (project / "rxconfig.py").write_text(
        "import reflex as rx\nconfig = rx.Config(app_name='explicit')\n"
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    assert reflex_base.config._get_config(project).app_name == "explicit"


def _write_state_config(project: Path, app_name: str = "state_reload") -> None:
    """Write a config that imports a module defining a state class.

    Args:
        project: The project directory to populate.
        app_name: The app name written to the config.
    """
    project.mkdir(exist_ok=True)
    (project / f"{STATE_MODULE}.py").write_text(
        "import reflex as rx\n\nclass MyState(rx.State):\n    value: str = ''\n"
    )
    (project / "rxconfig.py").write_text(
        f"import {STATE_MODULE}\nimport reflex as rx\n\n"
        f"config = rx.Config(app_name={app_name!r})\n"
    )


def test_reload_config_does_not_redefine_project_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_config_modules: None
):
    """Reloading config does not re-import project modules that define state.

    Args:
        tmp_path: The pytest tmp_path fixture.
        monkeypatch: The pytest monkeypatch fixture.
        clean_config_modules: Cleanup for modules left behind by the load.
    """
    from reflex_base.registry import RegistrationContext

    _write_state_config(tmp_path)
    monkeypatch.chdir(tmp_path)

    with RegistrationContext() as context:
        assert reflex_base.config.get_config().app_name == "state_reload"
        assert reflex_base.config.reload_config().app_name == "state_reload"

        with context.fork():
            assert reflex_base.config.reload_config().app_name == "state_reload"


def test_get_config_reloads_project_state_for_each_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_config_modules: None
):
    """Initial config loads register project state in each context.

    Args:
        tmp_path: The pytest tmp_path fixture.
        monkeypatch: The pytest monkeypatch fixture.
        clean_config_modules: Cleanup for modules left behind by the load.
    """
    from reflex_base.registry import RegistrationContext

    _write_state_config(tmp_path)
    monkeypatch.chdir(tmp_path)

    with RegistrationContext() as first_context:
        reflex_base.config.get_config()
        first_state = next(
            state
            for state in first_context.base_states.values()
            if state.__module__ == STATE_MODULE
        )

    with RegistrationContext() as second_context:
        reflex_base.config.get_config()
        second_state = next(
            state
            for state in second_context.base_states.values()
            if state.__module__ == STATE_MODULE
        )

    assert second_state is not first_state


def test_reload_config_restores_modules_for_an_older_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_config_modules: None
):
    """Reloading an older context restores its project-local modules.

    Args:
        tmp_path: The pytest tmp_path fixture.
        monkeypatch: The pytest monkeypatch fixture.
        clean_config_modules: Cleanup for modules left behind by the load.
    """
    from reflex_base.registry import RegistrationContext

    first_project = tmp_path / "first"
    second_project = tmp_path / "second"
    _write_state_config(first_project, "first")
    _write_state_config(second_project, "second")

    first_context = RegistrationContext()
    with first_context:
        monkeypatch.chdir(first_project)
        assert reflex_base.config.get_config().app_name == "first"
        first_module = sys.modules[STATE_MODULE]

    with RegistrationContext():
        monkeypatch.chdir(second_project)
        assert reflex_base.config.get_config().app_name == "second"
        assert sys.modules[STATE_MODULE] is not first_module

    with first_context:
        monkeypatch.chdir(first_project)
        assert reflex_base.config.reload_config().app_name == "first"
        assert sys.modules[STATE_MODULE] is first_module


def test_reload_config_restores_state_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_config_modules: None
):
    """Reloading config preserves a package containing a registered state.

    Args:
        tmp_path: The pytest tmp_path fixture.
        monkeypatch: The pytest monkeypatch fixture.
        clean_config_modules: Cleanup for modules left behind by the load.
    """
    from reflex_base.registry import RegistrationContext

    package = tmp_path / PACKAGE_NAME
    package.mkdir()
    (package / "__init__.py").write_text(
        f"from .{PACKAGE_SETTINGS_MODULE.rsplit('.', maxsplit=1)[-1]} import APP_NAME\n"
    )
    (package / "settings.py").write_text("APP_NAME = 'first'\n")
    (package / "state.py").write_text(
        "import reflex as rx\n\nclass MyState(rx.State):\n    value: str = ''\n"
    )
    (tmp_path / f"{CONFIG_MODULE}.py").write_text(
        f"import {PACKAGE_STATE_MODULE}\nimport reflex as rx\n\n"
        f"import {PACKAGE_NAME}\n\n"
        f"config = rx.Config(app_name={PACKAGE_NAME}.APP_NAME)\n"
    )
    monkeypatch.chdir(tmp_path)

    with RegistrationContext():
        assert reflex_base.config.get_config().app_name == "first"
        (package / "settings.py").write_text("APP_NAME = 'second'\n")
        assert reflex_base.config.reload_config().app_name == "second"
        (package / "settings.py").write_text("APP_NAME = 'third'\n")
        assert reflex_base.config.reload_config().app_name == "third"
        assert PACKAGE_STATE_MODULE in sys.modules
        assert PACKAGE_NAME in sys.modules


def test_reload_config_preserves_state_defined_in_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_config_modules: None
):
    """Reloading config does not redefine a state defined in a package.

    Args:
        tmp_path: The pytest tmp_path fixture.
        monkeypatch: The pytest monkeypatch fixture.
        clean_config_modules: Cleanup for modules left behind by the load.
    """
    from reflex_base.registry import RegistrationContext

    package = tmp_path / PACKAGE_NAME
    package.mkdir()
    (package / "__init__.py").write_text(
        "import reflex as rx\n\nclass PackageState(rx.State):\n    value: str = ''\n"
    )
    (tmp_path / f"{CONFIG_MODULE}.py").write_text(
        f"import {PACKAGE_NAME}\nimport reflex as rx\n\n"
        "config = rx.Config(app_name='package_state')\n"
    )
    monkeypatch.chdir(tmp_path)

    with RegistrationContext():
        assert reflex_base.config.get_config().app_name == "package_state"
        assert reflex_base.config.reload_config().app_name == "package_state"


def _write_dependency_config(project: Path, app_name: str) -> None:
    """Write a config that imports a project-local non-state dependency.

    Args:
        project: The project directory to populate.
        app_name: The app name exposed by the dependency.
    """
    project.mkdir()
    (project / f"{DEPENDENCY_MODULE}.py").write_text(f"APP_NAME = {app_name!r}\n")
    (project / "rxconfig.py").write_text(
        f"import {DEPENDENCY_MODULE}\nimport reflex as rx\n\n"
        f"config = rx.Config(app_name={DEPENDENCY_MODULE}.APP_NAME)\n"
    )


def test_reload_config_evicts_modules_when_project_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_config_modules: None
):
    """Reloading a context after changing projects imports the new modules.

    Args:
        tmp_path: The pytest tmp_path fixture.
        monkeypatch: The pytest monkeypatch fixture.
        clean_config_modules: Cleanup for modules left behind by the load.
    """
    from reflex_base.registry import RegistrationContext

    first_project = tmp_path / "first"
    second_project = tmp_path / "second"
    _write_dependency_config(first_project, "first")
    _write_dependency_config(second_project, "second")

    with RegistrationContext():
        monkeypatch.chdir(first_project)
        assert reflex_base.config.get_config().app_name == "first"
        (first_project / f"{DEPENDENCY_MODULE}.py").write_text("APP_NAME = 'updated'\n")
        assert reflex_base.config.reload_config().app_name == "updated"
        monkeypatch.chdir(second_project)
        assert reflex_base.config.reload_config().app_name == "second"
        dependency = sys.modules[DEPENDENCY_MODULE]
        assert Path(dependency.__file__ or "").is_relative_to(second_project)


@pytest.fixture
def clean_config_modules() -> Generator[None, None, None]:
    """Drop the modules and dep records a real rxconfig load leaves behind.

    Yields:
        None, once the module table is clean.
    """
    names = (
        CONFIG_MODULE,
        "side_module",
        "chdir_dep_module",
        STATE_MODULE,
        DEPENDENCY_MODULE,
        PACKAGE_NAME,
        PACKAGE_STATE_MODULE,
        PACKAGE_SETTINGS_MODULE,
    )
    try:
        yield
    finally:
        for name in names:
            sys.modules.pop(name, None)
        reflex_base.config._config_module_deps.clear()


# Reruns: taking the prepended entry back out is itself a sys.path shrink, so
# a probe walk overlapping that one `del` can still skip an entry (~1 lookup in
# 5000, ~12% of runs here). That residual is what this test is meant to keep an
# eye on, not something a submitter can act on, so let it re-run rather than
# fail their PR. Reruns make a spurious failure ~0.02% per run; a test that
# fails all four attempts is a real regression, not this.
@pytest.mark.flaky(reruns=3)
def test_get_config_keeps_sys_path_intact_for_other_threads(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
    clean_config_modules: None,
):
    """Loading rxconfig must not shrink sys.path while other threads import.

    `reflex run` loads the config from the frontend thread while the main
    thread is still importing the backend; the import system walks sys.path
    by index, so shrinking it under another thread turns unrelated imports
    into ModuleNotFoundError. Unlike the gated test above, this one drives a
    real rxconfig load in a loop, so it also covers the path the loader takes
    around the actual import rather than a stubbed inner seam.

    Marked flaky: the loader's own cleanup can trip the probe on a small
    fraction of runs. It still fails every attempt against a loader that
    clears sys.path outright.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        tmp_path: The pytest tmp_path fixture.
        tmp_path_factory: The pytest tmp_path_factory fixture.
        clean_config_modules: Cleanup for modules left behind by the load.
    """
    (tmp_path / "rxconfig.py").write_text(
        "import reflex as rx\nconfig = rx.Config(app_name='race')\n"
    )
    monkeypatch.chdir(tmp_path)
    # A private module at the end of sys.path. Probing it with find_spec walks
    # sys.path the way an import does but never registers anything in
    # sys.modules, so the loader's own module bookkeeping cannot interfere.
    probe_dir = tmp_path_factory.mktemp("rx_race_probe")
    (probe_dir / "rx_race_probe.py").write_text("VALUE = 1\n")
    sys.path.append(str(probe_dir))
    importlib.invalidate_caches()
    stop = threading.Event()
    loader_errors: list[BaseException] = []

    def loader() -> None:
        while not stop.is_set():
            try:
                reflex_base.config._get_config()
            except BaseException as e:
                loader_errors.append(e)
                return

    thread = threading.Thread(target=loader)
    thread.start()
    try:
        missing = 0
        for _ in range(500):
            if importlib.util.find_spec("rx_race_probe") is None:
                missing += 1
    finally:
        stop.set()
        thread.join()
        sys.path.remove(str(probe_dir))
    assert not loader_errors
    assert missing == 0


def test_concurrent_import_not_recorded_as_rxconfig_dep(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    race_gate: _RaceGate,
    clean_config_modules: None,
):
    """A project-local module imported by another thread mid-load is not evicted.

    Dependency recording used to diff sys.modules around the rxconfig import,
    so a concurrent import from another thread was misattributed to rxconfig
    and evicted from sys.modules on the next config load.

    Args:
        tmp_path: The pytest tmp_path fixture.
        monkeypatch: The pytest monkeypatch fixture.
        race_gate: Handle to pause the load inside rxconfig.py.
        clean_config_modules: Cleanup for modules left behind by the load.
    """
    (tmp_path / "rxconfig.py").write_text(
        textwrap.dedent(
            """
            import _config_race_gate
            import reflex as rx

            _config_race_gate.in_load.set()
            _config_race_gate.release.wait(timeout=5)
            config = rx.Config(app_name="depapp")
            """
        )
    )
    (tmp_path / "side_module.py").write_text("value = 42\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delitem(sys.modules, "side_module", raising=False)

    loader = threading.Thread(target=reflex_base.config._get_config)
    loader.start()
    try:
        assert race_gate.in_load.wait(timeout=5)
        # Import a project-local module from this thread while rxconfig loads.
        import side_module  # noqa: F401  # pyright: ignore[reportMissingImports]
    finally:
        race_gate.release.set()
        loader.join(timeout=5)
    assert not loader.is_alive()

    assert "side_module" not in reflex_base.config._config_module_deps
    # A second load must not evict the concurrently imported module.
    race_gate.release.set()
    reflex_base.config._get_config()
    assert "side_module" in sys.modules


def test_config_deps_recorded_against_load_root_when_rxconfig_chdirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_config_modules: None
):
    """A project-local dep is recorded even when rxconfig.py changes the cwd.

    Dependency classification used to read Path.cwd() after the import rather
    than the root the load started from, so an rxconfig.py that chdir'd made
    its own project-local imports look external. They were then never recorded
    as deps, never evicted, and stayed cached for the next project to inherit.

    Args:
        tmp_path: The pytest tmp_path fixture.
        monkeypatch: The pytest monkeypatch fixture.
        clean_config_modules: Cleanup for modules left behind by the load.
    """
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / "chdir_dep_module.py").write_text("value = 1\n")
    (tmp_path / "rxconfig.py").write_text(
        textwrap.dedent(
            f"""
            import os

            import chdir_dep_module  # noqa: F401
            import reflex as rx

            os.chdir({str(elsewhere)!r})
            config = rx.Config(app_name="chdirapp")
            """
        )
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delitem(sys.modules, "chdir_dep_module", raising=False)

    config = reflex_base.config._get_config()

    assert config.app_name == "chdirapp"
    assert "chdir_dep_module" in reflex_base.config._config_module_deps


def test_record_imports_never_rebinds_meta_path():
    """Recording must mutate sys.meta_path in place, never rebind it.

    Rebinding drops finders another thread inserted while the replacement list
    was being built. reflex.components installs its redirect finder on first
    import, and losing it makes every later reflex.components.* import fail
    with ModuleNotFoundError for the rest of the process.
    """
    meta_path = sys.meta_path
    with reflex_base.config._record_imports():
        assert sys.meta_path is meta_path
    assert sys.meta_path is meta_path


def test_get_config_survives_rxconfig_rebuilding_meta_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_config_modules: None
):
    """A load succeeds even if rxconfig.py rebuilds sys.meta_path.

    The recorder is dropped by the rebuild, so the next load has to reinstall
    it rather than assume it is still there.

    Args:
        tmp_path: The pytest tmp_path fixture.
        monkeypatch: The pytest monkeypatch fixture.
        clean_config_modules: Cleanup for modules left behind by the load.
    """
    (tmp_path / "rxconfig.py").write_text(
        textwrap.dedent(
            """
            import sys
            import reflex as rx
            from reflex_base.config import _import_recorder

            sys.meta_path = [f for f in sys.meta_path if f is not _import_recorder]
            config = rx.Config(app_name="metapathapp")
            """
        )
    )
    monkeypatch.chdir(tmp_path)
    meta_path = sys.meta_path
    contents_before = meta_path.copy()
    try:
        config = reflex_base.config._get_config()
        assert config.app_name == "metapathapp"
        assert reflex_base.config._import_recorder not in sys.meta_path
        # The next load reinstalls the recorder, so deps are recorded again.
        reflex_base.config._get_config()
        assert "rxconfig" in reflex_base.config._config_module_deps
    finally:
        meta_path[:] = contents_before
        sys.meta_path = meta_path


def test_load_config_deprecated(mocker: MockerFixture):
    """_load_config() still loads a config, but warns about the rename.

    Args:
        mocker: The pytest mocker fixture.
    """
    conf = rx.Config(app_name="renamed")
    get_config = mocker.patch.object(
        reflex_base.config, "_get_config", return_value=conf
    )
    deprecate = mocker.patch("reflex_base.utils.console.deprecate")

    assert reflex_base.config._load_config() is conf

    get_config.assert_called_once_with()
    deprecate.assert_called_once()
    assert deprecate.call_args.kwargs["feature_name"] == "_load_config()"


def test_get_config_reload_deprecated(mocker: MockerFixture):
    """get_config(reload=True) reloads the config and warns about deprecation.

    Args:
        mocker: The pytest-mock fixture.
    """
    from reflex_base.registry import RegistrationContext

    deprecate = mocker.patch("reflex_base.utils.console.deprecate")
    first = rx.Config(app_name="first")
    second = rx.Config(app_name="second")
    mocker.patch.object(reflex_base.config, "_get_config", side_effect=[first, second])

    with RegistrationContext():
        assert reflex_base.config.get_config() is first
        deprecate.assert_not_called()
        assert reflex_base.config.get_config(reload=True) is second
        deprecate.assert_called_once()
        assert deprecate.call_args.kwargs["feature_name"] == "get_config(reload=True)"
        # The freshly loaded config stays cached on the context afterwards.
        assert reflex_base.config.get_config() is second
        deprecate.assert_called_once()
