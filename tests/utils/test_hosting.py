import json
from unittest.mock import mock_open

import pytest

from reflex.utils import hosting


def test_get_existing_access_token(mocker):
    # Config file has token only
    mock_hosting_config = {"access_token": "ejJhfake_token"}
    mocker.patch("builtins.open", mock_open(read_data=json.dumps(mock_hosting_config)))
    token, code = hosting.get_existing_access_token()
    assert token == mock_hosting_config["access_token"]
    assert code is None
    # Config file has both access token and the invitation code
    mock_hosting_config = {"access_token": "ejJhfake_token", "code": "fake_code"}
    mocker.patch("builtins.open", mock_open(read_data=json.dumps(mock_hosting_config)))
    token, code = hosting.get_existing_access_token()
    assert token == mock_hosting_config["access_token"]
    assert code == mock_hosting_config["code"]

    # Config file does not have access token
    mock_hosting_config = {"code": "fake_code"}
    mocker.patch("builtins.open", mock_open(read_data=json.dumps(mock_hosting_config)))
    with pytest.raises(Exception) as ex:
        token, code = hosting.get_existing_access_token()
        assert token is None

    # Config file not exist
    mocker.patch("builtins.open", side_effect=FileNotFoundError)
    with pytest.raises(Exception) as ex:
        hosting.get_existing_access_token()
        assert ex.value == "No existing login found"

    # Config file is empty
    mocker.patch("builtins.open", mock_open(read_data=""))
    with pytest.raises(Exception) as ex:
        hosting.get_existing_access_token()
        assert ex.value == "No existing login found"

    # Config file content is not valid json
    mocker.patch("builtins.open", mock_open(read_data="im not json content"))
    with pytest.raises(Exception) as ex:
        hosting.get_existing_access_token()
        assert ex.value == "No existing login found"


def test_validate_token():
    pass


def test_authenticated_token():
    pass


def test_prepare_deploy():
    pass


def test_deploy():
    pass


def test_list_deployments():
    pass


def test_get_deployment_status():
    pass
