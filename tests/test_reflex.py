from functools import reduce
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from reflex.reflex import cli
from reflex.utils.hosting import DeploymentPrepInfo

runner = CliRunner()


def test_login_success_existing_token(mocker):
    mocker.patch(
        "reflex.utils.hosting.authenticated_token",
        return_value=("fake-token", "fake-code"),
    )
    result = runner.invoke(cli, ["login"])
    assert result.exit_code == 0


def test_login_success_on_browser(mocker):
    mocker.patch(
        "reflex.utils.hosting.authenticated_token",
        return_value=("", "fake-code"),
    )
    mock_authenticate_on_browser = mocker.patch(
        "reflex.utils.hosting.authenticate_on_browser", return_value="fake-token"
    )
    result = runner.invoke(cli, ["login"])
    assert result.exit_code == 0
    mock_authenticate_on_browser.assert_called_once_with("fake-code")


def test_login_fail(mocker):
    # Access token does not exist, but user authenticates successfully on browser.
    mocker.patch(
        "reflex.utils.hosting.get_existing_access_token", return_value=("", "")
    )
    mocker.patch("reflex.utils.hosting.authenticate_on_browser", return_value="")
    result = runner.invoke(cli, ["login"])
    assert result.exit_code == 1


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


def test_deploy_non_interactive_prepare_failed(
    mocker,
    setup_env_authentication,
):
    mocker.patch(
        "reflex.utils.hosting.prepare_deploy",
        side_effect=Exception("server did not like params in prepare"),
    )
    result = runner.invoke(
        cli, ["deploy", "--no-interactive", "-k", "chatroom", "-r", "sjc"]
    )
    assert result.exit_code == 1


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
def test_deploy_non_interactive_success(
    mocker, setup_env_authentication, optional_args, values
):
    mocker.patch("reflex.utils.console.ask")
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
    fake_export_dir = "fake-export-dir"
    mocker.patch("tempfile.mkdtemp", return_value=fake_export_dir)
    mocker.patch("reflex.reflex.export")
    mock_deploy = mocker.patch(
        "reflex.utils.hosting.deploy",
        return_value=Mock(
            frontend_url="fake-frontend-url", backend_url="fake-backend-url"
        ),
    )
    mocker.patch("reflex.utils.hosting.wait_for_server_to_pick_up_request")
    mocker.patch("reflex.utils.hosting.display_deploy_milestones")
    mocker.patch("reflex.utils.hosting.poll_backend", return_value=True)
    mocker.patch("reflex.utils.hosting.poll_frontend", return_value=True)
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
        export_dir=fake_export_dir,
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
        with_metrics=None,
        with_tracing=None,
    )
    expected_call_args.update(values or {})
    assert mock_deploy.call_args.kwargs == expected_call_args


def get_app_prefix():
    return "fake-prefix"


def get_deployment_key():
    return "i-want-this-site"


def get_suggested_key():
    return "suggested-key"


def test_deploy_interactive_prepare_failed(
    mocker,
    setup_env_authentication,
):
    mocker.patch(
        "reflex.utils.hosting.prepare_deploy",
        side_effect=Exception("server did not like params in prepare"),
    )
    result = runner.invoke(cli, ["deploy"])
    assert result.exit_code == 1


@pytest.mark.parametrize(
    "app_prefix,deployment_key,prepare_responses,user_input_region,user_input_envs,expected_key,args_patch",
    [
        # CLI provides suggestion and but user enters a different key
        (
            get_app_prefix(),
            get_deployment_key(),
            Mock(
                app_prefix=get_app_prefix(),
                reply=None,
                suggestion=Mock(
                    api_url="fake-api-url",
                    deploy_url="fake-deploy-url",
                    key=get_suggested_key(),
                ),
                existing=None,
                enabled_regions=["sjc"],
            ),
            ["sjc"],
            [],
            get_deployment_key(),
            None,
        ),
        # CLI provides suggestion and but user enters a different key and enters envs
        (
            get_app_prefix(),
            get_deployment_key(),
            Mock(
                app_prefix=get_app_prefix(),
                reply=None,
                suggestion=Mock(
                    api_url="fake-api-url",
                    deploy_url="fake-deploy-url",
                    key=get_suggested_key(),
                ),
                existing=None,
                enabled_regions=["sjc"],
            ),
            ["sjc"],
            ["k1=v1", "k2=v2"],
            get_deployment_key(),
            {"envs": {"k1": "v1", "k2": "v2"}},
        ),
        # CLI provides suggestion and but user takes it
        (
            get_app_prefix(),
            get_deployment_key(),
            Mock(
                app_prefix=get_app_prefix(),
                reply=None,
                suggestion=Mock(
                    api_url="fake-api-url",
                    deploy_url="fake-deploy-url",
                    key=get_suggested_key(),
                ),
                existing=None,
                enabled_regions=["sjc"],
            ),
            ["sjc"],
            [],
            get_suggested_key(),
            None,
        ),
        # CLI provides suggestion and but user takes it and enters envs
        (
            get_app_prefix(),
            get_deployment_key(),
            Mock(
                app_prefix=get_app_prefix(),
                reply=None,
                suggestion=Mock(
                    api_url="fake-api-url",
                    deploy_url="fake-deploy-url",
                    key=get_suggested_key(),
                ),
                existing=None,
                enabled_regions=["sjc"],
            ),
            ["sjc"],
            ["k1=v1", "k3=v3"],
            get_suggested_key(),
            {"envs": {"k1": "v1", "k3": "v3"}},
        ),
        # User has an existing deployment
        (
            get_app_prefix(),
            get_deployment_key(),
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
                enabled_regions=["sjc"],
            ),
            ["sjc"],
            [],
            get_deployment_key(),
            None,
        ),
        # User has an existing deployment then updates the envs
        (
            get_app_prefix(),
            get_deployment_key(),
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
                enabled_regions=["sjc"],
            ),
            ["sjc"],
            ["k4=v4"],
            get_deployment_key(),
            {"envs": {"k4": "v4"}},
        ),
    ],
)
def test_deploy_interactive(
    mocker,
    setup_env_authentication,
    app_prefix,
    deployment_key,
    prepare_responses,
    user_input_region,
    user_input_envs,
    expected_key,
    args_patch,
):
    mocker.patch(
        "reflex.utils.hosting.check_requirements_for_non_reflex_packages",
        return_value=True,
    )
    mocker.patch(
        "reflex.utils.hosting.prepare_deploy",
        return_value=prepare_responses,
    )
    mocker.patch(
        "reflex.utils.hosting.interactive_get_deployment_key_from_user_input",
        return_value=(expected_key, "fake-api-url", "fake-deploy-url"),
    )
    mocker.patch("reflex.utils.console.ask", side_effect=user_input_region)
    mocker.patch(
        "reflex.utils.hosting.interactive_prompt_for_envs", return_value=user_input_envs
    )
    fake_export_dir = "fake-export-dir"
    mocker.patch("tempfile.mkdtemp", return_value=fake_export_dir)
    mocker.patch("reflex.reflex.export")
    mock_deploy = mocker.patch(
        "reflex.utils.hosting.deploy",
        return_value=Mock(
            frontend_url="fake-frontend-url", backend_url="fake-backend-url"
        ),
    )
    mocker.patch("reflex.utils.hosting.wait_for_server_to_pick_up_request")
    mocker.patch("reflex.utils.hosting.display_deploy_milestones")
    mocker.patch("reflex.utils.hosting.poll_backend", return_value=True)
    mocker.patch("reflex.utils.hosting.poll_frontend", return_value=True)

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
        export_dir=fake_export_dir,
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
        with_metrics=None,
        with_tracing=None,
    )
    expected_call_args.update(args_patch or {})

    assert mock_deploy.call_args.kwargs == expected_call_args
