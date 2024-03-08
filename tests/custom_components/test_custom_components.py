from unittest.mock import mock_open

import pytest

from reflex.custom_components.custom_components import _get_version_to_publish


@pytest.mark.parametrize(
    "version_string",
    [
        "version='0.1.0'",
        "version ='0.1.0'",
        "version= '0.1.0'",
        "version = '0.1.0'",
        "version  =   '0.1.0' ",
        'version="0.1.0"',
        'version ="0.1.0"',
        'version = "0.1.0"',
        'version   =    "0.1.0" ',
    ],
)
def test_get_version_to_publish(version_string, mocker):
    python_toml = f"""[tool.poetry]
name = \"test\"
{version_string}
description = \"test\"
"""
    open_mock = mock_open(read_data=python_toml)
    mocker.patch("builtins.open", open_mock)
    assert _get_version_to_publish() == "0.1.0"
