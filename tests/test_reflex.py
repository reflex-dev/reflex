from functools import reduce
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from reflex.constants.hosting import Hosting
from reflex.reflex import cli
from reflex.utils.hosting import DeploymentPrepInfo

runner = CliRunner()


def test_login_success(mocker):
    mock_get_existing_access_token = mocker.patch(
        "reflex.utils.hosting.get_existing_access_token",
        return_value=("fake-token", "fake-code"),
    )
    mock_validate_token = mocker.patch("reflex.utils.hosting.validate_token")
    result = runner.invoke(cli, ["login"])
    assert result.exit_code == 0
    mock_get_existing_access_token.assert_called_once()
    mock_validate_token.assert_called_once_with("fake-token")


def test_login_existing_token_but_invalid(mocker):
    mocker.patch(
        "reflex.utils.hosting.get_existing_access_token",
        return_value=("fake-token", "fake-code"),
    )
    mock_validate_token = mocker.patch("reflex.utils.hosting.validate_token")
    mocker.patch("os.path.exists", return_value=True)
    mock_delete_token_from_config = mocker.patch(
        "reflex.utils.hosting.delete_token_from_config"
    )
    mock_validate_token.side_effect = ValueError("this message does not matter")
    result = runner.invoke(cli, ["login"])
    assert result.exit_code == 1
    # Make sure the invalid token delete is performed
    mock_delete_token_from_config.assert_called_once()


def test_login_no_existing_token_fetched_valid(mocker):
    # Access token does not exist, but user authenticates successfully on browser.
    mocker.patch(
        "reflex.utils.hosting.get_existing_access_token",
        side_effect=Exception("no token found"),
    )
    mock_webbrowser_open = mocker.patch("webbrowser.open", return_value=True)
    # Token is fetched successfully
    mocker.patch(
        "reflex.utils.hosting.fetch_token", return_value=("fake-token2", "fake-code2")
    )
    mock_validate_token = mocker.patch("reflex.utils.hosting.validate_token")
    mock_save_token_to_config = mocker.patch(
        "reflex.utils.hosting.save_token_to_config"
    )
    result = runner.invoke(cli, ["login"])
    assert result.exit_code == 0
    mock_webbrowser_open.assert_called_once()
    mock_validate_token.assert_called_once_with(
        "fake-token2",
    )
    mock_save_token_to_config.assert_called_once_with("fake-token2", "fake-code2")


def test_login_no_existing_token_fetch_none(mocker):
    # Access token does not exist, but user authenticates successfully on browser.
    mocker.patch(
        "reflex.utils.hosting.get_existing_access_token",
        side_effect=Exception("no token found"),
    )
    mock_webbrowser_open = mocker.patch("webbrowser.open", return_value=True)
    # Token is not fetched
    mock_fetch_token = mocker.patch(
        "reflex.utils.hosting.fetch_token", side_effect=Exception("no token fetched")
    )
    mocker.patch("time.sleep")
    result = runner.invoke(cli, ["login"])
    assert result.exit_code == 1
    mock_webbrowser_open.assert_called_once()
    assert mock_fetch_token.call_count == Hosting.WEB_AUTH_RETRIES


@pytest.mark.parametrize(
    "args",
    [
        ["--no-interactive", "-k", "chatroom"],
        ["--no-interactive", "--deployment-key", "chatroom"],
        ["--no-interactive", "-r", "sjc"],
        ["--no-interactive", "--region", "sjc"],
        ["--no-interactive", "-r", "sjc", "-r", "lax"],
        ["--no-interactive", "-r", "sjc", "--region", "lax"],
    ],
)
def test_deploy_required_args_missing(args):
    result = runner.invoke(cli, ["deploy", *args])
    assert result.exit_code == 1


@pytest.fixture
def setup_env_authentication(mocker):
    mocker.patch("reflex.utils.prerequisites.check_initialized")
    mocker.patch("reflex.utils.hosting.authenticated_token", return_value="fake-token")
    mocker.patch("time.sleep")
    mocker.patch("reflex.utils.hosting.check_requirements_txt_exist")


@pytest.mark.parametrize(
    "optional_args,values",
    [
        ([], None),
        (["--env", "k1=v1"], {"envs": {"k1": "v1"}}),
        (["--cpus", 2], {"cpus": 2}),
        (["--memory-mb", 2048], {"memory_mb": 2048}),
        (["--no-auto-start"], {"auto_start": False}),
        (["--no-auto-stop"], {"auto_stop": False}),
        (
            ["--frontend-hostname", "myfrontend.com"],
            {"frontend_hostname": "myfrontend.com"},
        ),
    ],
)
def test_deploy_non_interactive(
    mocker, setup_env_authentication, optional_args, values
):
    mocker.patch(
        "reflex.utils.hosting.prepare_deploy",
        side_effect=Exception("server did not like params in prepare"),
    )
    result = runner.invoke(
        cli, ["deploy", "--no-interactive", "-k", "chatroom", "-r", "sjc"]
    )
    assert result.exit_code == 1
    app_prefix = "fake-prefix"
    mocker.patch(
        "reflex.utils.hosting.prepare_deploy",
        return_value=Mock(
            app_prefix=app_prefix,
            reply=Mock(
                api_url="fake-api-url", deploy_url="fake-deploy-url", key="fake-key"
            ),
        ),
    )
    mocker.patch("reflex.reflex.export")
    mock_deploy = mocker.patch(
        "reflex.utils.hosting.deploy",
        return_value=Mock(
            frontend_url="fake-frontend-url", backend_url="fake-backend-url"
        ),
    )
    mocker.patch("reflex.utils.hosting.poll_backend", return_value=True)
    mocker.patch("reflex.utils.hosting.poll_frontend", return_value=True)
    mock_cleanup = mocker.patch("reflex.utils.hosting.clean_up")
    # TODO: typer option default not working in test for app name
    deployment_key = "chatroom-0"
    app_name = "chatroom"
    regions = ["sjc"]
    result = runner.invoke(
        cli,
        [
            "deploy",
            "--no-interactive",
            "-k",
            deployment_key,
            *reduce(lambda x, y: x + ["-r", y], regions, []),
            "--app-name",
            app_name,
            *optional_args,
        ],
    )
    assert result.exit_code == 0

    expected_call_args = dict(
        frontend_file_name="frontend.zip",
        backend_file_name="backend.zip",
        key=deployment_key,
        app_name=app_name,
        regions=regions,
        app_prefix=app_prefix,
        cpus=None,
        memory_mb=None,
        auto_start=True,
        auto_stop=True,
        frontend_hostname=None,
        envs=None,
    )
    expected_call_args.update(values or {})
    assert mock_deploy.call_args.kwargs == expected_call_args
    mock_cleanup.assert_called_once()


def get_app_prefix():
    return "fake-prefix"


def get_deployment_key():
    return "i-want-this-site"


def get_suggested_key():
    return "suggested-key"


@pytest.mark.parametrize(
    "app_prefix,deployment_key,prepare_responses,user_inputs,expected_key,args_patch",
    [
        # CLI provides suggestion and but user enters a different key
        (
            get_app_prefix(),
            get_deployment_key(),
            [
                Mock(
                    app_prefix=get_app_prefix(),
                    reply=None,
                    suggestion=Mock(
                        api_url="fake-api-url",
                        deploy_url="fake-deploy-url",
                        key=get_suggested_key(),
                    ),
                    existing=None,
                ),
                Mock(
                    app_prefix=get_app_prefix(),
                    reply=Mock(
                        api_url="fake-api-url",
                        deploy_url="fake-deploy-url",
                        key=get_deployment_key(),
                    ),
                    suggestion=None,
                    existing=None,
                ),
            ],
            [get_deployment_key(), "sjc", ""],
            get_deployment_key(),
            None,
        ),
        # CLI provides suggestion and but user enters a different key and enters envs
        (
            get_app_prefix(),
            get_deployment_key(),
            [
                Mock(
                    app_prefix=get_app_prefix(),
                    reply=None,
                    suggestion=Mock(
                        api_url="fake-api-url",
                        deploy_url="fake-deploy-url",
                        key=get_suggested_key(),
                    ),
                    existing=None,
                ),
                Mock(
                    app_prefix=get_app_prefix(),
                    reply=Mock(
                        api_url="fake-api-url",
                        deploy_url="fake-deploy-url",
                        key=get_deployment_key(),
                    ),
                    suggestion=None,
                    existing=None,
                ),
            ],
            [get_deployment_key(), "sjc", "k1", "v1", "k2", "v2", ""],
            get_deployment_key(),
            {"envs": {"k1": "v1", "k2": "v2"}},
        ),
        # CLI provides suggestion and but user takes it
        (
            get_app_prefix(),
            get_deployment_key(),
            [
                Mock(
                    app_prefix=get_app_prefix(),
                    reply=None,
                    suggestion=Mock(
                        api_url="fake-api-url",
                        deploy_url="fake-deploy-url",
                        key=get_suggested_key(),
                    ),
                    existing=None,
                ),
                Mock(
                    app_prefix=get_app_prefix(),
                    reply=Mock(
                        api_url="fake-api-url",
                        deploy_url="fake-deploy-url",
                        key=get_deployment_key(),
                    ),
                    suggestion=None,
                    existing=None,
                ),
            ],
            ["", "sjc", ""],
            get_suggested_key(),
            None,
        ),
        # CLI provides suggestion and but user takes it and enters envs
        (
            get_app_prefix(),
            get_deployment_key(),
            [
                Mock(
                    app_prefix=get_app_prefix(),
                    reply=None,
                    suggestion=Mock(
                        api_url="fake-api-url",
                        deploy_url="fake-deploy-url",
                        key=get_suggested_key(),
                    ),
                    existing=None,
                ),
                Mock(
                    app_prefix=get_app_prefix(),
                    reply=Mock(
                        api_url="fake-api-url",
                        deploy_url="fake-deploy-url",
                        key=get_deployment_key(),
                    ),
                    suggestion=None,
                    existing=None,
                ),
            ],
            ["", "sjc", "k1", "v1", "k3", "v3", ""],
            get_suggested_key(),
            {"envs": {"k1": "v1", "k3": "v3"}},
        ),
        # User has an existing deployment
        (
            get_app_prefix(),
            get_deployment_key(),
            [
                Mock(
                    app_prefix=get_app_prefix(),
                    reply=None,
                    existing=Mock(
                        __getitem__=lambda _, __: DeploymentPrepInfo(
                            api_url="fake-api-url",
                            deploy_url="fake-deploy-url",
                            key=get_deployment_key(),
                        )
                    ),
                    suggestion=None,
                )
            ],
            ["sjc", ""],
            get_deployment_key(),
            None,
        ),
        # User has an existing deployment then updates the envs
        (
            get_app_prefix(),
            get_deployment_key(),
            [
                Mock(
                    app_prefix=get_app_prefix(),
                    reply=None,
                    existing=Mock(
                        __getitem__=lambda _, __: DeploymentPrepInfo(
                            api_url="fake-api-url",
                            deploy_url="fake-deploy-url",
                            key=get_deployment_key(),
                        )
                    ),
                    suggestion=None,
                )
            ],
            ["sjc", "k4", "v4", ""],
            get_deployment_key(),
            {"envs": {"k4": "v4"}},
        ),
    ],
)
def test_deploy(
    mocker,
    setup_env_authentication,
    app_prefix,
    deployment_key,
    prepare_responses,
    user_inputs,
    expected_key,
    args_patch,
):
    mocker.patch(
        "reflex.utils.hosting.prepare_deploy",
        side_effect=Exception("server did not like params in prepare"),
    )
    result = runner.invoke(cli, ["deploy"])
    assert result.exit_code == 1

    mocker.patch(
        "reflex.utils.hosting.prepare_deploy",
        side_effect=prepare_responses,
    )
    mocker.patch("reflex.utils.console.ask", side_effect=user_inputs)
    mocker.patch("reflex.reflex.export")
    mock_deploy = mocker.patch(
        "reflex.utils.hosting.deploy",
        return_value=Mock(
            frontend_url="fake-frontend-url", backend_url="fake-backend-url"
        ),
    )
    mocker.patch("reflex.utils.hosting.poll_backend", return_value=True)
    mocker.patch("reflex.utils.hosting.poll_frontend", return_value=True)
    mock_cleanup = mocker.patch("reflex.utils.hosting.clean_up")
    # TODO: typer option default not working in test for app name
    app_name = "fake-app-workaround"
    regions = ["sjc"]
    result = runner.invoke(
        cli,
        ["deploy", "--app-name", app_name],
    )
    assert result.exit_code == 0

    expected_call_args = dict(
        frontend_file_name="frontend.zip",
        backend_file_name="backend.zip",
        key=expected_key,
        app_name=app_name,
        regions=regions,
        app_prefix=app_prefix,
        cpus=None,
        memory_mb=None,
        auto_start=True,
        auto_stop=True,
        frontend_hostname=None,
        envs=None,
    )
    expected_call_args.update(args_patch or {})

    assert mock_deploy.call_args.kwargs == expected_call_args
    mock_cleanup.assert_called_once()
