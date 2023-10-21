import json
from unittest.mock import Mock, mock_open

import httpx
import pytest

from reflex import constants
from reflex.utils import hosting


def test_get_existing_access_token_and_no_invitation_code(mocker):
    # Config file has token only
    mock_hosting_config = {"access_token": "ejJhfake_token"}
    mocker.patch("builtins.open", mock_open(read_data=json.dumps(mock_hosting_config)))
    token, code = hosting.get_existing_access_token()
    assert token == mock_hosting_config["access_token"]
    assert code is None


def test_get_existing_access_token_and_invitation_code(mocker):
    # Config file has both access token and the invitation code
    mock_hosting_config = {"access_token": "ejJhfake_token", "code": "fake_code"}
    mocker.patch("builtins.open", mock_open(read_data=json.dumps(mock_hosting_config)))
    token, code = hosting.get_existing_access_token()
    assert token == mock_hosting_config["access_token"]
    assert code == mock_hosting_config["code"]


def test_no_existing_access_token(mocker):
    # Config file does not have access token
    mock_hosting_config = {"code": "fake_code"}
    mocker.patch("builtins.open", mock_open(read_data=json.dumps(mock_hosting_config)))
    with pytest.raises(Exception):
        token, _ = hosting.get_existing_access_token()
        assert token is None


def test_no_config_file(mocker):
    # Config file not exist
    mocker.patch("builtins.open", side_effect=FileNotFoundError)
    with pytest.raises(Exception) as ex:
        hosting.get_existing_access_token()
        assert ex.value == "No existing login found"


def test_empty_config_file(mocker):
    # Config file is empty
    mocker.patch("builtins.open", mock_open(read_data=""))
    with pytest.raises(Exception) as ex:
        hosting.get_existing_access_token()
        assert ex.value == "No existing login found"


def test_invalid_json_config_file(mocker):
    # Config file content is not valid json
    mocker.patch("builtins.open", mock_open(read_data="im not json content"))
    with pytest.raises(Exception) as ex:
        hosting.get_existing_access_token()
        assert ex.value == "No existing login found"


def test_validate_token_success(mocker):
    # Valid token passes without raising any exceptions
    mocker.patch("httpx.post")
    hosting.validate_token("fake_token")


def test_invalid_token_access_denied(mocker):
    # Invalid token raises an exception
    mocker.patch("httpx.post", return_value=httpx.Response(403))
    with pytest.raises(ValueError) as ex:
        hosting.validate_token("invalid_token")
        assert ex.value == "access denied"


def test_unable_to_validate_token(mocker):
    # Unable to validate token raises an exception, but not access denied
    mocker.patch("httpx.post", return_value=httpx.Response(500))
    with pytest.raises(Exception):
        hosting.validate_token("invalid_token")


def test_delete_access_token_from_config(mocker):
    config_json = {
        "access_token": "fake_token",
        "code": "fake_code",
        "future": "some value",
    }
    mock_f = mock_open(read_data=json.dumps(config_json))
    mocker.patch("builtins.open", mock_f)
    mocker.patch("os.path.exists", return_value=True)
    mock_json_dump = mocker.patch("json.dump")
    hosting.delete_token_from_config()
    config_json.pop("access_token")
    assert mock_json_dump.call_args[0][0] == config_json


def test_save_access_token_and_invitation_code_to_config(mocker):
    access_token = "fake_token"
    invitation_code = "fake_code"
    expected_config_json = {
        "access_token": access_token,
        "code": invitation_code,
    }
    mocker.patch("builtins.open")
    mock_json_dump = mocker.patch("json.dump")
    hosting.save_token_to_config(access_token, invitation_code)
    assert mock_json_dump.call_args[0][0] == expected_config_json


def test_save_access_code_but_none_invitation_code_to_config(mocker):
    access_token = "fake_token"
    invitation_code = None
    expected_config_json = {
        "access_token": access_token,
        "code": invitation_code,
    }
    mocker.patch("builtins.open")
    mock_json_dump = mocker.patch("json.dump")
    hosting.save_token_to_config(access_token, invitation_code)
    expected_config_json.pop("code")
    assert mock_json_dump.call_args[0][0] == expected_config_json


def test_authenticated_token_success(mocker):
    access_token = "fake_token"
    mocker.patch(
        "reflex.utils.hosting.get_existing_access_token",
        return_value=(access_token, "fake_code"),
    )
    mocker.patch("reflex.utils.hosting.validate_token")
    assert hosting.authenticated_token() == access_token


def test_no_authenticated_token(mocker):
    mocker.patch(
        "reflex.utils.hosting.get_existing_access_token",
        return_value=(None, None),
    )
    assert hosting.authenticated_token() is None


def test_maybe_authenticated_token_is_invalid(mocker):
    mocker.patch(
        "reflex.utils.hosting.get_existing_access_token",
        return_value=("invalid_token", "fake_code"),
    )
    mocker.patch("reflex.utils.hosting.validate_token", side_effect=ValueError)
    mocker.patch("builtins.open")
    mocker.patch("json.load")
    mock_json_dump = mocker.patch("json.dump")
    assert hosting.authenticated_token() is None
    mock_json_dump.assert_called_once()


def test_prepare_deploy_not_authenticated(mocker):
    mocker.patch("reflex.utils.hosting.authenticated_token", return_value=None)
    with pytest.raises(Exception) as ex:
        hosting.prepare_deploy("fake-app")
        assert ex.value == "Not authenticated"


def test_server_unable_to_prepare_deploy(mocker):
    mocker.patch("reflex.utils.hosting.authenticated_token", return_value="fake_token")
    mocker.patch("httpx.post", return_value=httpx.Response(500))
    with pytest.raises(Exception):
        hosting.prepare_deploy("fake-app")


def test_prepare_deploy_success(mocker):
    mocker.patch("reflex.utils.hosting.authenticated_token", return_value="fake_token")
    mocker.patch(
        "httpx.post",
        return_value=Mock(
            status_code=200,
            json=lambda: dict(
                app_prefix="fake-app-prefix",
                reply=dict(
                    key="fake-key",
                    api_url="fake-api-url",
                    deploy_url="fake-deploy-url",
                ),
                suggestion=None,
                existing=[],
            ),
        ),
    )
    # server returns valid response (format is checked by pydantic model validation)
    hosting.prepare_deploy("fake-app")


def test_deploy(mocker):
    mocker.patch("reflex.utils.hosting.authenticated_token", return_value="fake_token")
    mocker.patch("builtins.open")
    mocker.patch(
        "httpx.post",
        return_value=Mock(
            status_code=200,
            json=lambda: dict(
                frontend_url="https://fake-url", backend_url="https://fake-url"
            ),
        ),
    )
    hosting.deploy(
        frontend_file_name="fake-frontend-path",
        backend_file_name="fake-backend-path",
        export_dir="fake-export-dir",
        key="fake-key",
        app_name="fake-app-name",
        regions=["fake-region"],
        app_prefix="fake-app-prefix",
    )


def test_validate_token_with_retries_failed(mocker):
    mock_validate_token = mocker.patch(
        "reflex.utils.hosting.validate_token", side_effect=Exception
    )
    mock_delete_token = mocker.patch("reflex.utils.hosting.delete_token_from_config")
    mocker.patch("time.sleep")

    assert hosting.validate_token_with_retries("fake-token") is False
    assert mock_validate_token.call_count == constants.Hosting.WEB_AUTH_RETRIES
    assert mock_delete_token.call_count == 0


def test_validate_token_access_denied(mocker):
    mock_validate_token = mocker.patch(
        "reflex.utils.hosting.validate_token", side_effect=ValueError
    )
    mock_delete_token = mocker.patch("reflex.utils.hosting.delete_token_from_config")
    mocker.patch("time.sleep")
    with pytest.raises(SystemExit):
        hosting.validate_token_with_retries("fake-token")
    assert mock_validate_token.call_count == 1
    assert mock_delete_token.call_count == 1


def test_validate_token_with_retries_success(mocker):
    validate_token_returns = [Exception, Exception, None]
    mock_validate_token = mocker.patch(
        "reflex.utils.hosting.validate_token", side_effect=validate_token_returns
    )
    mock_delete_token = mocker.patch("reflex.utils.hosting.delete_token_from_config")
    mocker.patch("time.sleep")

    assert hosting.validate_token_with_retries("fake-token") is True
    assert mock_validate_token.call_count == len(validate_token_returns)
    assert mock_delete_token.call_count == 0


@pytest.mark.parametrize(
    "prepare_response, expected",
    [
        (
            hosting.DeploymentPrepareResponse(
                app_prefix="fake-prefix",
                reply=hosting.DeploymentPrepInfo(
                    key="key1", api_url="url11", deploy_url="url12"
                ),
                existing=None,
                suggestion=None,
            ),
            ("key1", "url11", "url12"),
        ),
        (
            hosting.DeploymentPrepareResponse(
                app_prefix="fake-prefix",
                reply=None,
                existing=[
                    hosting.DeploymentPrepInfo(
                        key="key21", api_url="url211", deploy_url="url212"
                    ),
                    hosting.DeploymentPrepInfo(
                        key="key22", api_url="url21", deploy_url="url22"
                    ),
                ],
                suggestion=None,
            ),
            ("key21", "url211", "url212"),
        ),
        (
            hosting.DeploymentPrepareResponse(
                app_prefix="fake-prefix",
                reply=None,
                existing=None,
                suggestion=hosting.DeploymentPrepInfo(
                    key="key31", api_url="url31", deploy_url="url31"
                ),
            ),
            ("key31", "url31", "url31"),
        ),
    ],
)
def test_interactive_get_deployment_key_user_accepts_defaults(
    mocker, prepare_response, expected
):
    mocker.patch("reflex.utils.console.ask", side_effect=[""])
    assert (
        hosting.interactive_get_deployment_key_from_user_input(
            prepare_response, "fake-app"
        )
        == expected
    )


def test_interactive_get_deployment_key_user_input_accepted(mocker):
    mocker.patch("reflex.utils.console.ask", side_effect=["my-site"])
    mocker.patch(
        "reflex.utils.hosting.prepare_deploy",
        return_value=hosting.DeploymentPrepareResponse(
            app_prefix="fake-prefix",
            reply=hosting.DeploymentPrepInfo(
                key="my-site", api_url="url211", deploy_url="url212"
            ),
        ),
    )
    assert hosting.interactive_get_deployment_key_from_user_input(
        hosting.DeploymentPrepareResponse(
            app_prefix="fake-prefix",
            reply=None,
            existing=None,
            suggestion=hosting.DeploymentPrepInfo(
                key="rejected-key", api_url="rejected-url", deploy_url="rejected-url"
            ),
        ),
        "fake-app",
    ) == ("my-site", "url211", "url212")


def test_process_envs():
    assert hosting.process_envs(["a=b", "c=d"]) == {"a": "b", "c": "d"}


@pytest.mark.parametrize(
    "inputs, expected",
    [
        # enters two envs then enter
        (
            ["a", "b", "c", "d", ""],
            ["a=b", "c=d"],
        ),
        # No envs
        ([""], []),
        # enters one env with value, one without, then enter
        (["a", "b", "c", "", ""], ["a=b", "c="]),
    ],
)
def test_interactive_prompt_for_envs(mocker, inputs, expected):
    mocker.patch("reflex.utils.console.ask", side_effect=inputs)
    assert hosting.interactive_prompt_for_envs() == expected
