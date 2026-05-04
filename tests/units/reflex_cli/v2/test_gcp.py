from __future__ import annotations

from pathlib import Path
from unittest import mock

import httpx
import pytest
from click.testing import CliRunner
from pytest_mock import MockFixture
from reflex_cli.utils import hosting
from reflex_cli.v2.deployments import hosting_cli
from typer.main import Typer, get_command

hosting_cli = (
    get_command(hosting_cli) if isinstance(hosting_cli, Typer) else hosting_cli
)

runner = CliRunner()

DOCKERFILE = "FROM python:3.13-slim\nWORKDIR /app\n"
DEPLOY_SCRIPT = (
    "#!/usr/bin/env bash\nset -euo pipefail\necho deploying ${SERVICE_NAME}\n"
)
MANIFEST = {"dockerfile": DOCKERFILE, "deploy_command": DEPLOY_SCRIPT}


def _patch_environment(
    mocker: MockFixture, account: str = "user@example.com"
) -> mock.MagicMock:
    """Patch auth + tool detection. Returns the deploy-script subprocess mock."""
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(token="fake-token", validated_data={}),
    )

    def fake_which(name: str) -> str | None:
        return f"/usr/bin/{name}"

    mocker.patch("reflex_cli.v2.gcp.shutil.which", side_effect=fake_which)
    mocker.patch("reflex_cli.v2.gcp._get_active_gcp_account", return_value=account)
    return mocker.patch("reflex_cli.v2.gcp._run_deploy_script", return_value=0)


def _mock_manifest_response(
    mocker: MockFixture, body=MANIFEST, status_code: int = 200
) -> mock.MagicMock:
    response = mock.MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = body
    response.text = "ok"
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "boom", request=mock.MagicMock(), response=response
        )
    else:
        response.raise_for_status.return_value = None
    return mocker.patch("httpx.get", return_value=response)


def test_gcp_deploy_writes_dockerfile_and_runs_script(
    mocker: MockFixture, tmp_path: Path
):
    run_mock = _patch_environment(mocker)
    get_mock = _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        [
            "gcp",
            "deploy",
            "--gcp-project",
            "my-gcp-project",
            "--region",
            "europe-west1",
            "--service-name",
            "myapp",
            "--ar-repo",
            "myrepo",
            "--version",
            "v1",
            "--source",
            str(tmp_path),
        ],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    dockerfile = tmp_path / "Dockerfile"
    assert dockerfile.read_text() == DOCKERFILE
    assert run_mock.call_count == 1
    kwargs = run_mock.call_args.kwargs
    assert kwargs["script"] == DEPLOY_SCRIPT
    assert kwargs["cwd"] == tmp_path.resolve()
    assert kwargs["env_overrides"] == {
        "GCP_PROJECT": "my-gcp-project",
        "GCP_REGION": "europe-west1",
        "SERVICE_NAME": "myapp",
        "AR_REPO": "myrepo",
        "VERSION": "v1",
    }
    # X-API-Token header is sent.
    assert get_mock.call_args.kwargs["headers"] == {"X-API-TOKEN": "fake-token"}


def test_gcp_deploy_aborts_on_no(mocker: MockFixture, tmp_path: Path):
    run_mock = _patch_environment(mocker)
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        ["gcp", "deploy", "--gcp-project", "p", "--source", str(tmp_path)],
        input="n\n",
    )

    assert result.exit_code == 1
    # Dockerfile is still written so the user can run it later.
    assert (tmp_path / "Dockerfile").exists()
    assert run_mock.call_count == 0


def test_gcp_deploy_propagates_script_failure(mocker: MockFixture, tmp_path: Path):
    run_mock = _patch_environment(mocker)
    run_mock.return_value = 7
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        ["gcp", "deploy", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 7


def test_gcp_deploy_dry_run(mocker: MockFixture, tmp_path: Path):
    run_mock = _patch_environment(mocker)
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        [
            "gcp",
            "deploy",
            "--gcp-project",
            "p",
            "--source",
            str(tmp_path),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert run_mock.call_count == 0
    assert not (tmp_path / "Dockerfile").exists()
    assert "Dry run" in result.output


def test_gcp_deploy_prompts_before_overwriting_dockerfile(
    mocker: MockFixture, tmp_path: Path
):
    run_mock = _patch_environment(mocker)
    _mock_manifest_response(mocker)
    existing = tmp_path / "Dockerfile"
    existing.write_text("FROM existing\n")

    # User says no to overwrite -> abort with non-zero.
    result = runner.invoke(
        hosting_cli,
        ["gcp", "deploy", "--gcp-project", "p", "--source", str(tmp_path)],
        input="n\n",
    )

    assert result.exit_code == 1
    assert existing.read_text() == "FROM existing\n"
    assert run_mock.call_count == 0


def test_gcp_deploy_overwrite_flag_skips_prompt(mocker: MockFixture, tmp_path: Path):
    run_mock = _patch_environment(mocker)
    _mock_manifest_response(mocker)
    existing = tmp_path / "Dockerfile"
    existing.write_text("FROM existing\n")

    result = runner.invoke(
        hosting_cli,
        [
            "gcp",
            "deploy",
            "--gcp-project",
            "p",
            "--source",
            str(tmp_path),
            "--overwrite-dockerfile",
        ],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    assert existing.read_text() == DOCKERFILE
    assert run_mock.call_count == 1


def test_gcp_deploy_requires_gcloud(mocker: MockFixture, tmp_path: Path):
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(token="t", validated_data={}),
    )
    mocker.patch(
        "reflex_cli.v2.gcp.shutil.which",
        side_effect=lambda name: None if name == "gcloud" else f"/usr/bin/{name}",
    )

    result = runner.invoke(
        hosting_cli,
        ["gcp", "deploy", "--gcp-project", "p", "--source", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "gcloud" in result.output


def test_gcp_deploy_requires_docker(mocker: MockFixture, tmp_path: Path):
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(token="t", validated_data={}),
    )
    mocker.patch(
        "reflex_cli.v2.gcp.shutil.which",
        side_effect=lambda name: None if name == "docker" else f"/usr/bin/{name}",
    )

    result = runner.invoke(
        hosting_cli,
        ["gcp", "deploy", "--gcp-project", "p", "--source", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "docker" in result.output.lower()


def test_gcp_deploy_requires_gcp_login(mocker: MockFixture, tmp_path: Path):
    _patch_environment(mocker, account="")

    result = runner.invoke(
        hosting_cli,
        ["gcp", "deploy", "--gcp-project", "p", "--source", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "gcloud auth login" in result.output


def test_gcp_deploy_403_mentions_enterprise_tier(mocker: MockFixture, tmp_path: Path):
    _patch_environment(mocker)
    _mock_manifest_response(mocker, body={"detail": "denied"}, status_code=403)

    result = runner.invoke(
        hosting_cli,
        ["gcp", "deploy", "--gcp-project", "p", "--source", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "Enterprise" in result.output


def test_gcp_deploy_rejects_missing_fields(mocker: MockFixture, tmp_path: Path):
    _patch_environment(mocker)
    _mock_manifest_response(mocker, body={"dockerfile": "FROM scratch"})

    result = runner.invoke(
        hosting_cli,
        ["gcp", "deploy", "--gcp-project", "p", "--source", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "deploy_command" in result.output


def test_gcp_deploy_default_version_is_timestamp(mocker: MockFixture, tmp_path: Path):
    run_mock = _patch_environment(mocker)
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        ["gcp", "deploy", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    version = run_mock.call_args.kwargs["env_overrides"]["VERSION"]
    # YYYYMMDD-HHMMSS
    assert len(version) == 15
    assert version[8] == "-"
    assert version.replace("-", "").isdigit()


@pytest.fixture(autouse=True)
def _no_log_level_side_effects(mocker: MockFixture):
    mocker.patch("reflex_cli.utils.console.set_log_level")
