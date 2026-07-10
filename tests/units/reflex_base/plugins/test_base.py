"""Tests for plugin base helpers."""

import pytest
from pytest_mock import MockerFixture
from reflex_base.plugins import Plugin, get_plugin
from reflex_base.utils.exceptions import ConfigError


class ConfiguredPlugin(Plugin):
    """Plugin type configured by the tests."""


class ConfiguredSubPlugin(ConfiguredPlugin):
    """Configured plugin subtype."""


class MissingPlugin(Plugin):
    """Plugin type absent from the test configuration."""


def _configure(mocker: MockerFixture, *plugins: Plugin) -> None:
    """Install a config containing the given plugins.

    Args:
        mocker: The pytest-mock fixture.
        plugins: Plugin instances to configure.
    """
    config = mocker.Mock(plugins=plugins)
    mocker.patch("reflex_base.config.get_config", return_value=config)


def test_get_plugin_returns_configured_instance(mocker: MockerFixture):
    """The configured instance is returned by its type."""
    plugin = ConfiguredPlugin()
    _configure(mocker, plugin)

    assert get_plugin(ConfiguredPlugin) is plugin


def test_get_plugin_returns_none_when_missing(mocker: MockerFixture):
    """An absent plugin type resolves to None."""
    _configure(mocker, ConfiguredPlugin())

    assert get_plugin(MissingPlugin) is None


def test_get_plugin_matches_subclasses(mocker: MockerFixture):
    """A subclass instance satisfies a base-plugin lookup."""
    plugin = ConfiguredSubPlugin()
    _configure(mocker, plugin)

    assert get_plugin(ConfiguredPlugin) is plugin


def test_get_plugin_rejects_ambiguous_matches(mocker: MockerFixture):
    """Multiple matching plugins raise instead of depending on list order."""
    _configure(mocker, ConfiguredPlugin(), ConfiguredSubPlugin())

    with pytest.raises(ConfigError, match="Multiple ConfiguredPlugin instances"):
        get_plugin(ConfiguredPlugin)


def test_register_route_default_is_noop():
    """The base route hook accepts the staged context and contributes nothing."""
    assert (
        Plugin().register_route(
            app_type=object,  # pyright: ignore[reportArgumentType]
            add_page=lambda *args, **kwargs: None,
            has_app_page=lambda route: False,
        )
        is None
    )
