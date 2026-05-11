from __future__ import annotations

import os
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
# A realistic-shaped Reflex deploy script — the rewrite logic targets the
# `gcloud builds submit ... .` block in here.
DEPLOY_SCRIPT = (
    "#!/usr/bin/env bash\n"
    "set -euo pipefail\n"
    'IMAGE="us-central1-docker.pkg.dev/${GCP_PROJECT}/reflex/${SERVICE_NAME}:${VERSION}"\n'
    "gcloud builds submit \\\n"
    '    --tag "${IMAGE}" \\\n'
    '    --project "${GCP_PROJECT}" \\\n'
    "    .\n"
    'gcloud run deploy "${SERVICE_NAME}" --image "${IMAGE}"\n'
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


def test_gcp_deploy_runs_script_from_source_with_cloudbuild_yaml(
    mocker: MockFixture, tmp_path: Path
):
    """Happy path: script runs with cwd=source, REFLEX_CLOUDBUILD_YAML points at a
    tempfile that contains the generated cloudbuild.yaml, the script is rewritten
    to use --config=, and the source tree is never written to.
    """
    captured: dict = {}

    def capture(**kwargs):
        cloudbuild_path = Path(kwargs["env_overrides"]["REFLEX_CLOUDBUILD_YAML"])
        captured["cloudbuild_existed_during_run"] = cloudbuild_path.exists()
        captured["cloudbuild_path"] = cloudbuild_path
        captured["cloudbuild_yaml"] = cloudbuild_path.read_text()
        captured["script"] = kwargs["script"]
        captured["cwd"] = Path(kwargs["cwd"])
        captured["env_overrides"] = kwargs["env_overrides"]
        return 0

    run_mock = _patch_environment(mocker)
    run_mock.side_effect = capture
    get_mock = _mock_manifest_response(mocker)

    # Pre-populate the source with a file and an existing Dockerfile that
    # must NOT be touched.
    (tmp_path / "app.py").write_text("print('hi')\n")
    (tmp_path / "Dockerfile").write_text("FROM existing\n")

    result = runner.invoke(
        hosting_cli,
        [
            "deploy",
            "--gcp",
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
    # Source tree is untouched.
    assert (tmp_path / "Dockerfile").read_text() == "FROM existing\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Dockerfile", "app.py"]

    # cwd is the user's source dir — no temp build context.
    assert captured["cwd"] == tmp_path.resolve()

    # cloudbuild.yaml existed during the run and is removed after.
    assert captured["cloudbuild_existed_during_run"]
    assert not captured["cloudbuild_path"].exists()

    # cloudbuild.yaml embeds the Reflex Dockerfile via heredoc and builds/pushes.
    yaml = captured["cloudbuild_yaml"]
    assert "cat > Dockerfile <<'REFLEX_DOCKERFILE_EOF'" in yaml
    # Each Dockerfile line shows up in the YAML (indented under the literal block).
    for line in DOCKERFILE.splitlines():
        assert f"      {line}" in yaml
    assert 'docker build -t "$_IMAGE" .' in yaml
    assert 'docker push "$_IMAGE"' in yaml
    assert "images:" in yaml

    # The script's `gcloud builds submit --tag X .` was rewritten to --config=.
    script = captured["script"]
    assert "--tag" not in script
    assert '--config="${REFLEX_CLOUDBUILD_YAML}"' in script
    assert '--substitutions=_IMAGE="${IMAGE}"' in script
    # Surrounding lines (run deploy etc.) are preserved.
    assert 'gcloud run deploy "${SERVICE_NAME}"' in script

    assert captured["env_overrides"]["GCP_PROJECT"] == "my-gcp-project"
    assert captured["env_overrides"]["GCP_REGION"] == "europe-west1"
    assert captured["env_overrides"]["SERVICE_NAME"] == "myapp"
    assert captured["env_overrides"]["AR_REPO"] == "myrepo"
    assert captured["env_overrides"]["VERSION"] == "v1"

    assert run_mock.call_count == 1
    # X-API-Token header is sent.
    assert get_mock.call_args.kwargs["headers"] == {"X-API-TOKEN": "fake-token"}


def test_gcp_deploy_aborts_on_no(mocker: MockFixture, tmp_path: Path):
    """Declining the run prompt aborts before any staging."""
    run_mock = _patch_environment(mocker)
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="n\n",
    )

    assert result.exit_code == 1
    # Nothing was written into the source tree.
    assert not (tmp_path / "Dockerfile").exists()
    assert run_mock.call_count == 0


def test_gcp_deploy_propagates_script_failure(mocker: MockFixture, tmp_path: Path):
    run_mock = _patch_environment(mocker)
    run_mock.return_value = 7
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 7


def test_gcp_deploy_dry_run(mocker: MockFixture, tmp_path: Path):
    run_mock = _patch_environment(mocker)
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        [
            "deploy",
            "--gcp",
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


def test_gcp_deploy_existing_dockerfile_in_source_is_preserved(
    mocker: MockFixture, tmp_path: Path
):
    """An existing Dockerfile in --source is never read or modified."""
    run_mock = _patch_environment(mocker)
    _mock_manifest_response(mocker)
    existing = tmp_path / "Dockerfile"
    existing.write_text("FROM existing\n")

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    assert existing.read_text() == "FROM existing\n"
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
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
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
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "docker" in result.output.lower()


def test_gcp_deploy_requires_gcp_login(mocker: MockFixture, tmp_path: Path):
    _patch_environment(mocker, account="")

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "gcloud auth login" in result.output


def test_gcp_deploy_403_mentions_enterprise_tier(mocker: MockFixture, tmp_path: Path):
    _patch_environment(mocker)
    _mock_manifest_response(mocker, body={"detail": "denied"}, status_code=403)

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "Enterprise" in result.output


def test_gcp_deploy_rejects_missing_fields(mocker: MockFixture, tmp_path: Path):
    _patch_environment(mocker)
    _mock_manifest_response(mocker, body={"dockerfile": "FROM scratch"})

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "deploy_command" in result.output


def test_gcp_deploy_default_version_is_timestamp(mocker: MockFixture, tmp_path: Path):
    run_mock = _patch_environment(mocker)
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    version = run_mock.call_args.kwargs["env_overrides"]["VERSION"]
    # YYYYMMDD-HHMMSS
    assert len(version) == 15
    assert version[8] == "-"
    assert version.replace("-", "").isdigit()


def test_gcp_deploy_no_interactive_skips_run_prompt(
    mocker: MockFixture, tmp_path: Path
):
    run_mock = _patch_environment(mocker)
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        [
            "deploy",
            "--gcp",
            "--gcp-project",
            "p",
            "--source",
            str(tmp_path),
            "--no-interactive",
            "--token",
            "fake-token",
        ],
    )

    assert result.exit_code == 0, result.output
    # Source tree was not modified.
    assert not (tmp_path / "Dockerfile").exists()
    assert run_mock.call_count == 1


def test_gcp_deploy_env_is_restricted_to_allowlist(mocker: MockFixture, tmp_path: Path):
    """Verify the script env excludes host secrets and only includes allowlisted vars."""
    from reflex_cli.v2 import gcp as gcp_module

    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        return_value=hosting.AuthenticatedClient(token="fake-token", validated_data={}),
    )
    mocker.patch(
        "reflex_cli.v2.gcp.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"
    )
    mocker.patch(
        "reflex_cli.v2.gcp._get_active_gcp_account", return_value="u@example.com"
    )
    _mock_manifest_response(mocker)

    captured: dict[str, dict[str, str]] = {}

    def fake_run(*args, **kwargs):
        captured["env"] = kwargs["env"]
        return mock.MagicMock(returncode=0)

    mocker.patch("reflex_cli.v2.gcp.subprocess.run", side_effect=fake_run)
    mocker.patch.dict(
        os.environ,
        {
            "PATH": "/usr/bin",
            "HOME": "/home/test",
            "AWS_SECRET_ACCESS_KEY": "should-not-leak",
            "GITHUB_TOKEN": "also-secret",
            "DOCKER_HOST": "unix:///var/run/docker.sock",
            "MY_RANDOM_VAR": "should-not-leak",
        },
        clear=True,
    )

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    env = captured["env"]
    # Allowlisted host vars are forwarded.
    assert env["PATH"] == "/usr/bin"
    assert env["HOME"] == "/home/test"
    assert env["DOCKER_HOST"] == "unix:///var/run/docker.sock"
    # Deploy overrides are present.
    assert env[gcp_module.ENV_GCP_PROJECT] == "p"
    # Host secrets are NOT forwarded.
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "GITHUB_TOKEN" not in env
    assert "MY_RANDOM_VAR" not in env


def test_deploy_requires_gcp_target_flag(tmp_path: Path):
    """Without any target flag, the command errors with usage hint."""
    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp-project", "p", "--source", str(tmp_path)],
    )

    assert result.exit_code == 2
    assert "--gcp" in result.output


def test_build_cloudbuild_yaml_embeds_dockerfile_via_heredoc():
    r"""The cloudbuild.yaml writes the Dockerfile via a single-quoted heredoc.

    The single-quoted marker means bash treats `/\ in the Dockerfile body
    literally; `$` is doubled to `$$` so Cloud Build's substitution pass
    over `args` doesn't grab Dockerfile variables. YAML literal-block indent
    (6 spaces) gets stripped uniformly so the closing marker ends up at
    column 0.
    """
    from reflex_cli.v2 import gcp as gcp_module

    # Dockerfile with the kinds of `$`/`${...}` Cloud Build would otherwise
    # try to substitute, plus shell-meta chars that break naive quoting.
    dockerfile = (
        "FROM python:3.13-slim\n"
        'ENV PATH="${UV_PROJECT_ENVIRONMENT}/bin:$PATH"\n'
        "RUN echo $weird '\"chars\"' \\\nthings\n"
    )
    yaml = gcp_module._build_cloudbuild_yaml(dockerfile)

    # Heredoc opens and closes with the same single-quoted marker.
    assert "cat > Dockerfile <<'REFLEX_DOCKERFILE_EOF'" in yaml
    assert yaml.count("REFLEX_DOCKERFILE_EOF") == 2

    # Inside the heredoc body, every literal `$` from the Dockerfile is doubled
    # to escape Cloud Build's substitution pass. Slice out the heredoc body and
    # verify no bare `$` survives there.
    open_marker = "cat > Dockerfile <<'REFLEX_DOCKERFILE_EOF'\n"
    close_marker = "      REFLEX_DOCKERFILE_EOF\n"
    body_start = yaml.index(open_marker) + len(open_marker)
    body_end = yaml.index(close_marker)
    heredoc_body = yaml[body_start:body_end]
    # Every `$` in the heredoc body is part of a `$$` pair — i.e. no isolated `$`.
    assert "$" in heredoc_body  # sanity
    assert heredoc_body.replace("$$", "").count("$") == 0
    # Concrete escapes are present.
    assert '      ENV PATH="$${UV_PROJECT_ENVIRONMENT}/bin:$$PATH"' in heredoc_body
    assert "      RUN echo $$weird '\"chars\"' \\" in heredoc_body

    # Non-`$` Dockerfile lines pass through verbatim (with 6-space indent).
    assert "      FROM python:3.13-slim" in yaml
    assert "      things" in yaml

    # Build + push lines use the `_IMAGE` substitution (single `$`).
    assert 'docker build -t "$_IMAGE" .' in yaml
    assert 'docker push "$_IMAGE"' in yaml
    assert "images:\n  - $_IMAGE\n" in yaml


def test_build_cloudbuild_yaml_rejects_marker_collision():
    """If the Dockerfile happens to contain the heredoc marker as a whole line, error."""
    from reflex_cli.v2 import gcp as gcp_module

    dockerfile = "FROM scratch\nREFLEX_DOCKERFILE_EOF\nCMD true\n"
    with pytest.raises(ValueError, match="heredoc marker"):
        gcp_module._build_cloudbuild_yaml(dockerfile)


def test_rewrite_builds_submit_replaces_tag_form_with_config():
    """The rewrite consumes the full multi-line `gcloud builds submit ... .`."""
    from reflex_cli.v2 import gcp as gcp_module

    original = (
        "set -e\n"
        "gcloud builds submit \\\n"
        '    --tag "${IMAGE}" \\\n'
        '    --project "${GCP_PROJECT}" \\\n'
        "    .\n"
        'gcloud run deploy "${SERVICE_NAME}"\n'
    )

    rewritten = gcp_module._rewrite_builds_submit(original)

    assert "--tag" not in rewritten
    assert '--config="${REFLEX_CLOUDBUILD_YAML}"' in rewritten
    assert '--substitutions=_IMAGE="${IMAGE}"' in rewritten
    # Lines outside the rewritten block are preserved.
    assert rewritten.startswith("set -e\n")
    assert rewritten.endswith('gcloud run deploy "${SERVICE_NAME}"\n')


def test_rewrite_builds_submit_errors_if_pattern_missing():
    """Without a `gcloud builds submit` line, we fail loudly so the CLI surfaces it."""
    from reflex_cli.v2 import gcp as gcp_module

    with pytest.raises(ValueError, match="gcloud builds submit"):
        gcp_module._rewrite_builds_submit("echo nothing here\n")


def test_gcp_deploy_surfaces_rewrite_failure(mocker: MockFixture, tmp_path: Path):
    """If the manifest's script can't be rewritten, the command errors out clearly."""
    _patch_environment(mocker)
    _mock_manifest_response(
        mocker,
        body={
            "dockerfile": DOCKERFILE,
            "deploy_command": "#!/usr/bin/env bash\necho no build here\n",
        },
    )

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "gcloud builds submit" in result.output


def test_deploy_gcp_requires_gcp_project(mocker: MockFixture, tmp_path: Path):
    """With --gcp set but --gcp-project missing, errors before any auth/manifest call."""
    auth_mock = mocker.patch("reflex_cli.utils.hosting.get_authenticated_client")
    get_mock = mocker.patch("httpx.get")

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--source", str(tmp_path)],
    )

    assert result.exit_code == 2
    assert "--gcp-project" in result.output
    assert auth_mock.call_count == 0
    assert get_mock.call_count == 0


@pytest.fixture(autouse=True)
def _no_log_level_side_effects(mocker: MockFixture):
    mocker.patch("reflex_cli.utils.console.set_log_level")
