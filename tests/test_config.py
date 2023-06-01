import os
from typing import Dict

import pytest

import pynecone as pc
from pynecone import constants
from pynecone.config import DBConfig


@pytest.fixture
def config_no_db_url_values(base_config_values) -> Dict:
    """Create config values with no db_url.

    Args:
        base_config_values: Base config fixture.

    Returns:
        Config values.
    """
    base_config_values.pop("db_url")
    return base_config_values


@pytest.fixture(autouse=True)
def config_empty_db_url_values(base_config_values):
    """Create config values with empty db_url.

    Args:
        base_config_values: Base config values fixture.

    Yields:
        Config values
    """
    base_config_values["db_url"] = None
    yield base_config_values
    os.environ.pop("DB_URL")


def test_config_db_url(base_config_values):
    """Test defined db_url is not changed.

    Args:
        base_config_values: base_config_values fixture.
    """
    os.environ.pop("DB_URL")
    config = pc.Config(**base_config_values)
    assert config.db_url == base_config_values["db_url"]


def test_default_db_url(config_no_db_url_values):
    """Test that db_url is assigned the default value if not passed.

    Args:
        config_no_db_url_values: Config values with no db_url defined.
    """
    config = pc.Config(**config_no_db_url_values)
    assert config.db_url == constants.DB_URL


def test_empty_db_url(config_empty_db_url_values):
    """Test that db_url is not automatically assigned if an empty value is defined.

    Args:
        config_empty_db_url_values: Config values with empty db_url.
    """
    config = pc.Config(**config_empty_db_url_values)
    assert config.db_url is None


def test_db_url_precedence(base_config_values, sqlite_db_config_values):
    """Test that db_url is not overwritten when db_url is defined.

    Args:
        base_config_values: config values that include db_ur.
        sqlite_db_config_values: DB config values.
    """
    db_config = DBConfig(**sqlite_db_config_values)
    base_config_values["db_config"] = db_config
    config = pc.Config(**base_config_values)
    assert config.db_url == base_config_values["db_url"]


def test_db_url_from_db_config(config_no_db_url_values, sqlite_db_config_values):
    """Test db_url generation from db_config.

    Args:
        config_no_db_url_values: Config values with no db_url.
        sqlite_db_config_values: DB config values.
    """
    db_config = DBConfig(**sqlite_db_config_values)
    config_no_db_url_values["db_config"] = db_config
    config = pc.Config(**config_no_db_url_values)
    assert config.db_url == db_config.get_url()
