from __future__ import annotations

import os
import subprocess
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

# Realistic Dockerfile shape: the multi-line `reflex export` RUN is what needs
# the Reflex access token (reflex-enterprise refuses to export without one).
EXPORT_RUN = (
    "RUN uv run reflex export --frontend-only \\\n"
    "    && mkdir -p .web/_static \\\n"
    "    && unzip -oq frontend.zip -d .web/_static \\\n"
    "    && rm frontend.zip\n"
)
DOCKERFILE = f'FROM python:3.13-slim\nWORKDIR /app\n{EXPORT_RUN}CMD ["run"]\n'
# A realistic-shaped Reflex deploy script — the rewrite logic targets the
# `gcloud builds submit ... .` block in here.
DEPLOY_SCRIPT = (
    "#!/usr/bin/env bash\n"
    "set -euo pipefail\n"
    'IMAGE="us-central1-docker.pkg.dev/${GCP_PROJECT}/reflex/${SERVICE_NAME}:${VERSION}"\n'
    "AUTH=${CLOUD_RUN_ALLOW_UNAUTHENTICATED:-true}\n"
    "gcloud builds submit \\\n"
    '    --tag "${IMAGE}" \\\n'
    '    --project "${GCP_PROJECT}" \\\n'
    "    .\n"
    'gcloud run deploy "${SERVICE_NAME}" --image "${IMAGE}"\n'
)
MANIFEST = {"dockerfile": DOCKERFILE, "deploy_command": DEPLOY_SCRIPT}
STAGED_VERSION = "projects/my-gcp-project/secrets/reflex-access-token/versions/4"


def _patch_gcloud(
    mocker: MockFixture,
    failures: tuple[str, ...] = (),
    secret_exists: bool = True,
    create_fails_once: bool = False,
) -> list[tuple[list[str], str | None]]:
    """Patch `_run_gcloud`, recording every invocation.

    Args:
        mocker: The pytest-mock fixture.
        failures: gcloud subcommands (matched as a prefix of the args) to fail.
        secret_exists: Whether `gcloud secrets describe` finds the secret.
        create_fails_once: Whether the first `gcloud secrets create` fails, as it
            does when the Secret Manager API isn't enabled on the project yet.

    Returns:
        The list `(args, stdin)` tuples are appended to, in call order.
    """
    calls: list[tuple[list[str], str | None]] = []
    creates = 0

    def fake_run(
        gcloud_path: str,
        args: list[str],
        input_text: str | None = None,
        timeout: int = 30,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal creates
        calls.append((list(args), input_text))
        if any(" ".join(args).startswith(failure) for failure in failures):
            return subprocess.CompletedProcess(args, 1, "", "gcloud said no")
        if args[:2] == ["secrets", "describe"] and not secret_exists:
            return subprocess.CompletedProcess(args, 1, "", "NOT_FOUND")
        if args[:2] == ["secrets", "create"]:
            creates += 1
            if create_fails_once and creates == 1:
                return subprocess.CompletedProcess(
                    args, 1, "", "FAILED_PRECONDITION: API has not been used"
                )
        stdout = ""
        if args[:3] == ["secrets", "versions", "add"]:
            stdout = STAGED_VERSION + "\n"
        elif args[:2] == ["projects", "describe"]:
            stdout = "123456789\n"
        return subprocess.CompletedProcess(args, 0, stdout, "")

    mocker.patch("reflex_cli.v2.gcp._run_gcloud", side_effect=fake_run)
    return calls


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
    _patch_gcloud(mocker)
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
    # Each Dockerfile line shows up in the YAML (indented under the literal
    # block); the `reflex export` RUN gains the token secret mount.
    for line in DOCKERFILE.splitlines():
        if line.startswith("RUN "):
            continue
        assert f"      {line}" in yaml
    assert (
        "      RUN --mount=type=secret,id=reflex_access_token,mode=0444 \\\n"
        "          if [ -s /run/secrets/reflex_access_token ]; then export "
        'REFLEX_ACCESS_TOKEN="$$(cat /run/secrets/reflex_access_token)"; fi; \\\n'
        "          uv run reflex export --frontend-only \\\n"
    ) in yaml
    assert (
        "docker build --secret id=reflex_access_token,"
        'src=/tmp/reflex-access-token -t "$_IMAGE" .' in yaml
    )
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


def test_gcp_deploy_stages_token_in_secret_manager(mocker: MockFixture, tmp_path: Path):
    """The access token reaches the build through Secret Manager, then is destroyed.

    Cloud Build only reads secrets from Secret Manager: a value inlined in the
    build config or passed via --substitutions would stay readable in the
    build's metadata afterwards. The staged version is destroyed once the deploy
    finishes so the token isn't left behind in the user's project.
    """
    captured: dict = {}

    run_mock = _patch_environment(mocker)
    calls = _patch_gcloud(mocker)
    _mock_manifest_response(mocker)

    def capture(**kwargs):
        cloudbuild_path = Path(kwargs["env_overrides"]["REFLEX_CLOUDBUILD_YAML"])
        captured["cloudbuild_yaml"] = cloudbuild_path.read_text()
        # The version must still exist while the build runs.
        captured["calls_during_run"] = [args for args, _ in calls]
        return 0

    run_mock.side_effect = capture

    result = runner.invoke(
        hosting_cli,
        [
            "deploy",
            "--gcp",
            "--gcp-project",
            "my-gcp-project",
            "--source",
            str(tmp_path),
        ],
        input="y\n",
    )

    assert result.exit_code == 0, result.output

    # The secret is created, written from stdin, and shared with Cloud Build.
    assert calls[0][0][:3] == ["secrets", "describe", "reflex-access-token"]
    add_args, add_stdin = next(
        call for call in calls if call[0][:3] == ["secrets", "versions", "add"]
    )
    assert "--data-file=-" in add_args
    # The token goes over stdin, never in argv (visible to other processes).
    assert add_stdin == "fake-token"
    assert all("fake-token" not in " ".join(args) for args, _ in calls)
    bindings = [
        args for args, _ in calls if args[:2] == ["secrets", "add-iam-policy-binding"]
    ]
    members = [arg for args in bindings for arg in args if arg.startswith("--member=")]
    assert members == [
        "--member=serviceAccount:123456789@cloudbuild.gserviceaccount.com",
        "--member=serviceAccount:123456789-compute@developer.gserviceaccount.com",
    ]
    assert all("--role=roles/secretmanager.secretAccessor" in args for args in bindings)

    # cloudbuild.yaml references the version by name and never carries the value.
    yaml = captured["cloudbuild_yaml"]
    assert (
        f"    - versionName: {STAGED_VERSION}\n      env: REFLEX_ACCESS_TOKEN" in yaml
    )
    assert "  secretEnv:\n    - REFLEX_ACCESS_TOKEN\n" in yaml
    assert "  env:\n    - DOCKER_BUILDKIT=1\n" in yaml
    assert "printf '%s' \"$$REFLEX_ACCESS_TOKEN\" > /tmp/reflex-access-token" in yaml
    assert "rm -f /tmp/reflex-access-token" in yaml
    assert "fake-token" not in yaml

    # The version is destroyed only after the build, and only that version.
    assert not [
        args
        for args in captured["calls_during_run"]
        if args[:3] == ["secrets", "versions", "destroy"]
    ]
    assert calls[-1][0] == [
        "secrets",
        "versions",
        "destroy",
        "4",
        "--secret=reflex-access-token",
        "--project",
        "my-gcp-project",
        "--quiet",
    ]


def test_gcp_deploy_no_build_token_skips_secret_manager(
    mocker: MockFixture, tmp_path: Path
):
    """--no-build-token leaves Secret Manager and the Dockerfile alone."""
    captured: dict = {}

    run_mock = _patch_environment(mocker)
    calls = _patch_gcloud(mocker)
    _mock_manifest_response(mocker)

    def capture(**kwargs):
        path = Path(kwargs["env_overrides"]["REFLEX_CLOUDBUILD_YAML"])
        captured["cloudbuild_yaml"] = path.read_text()
        return 0

    run_mock.side_effect = capture

    result = runner.invoke(
        hosting_cli,
        [
            "deploy",
            "--gcp",
            "--gcp-project",
            "p",
            "--source",
            str(tmp_path),
            "--no-build-token",
        ],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    assert not [args for args, _ in calls if args[0] == "secrets"]
    yaml = captured["cloudbuild_yaml"]
    assert "availableSecrets" not in yaml
    assert "secretEnv" not in yaml
    assert "--mount=type=secret" not in yaml
    assert 'docker build -t "$_IMAGE" .' in yaml


@pytest.mark.parametrize(
    "failures",
    [
        # Nothing about Secret Manager is permitted.
        ("secrets create", "services enable"),
        # The API enables, but the secret still can't be created.
        ("secrets create",),
        # The secret exists, but no version can be added to it.
        ("secrets versions add",),
    ],
)
def test_gcp_deploy_builds_without_token_when_staging_fails(
    mocker: MockFixture, tmp_path: Path, failures: tuple[str, ...]
):
    """A project the deployer can't write secrets to still deploys, with a warning.

    Only apps using reflex-enterprise need the token, so a missing Secret
    Manager permission shouldn't block a deploy that would otherwise work.
    """
    captured: dict = {}

    run_mock = _patch_environment(mocker)
    calls = _patch_gcloud(
        mocker,
        failures=failures,
        secret_exists="secrets versions add" in failures,
    )
    _mock_manifest_response(mocker)

    def capture(**kwargs):
        path = Path(kwargs["env_overrides"]["REFLEX_CLOUDBUILD_YAML"])
        captured["cloudbuild_yaml"] = path.read_text()
        return 0

    run_mock.side_effect = capture

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    assert "reflex-enterprise" in result.output
    # Nothing was stored, so nothing is destroyed either.
    assert not [
        args for args, _ in calls if args[:3] == ["secrets", "versions", "destroy"]
    ]
    # The build falls back to the plain config rather than mounting a secret
    # that isn't there.
    yaml = captured["cloudbuild_yaml"]
    assert "availableSecrets" not in yaml
    assert "--mount=type=secret" not in yaml


def test_gcp_deploy_creates_missing_secret(mocker: MockFixture, tmp_path: Path):
    """A project without the secret yet gets it created, then written to."""
    _patch_environment(mocker)
    calls = _patch_gcloud(mocker, secret_exists=False)
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    assert [args[:3] for args, _ in calls][:3] == [
        ["secrets", "describe", "reflex-access-token"],
        ["secrets", "create", "reflex-access-token"],
        ["secrets", "versions", "add"],
    ]


def test_gcp_deploy_creates_secret_after_enabling_api(
    mocker: MockFixture, tmp_path: Path
):
    """A first deploy creates the secret, enabling the API if that's what blocked it."""
    run_mock = _patch_environment(mocker)
    calls = _patch_gcloud(mocker, secret_exists=False, create_fails_once=True)
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    subcommands = [" ".join(args[:2]) for args, _ in calls]
    # create -> enable the API -> create again -> store the token.
    assert subcommands[:4] == [
        "secrets describe",
        "secrets create",
        "services enable",
        "secrets create",
    ]
    assert ["secrets", "versions", "add"] in [args[:3] for args, _ in calls]
    assert "--replication-policy=automatic" in calls[1][0]
    assert "--labels=managed-by=reflex-cli" in calls[1][0]
    assert run_mock.call_count == 1


def test_gcp_deploy_reuses_existing_secret(mocker: MockFixture, tmp_path: Path):
    """When the secret already exists, no create (or API enable) is attempted."""
    _patch_environment(mocker)
    calls = _patch_gcloud(mocker)
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    subcommands = [" ".join(args[:2]) for args, _ in calls]
    assert "secrets create" not in subcommands
    assert "services enable" not in subcommands


def test_gcp_deploy_user_managed_token_secret(mocker: MockFixture, tmp_path: Path):
    """A full version resource is referenced as-is; the CLI writes nothing."""
    captured: dict = {}
    version = "projects/other/secrets/my-reflex-token/versions/2"

    run_mock = _patch_environment(mocker)
    calls = _patch_gcloud(mocker)
    _mock_manifest_response(mocker)

    def capture(**kwargs):
        path = Path(kwargs["env_overrides"]["REFLEX_CLOUDBUILD_YAML"])
        captured["cloudbuild_yaml"] = path.read_text()
        return 0

    run_mock.side_effect = capture

    result = runner.invoke(
        hosting_cli,
        [
            "deploy",
            "--gcp",
            "--gcp-project",
            "p",
            "--source",
            str(tmp_path),
            "--token-secret",
            version,
        ],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    assert not [args for args, _ in calls if args[0] in ("secrets", "services")]
    assert f"    - versionName: {version}" in captured["cloudbuild_yaml"]
    assert "--mount=type=secret,id=reflex_access_token" in captured["cloudbuild_yaml"]


@pytest.mark.parametrize(
    "value",
    [
        "projects/p/secrets/s",
        "projects/p/secrets/s/versions",
        "secrets/s/versions/1",
        "bad name",
        "",
    ],
)
def test_gcp_deploy_rejects_malformed_token_secret(
    mocker: MockFixture, tmp_path: Path, value: str
):
    """A typo'd --token-secret fails at the CLI, not mid-deploy inside gcloud."""
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
            "--token-secret",
            value,
        ],
    )

    assert result.exit_code == 2
    assert "--token-secret" in result.output
    assert run_mock.call_count == 0


def test_gcp_deploy_warns_when_dockerfile_has_no_export_step(
    mocker: MockFixture, tmp_path: Path
):
    """If Reflex's Dockerfile stops running `reflex export`, say so loudly.

    Silently skipping would reproduce the original failure — the export dying on
    a missing token — with nothing pointing at the cause.
    """
    run_mock = _patch_environment(mocker)
    calls = _patch_gcloud(mocker)
    _mock_manifest_response(
        mocker,
        body={
            "dockerfile": "FROM python:3.13-slim\nRUN uv sync --frozen\n",
            "deploy_command": DEPLOY_SCRIPT,
        },
    )

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    assert "reflex export" in result.output
    assert "reflex-enterprise" in result.output
    assert not [args for args, _ in calls if args[0] == "secrets"]
    assert run_mock.call_count == 1


def test_gcp_deploy_destroys_staged_version_when_script_fails(
    mocker: MockFixture, tmp_path: Path
):
    """A failed deploy still cleans up the staged token."""
    run_mock = _patch_environment(mocker)
    run_mock.return_value = 7
    calls = _patch_gcloud(mocker)
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 7
    assert calls[-1][0][:3] == ["secrets", "versions", "destroy"]


@pytest.mark.parametrize(
    "failures", [("secrets add-iam-policy-binding",), ("projects describe",)]
)
def test_gcp_deploy_warns_but_continues_when_iam_grant_fails(
    mocker: MockFixture, tmp_path: Path, failures: tuple[str, ...]
):
    """An ungrantable secret still deploys: the build SA may already have access."""
    captured: dict = {}

    run_mock = _patch_environment(mocker)
    calls = _patch_gcloud(mocker, failures=failures)
    _mock_manifest_response(mocker)

    def capture(**kwargs):
        path = Path(kwargs["env_overrides"]["REFLEX_CLOUDBUILD_YAML"])
        captured["cloudbuild_yaml"] = path.read_text()
        return 0

    run_mock.side_effect = capture

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    # The secret is still wired up, and still cleaned up.
    assert f"versionName: {STAGED_VERSION}" in captured["cloudbuild_yaml"]
    assert calls[-1][0][:3] == ["secrets", "versions", "destroy"]


def test_gcp_deploy_warns_with_cleanup_command_when_destroy_fails(
    mocker: MockFixture, tmp_path: Path
):
    """If the staged version can't be destroyed, say how to remove it by hand."""
    _patch_environment(mocker)
    _patch_gcloud(mocker, failures=("secrets versions destroy",))
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    assert "gcloud secrets versions destroy 4" in " ".join(result.output.split())


def test_gcp_deploy_dry_run_stages_nothing(mocker: MockFixture, tmp_path: Path):
    """--dry-run previews the secret wiring without touching the project."""
    _patch_environment(mocker)
    calls = _patch_gcloud(mocker)
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
    assert not calls
    assert "availableSecrets" in result.output
    # The version doesn't exist yet, so the preview stands in for it.
    assert "versions/NEW" in result.output
    assert "--mount=type=secret,id=reflex_access_token" in result.output


def test_gcp_deploy_forwards_resource_flags(mocker: MockFixture, tmp_path: Path):
    """--cpu / --memory / --min-instances flow through to the deploy script env."""
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
            "--cpu",
            "4",
            "--memory",
            "2Gi",
            "--min-instances",
            "0",
        ],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    env_overrides = run_mock.call_args.kwargs["env_overrides"]
    assert env_overrides["CLOUD_RUN_CPU"] == "4"
    assert env_overrides["CLOUD_RUN_MEMORY"] == "2Gi"
    assert env_overrides["CLOUD_RUN_MIN_INSTANCES"] == "0"


def test_gcp_deploy_resource_flags_have_defaults(mocker: MockFixture, tmp_path: Path):
    """When the user omits the new flags, defaults reach the deploy script env."""
    run_mock = _patch_environment(mocker)
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    env_overrides = run_mock.call_args.kwargs["env_overrides"]
    assert env_overrides["CLOUD_RUN_CPU"] == "1"
    assert env_overrides["CLOUD_RUN_MEMORY"] == "1Gi"
    assert env_overrides["CLOUD_RUN_MIN_INSTANCES"] == "1"


def test_gcp_deploy_forwards_max_instances(mocker: MockFixture, tmp_path: Path):
    """--max-instances threads through to CLOUD_RUN_MAX_INSTANCES."""
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
            "--max-instances",
            "42",
        ],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    env_overrides = run_mock.call_args.kwargs["env_overrides"]
    assert env_overrides["CLOUD_RUN_MAX_INSTANCES"] == "42"


def test_gcp_deploy_max_instances_default(mocker: MockFixture, tmp_path: Path):
    """Default --max-instances is 100, matching Cloud Run's own default."""
    run_mock = _patch_environment(mocker)
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    env_overrides = run_mock.call_args.kwargs["env_overrides"]
    assert env_overrides["CLOUD_RUN_MAX_INSTANCES"] == "100"


def test_gcp_deploy_rejects_max_less_than_min(mocker: MockFixture, tmp_path: Path):
    """--max-instances < --min-instances is caught at the CLI, not inside gcloud."""
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
            "--min-instances",
            "5",
            "--max-instances",
            "3",
        ],
    )

    assert result.exit_code == 2
    assert "max-instances" in result.output.lower()
    assert "min-instances" in result.output.lower()
    assert run_mock.call_count == 0


def test_gcp_deploy_allow_unauthenticated_defaults_true(
    mocker: MockFixture, tmp_path: Path
):
    """Default is --allow-unauthenticated (public service), matching prior behavior."""
    run_mock = _patch_environment(mocker)
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    env_overrides = run_mock.call_args.kwargs["env_overrides"]
    assert env_overrides["CLOUD_RUN_ALLOW_UNAUTHENTICATED"] == "true"


def test_gcp_deploy_no_allow_unauthenticated_requires_backend_support(
    mocker: MockFixture, tmp_path: Path
):
    """--no-allow-unauthenticated aborts when the fetched script doesn't honor it.

    The deploy script's auth flag is read from CLOUD_RUN_ALLOW_UNAUTHENTICATED.
    If we shipped a CLI build against an older backend that still hard-codes
    --allow-unauthenticated, the user's --no-allow-unauthenticated would be
    silently ignored and the service would deploy as PUBLIC. Catch the
    mismatch at the CLI before we deploy anything.
    """
    run_mock = _patch_environment(mocker)
    # Manifest from an older backend that doesn't reference the env var —
    # built from scratch so it doesn't inherit DEPLOY_SCRIPT's auth env var.
    legacy_script = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'IMAGE="us-central1-docker.pkg.dev/${GCP_PROJECT}/reflex/${SERVICE_NAME}:${VERSION}"\n'
        "gcloud builds submit \\\n"
        '    --tag "${IMAGE}" \\\n'
        '    --project "${GCP_PROJECT}" \\\n'
        "    .\n"
        'gcloud run deploy "${SERVICE_NAME}" --image "${IMAGE}" --allow-unauthenticated\n'
    )
    _mock_manifest_response(
        mocker, body={"dockerfile": DOCKERFILE, "deploy_command": legacy_script}
    )

    result = runner.invoke(
        hosting_cli,
        [
            "deploy",
            "--gcp",
            "--gcp-project",
            "p",
            "--source",
            str(tmp_path),
            "--no-allow-unauthenticated",
        ],
    )

    assert result.exit_code == 1
    assert "CLOUD_RUN_ALLOW_UNAUTHENTICATED" in result.output
    assert "PUBLIC" in result.output
    assert run_mock.call_count == 0


def test_gcp_deploy_no_allow_unauthenticated(mocker: MockFixture, tmp_path: Path):
    """--no-allow-unauthenticated produces the 'false' value."""
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
            "--no-allow-unauthenticated",
        ],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    env_overrides = run_mock.call_args.kwargs["env_overrides"]
    assert env_overrides["CLOUD_RUN_ALLOW_UNAUTHENTICATED"] == "false"


def test_gcp_deploy_no_env_vars_means_no_env_vars_file(
    mocker: MockFixture, tmp_path: Path
):
    """Without --env or --envfile, REFLEX_ENV_VARS_FILE is absent from env_overrides."""
    run_mock = _patch_environment(mocker)
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    env_overrides = run_mock.call_args.kwargs["env_overrides"]
    assert "REFLEX_ENV_VARS_FILE" not in env_overrides


def test_gcp_deploy_forwards_env_flag(mocker: MockFixture, tmp_path: Path):
    """--env KEY=VALUE writes a tempfile and forwards its path via REFLEX_ENV_VARS_FILE.

    Captures the file's contents during the run (the tempfile is unlinked
    afterward) and verifies the YAML body uses json-encoded values.
    """
    captured: dict = {}

    def capture(**kwargs):
        path = Path(kwargs["env_overrides"]["REFLEX_ENV_VARS_FILE"])
        captured["existed_during_run"] = path.exists()
        captured["path"] = path
        captured["yaml"] = path.read_text()
        return 0

    run_mock = _patch_environment(mocker)
    run_mock.side_effect = capture
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
            "--env",
            "DB_URL=postgres://u:p@h/d",
            "--env",
            "FEATURE_FLAG=on",
        ],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    assert captured["existed_during_run"]
    assert not captured["path"].exists()  # cleaned up after run
    # YAML uses json.dumps per value, so embedded special chars are escaped.
    assert captured["yaml"] == 'DB_URL: "postgres://u:p@h/d"\nFEATURE_FLAG: "on"\n'


def test_gcp_deploy_envfile_loads_dotenv(mocker: MockFixture, tmp_path: Path):
    """--envfile reads a .env file via dotenv_values and forwards its contents."""
    envfile = tmp_path / ".env"
    envfile.write_text('DB_URL="postgres://u:p@h/d"\nFEATURE_FLAG=on\n')

    captured: dict = {}

    def capture(**kwargs):
        path = Path(kwargs["env_overrides"]["REFLEX_ENV_VARS_FILE"])
        captured["yaml"] = path.read_text()
        return 0

    run_mock = _patch_environment(mocker)
    run_mock.side_effect = capture
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
            "--envfile",
            str(envfile),
        ],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    yaml = captured["yaml"]
    assert 'DB_URL: "postgres://u:p@h/d"' in yaml
    assert 'FEATURE_FLAG: "on"' in yaml


def test_gcp_deploy_envfile_takes_precedence_over_env_with_warning(
    mocker: MockFixture, tmp_path: Path
):
    """When both --envfile and --env are passed, --envfile wins (matches existing flow)."""
    envfile = tmp_path / ".env"
    envfile.write_text("FROM_FILE=yes\n")

    captured: dict = {}

    def capture(**kwargs):
        path = Path(kwargs["env_overrides"]["REFLEX_ENV_VARS_FILE"])
        captured["yaml"] = path.read_text()
        return 0

    run_mock = _patch_environment(mocker)
    run_mock.side_effect = capture
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
            "--envfile",
            str(envfile),
            "--env",
            "FROM_FLAG=no",
        ],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    assert "FROM_FILE" in captured["yaml"]
    assert "FROM_FLAG" not in captured["yaml"]
    assert "envfile" in result.output.lower()
    assert "ignoring --env" in result.output


def test_format_env_vars_yaml_escapes_specials():
    """Values with quotes, backslashes, and newlines round-trip via json.dumps."""
    from reflex_cli.v2 import gcp as gcp_module

    envs = {
        "QUOTED": 'has "quotes" and \\ backslash',
        "MULTILINE": "line1\nline2",
        "EMPTY": "",
    }
    yaml = gcp_module._format_env_vars_yaml(envs)
    # Each line is `KEY: <json-encoded-value>`.
    assert 'QUOTED: "has \\"quotes\\" and \\\\ backslash"' in yaml
    assert 'MULTILINE: "line1\\nline2"' in yaml
    assert 'EMPTY: ""' in yaml


def test_gcp_deploy_forwards_service_account(mocker: MockFixture, tmp_path: Path):
    """--service-account threads through to CLOUD_RUN_SERVICE_ACCOUNT."""
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
            "--service-account",
            "my-sa@p.iam.gserviceaccount.com",
        ],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    env_overrides = run_mock.call_args.kwargs["env_overrides"]
    assert (
        env_overrides["CLOUD_RUN_SERVICE_ACCOUNT"] == "my-sa@p.iam.gserviceaccount.com"
    )


def test_gcp_deploy_omits_service_account_when_unset(
    mocker: MockFixture, tmp_path: Path
):
    """Without --service-account, CLOUD_RUN_SERVICE_ACCOUNT is not in env_overrides.

    The deploy script defaults it to empty, so Cloud Run falls back to the
    project's default compute SA. Leaving the key out of env_overrides (rather
    than sending an empty string) keeps the dry-run output tidy.
    """
    run_mock = _patch_environment(mocker)
    _mock_manifest_response(mocker)

    result = runner.invoke(
        hosting_cli,
        ["deploy", "--gcp", "--gcp-project", "p", "--source", str(tmp_path)],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    env_overrides = run_mock.call_args.kwargs["env_overrides"]
    assert "CLOUD_RUN_SERVICE_ACCOUNT" not in env_overrides


def test_gcp_deploy_rejects_empty_service_account(mocker: MockFixture, tmp_path: Path):
    """An explicit --service-account "" errors instead of silently falling back.

    A common footgun is `--service-account "$VAR"` in CI where VAR is unset; the
    flag would otherwise resolve to the default compute SA against user intent.
    """
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
            "--service-account",
            "",
        ],
        input="y\n",
    )

    assert result.exit_code == 2
    run_mock.assert_not_called()


def test_gcp_deploy_rejects_negative_min_instances(mocker: MockFixture, tmp_path: Path):
    """--min-instances is IntRange(min=0); negative values fail at the CLI layer."""
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
            "--min-instances",
            "-1",
        ],
    )

    assert result.exit_code == 2
    assert "min-instances" in result.output.lower()
    assert run_mock.call_count == 0


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
    # Secret Manager calls go through _run_gcloud, which subprocess.run is
    # stubbed out from under; the deploy script's env is what's under test here.
    _patch_gcloud(mocker)
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


def test_inject_token_secret_mount_rewrites_the_export_run():
    """The export RUN gets a secret mount; every other instruction is untouched."""
    from reflex_cli.v2 import gcp as gcp_module

    dockerfile = (
        "FROM python:3.13-slim\n"
        "RUN uv sync --frozen\n"
        "  RUN uv run reflex export --frontend-only \\\n"
        "      && unzip -oq frontend.zip -d .web/_static\n"
        'CMD ["uv", "run", "reflex", "run"]\n'
    )

    injected = gcp_module._inject_token_secret_mount(dockerfile)

    assert injected == (
        "FROM python:3.13-slim\n"
        "RUN uv sync --frozen\n"
        # Original indentation is preserved.
        "  RUN --mount=type=secret,id=reflex_access_token,mode=0444 \\\n"
        "      if [ -s /run/secrets/reflex_access_token ]; then export "
        'REFLEX_ACCESS_TOKEN="$(cat /run/secrets/reflex_access_token)"; fi; \\\n'
        "      uv run reflex export --frontend-only \\\n"
        "      && unzip -oq frontend.zip -d .web/_static\n"
        'CMD ["uv", "run", "reflex", "run"]\n'
    )


def test_inject_token_secret_mount_matches_lowercase_run():
    """Dockerfile instructions are case-insensitive, so `run` counts too."""
    from reflex_cli.v2 import gcp as gcp_module

    injected = gcp_module._inject_token_secret_mount(
        "FROM python:3.13-slim\nrun uv run reflex export --frontend-only\n"
    )

    assert injected is not None
    assert injected.endswith(
        "RUN --mount=type=secret,id=reflex_access_token,mode=0444 \\\n"
        "    if [ -s /run/secrets/reflex_access_token ]; then export "
        'REFLEX_ACCESS_TOKEN="$(cat /run/secrets/reflex_access_token)"; fi; \\\n'
        "    uv run reflex export --frontend-only\n"
    )


def test_inject_token_secret_mount_without_export_step():
    """No `reflex export` means nothing consumes a token, so none is staged."""
    from reflex_cli.v2 import gcp as gcp_module

    assert (
        gcp_module._inject_token_secret_mount(
            "FROM python:3.13-slim\nRUN uv sync --frozen\n"
        )
        is None
    )


def test_inject_token_secret_mount_keeps_dockerfile_that_declares_the_mount():
    """A Dockerfile that already mounts the secret is passed through unchanged."""
    from reflex_cli.v2 import gcp as gcp_module

    dockerfile = (
        "FROM python:3.13-slim\n"
        "RUN --mount=type=secret,id=reflex_access_token \\\n"
        "    uv run reflex export --frontend-only\n"
    )

    assert gcp_module._inject_token_secret_mount(dockerfile) == dockerfile


def test_build_cloudbuild_yaml_without_token_secret_is_unchanged():
    """No secret version means no BuildKit flags, env, or availableSecrets block."""
    from reflex_cli.v2 import gcp as gcp_module

    yaml = gcp_module._build_cloudbuild_yaml("FROM python:3.13-slim\n")

    assert "availableSecrets" not in yaml
    assert "secretEnv" not in yaml
    assert "DOCKER_BUILDKIT" not in yaml
    assert 'docker build -t "$_IMAGE" .' in yaml
    # A failing build reports the build's error instead of a confusing push error.
    assert yaml.count("      set -e\n") == 1


def test_build_cloudbuild_yaml_keeps_token_out_of_the_config():
    """Only the secret's resource name is embedded, and `$` stays escaped.

    Cloud Build stores the build config and its substitutions in the Build
    resource, readable by anyone with roles/cloudbuild.builds.viewer, so the
    token value must never be part of it.
    """
    from reflex_cli.v2 import gcp as gcp_module

    version = "projects/p/secrets/reflex-access-token/versions/9"
    yaml = gcp_module._build_cloudbuild_yaml(
        "FROM python:3.13-slim\n", token_secret_version=version
    )

    assert yaml.endswith(
        "availableSecrets:\n"
        "  secretManager:\n"
        f"    - versionName: {version}\n"
        "      env: REFLEX_ACCESS_TOKEN\n"
    )
    assert (
        "  env:\n    - DOCKER_BUILDKIT=1\n  secretEnv:\n    - REFLEX_ACCESS_TOKEN\n"
        in yaml
    )
    # `$$` survives Cloud Build's substitution pass as a literal `$`; a single
    # `$REFLEX_ACCESS_TOKEN` would be rejected as an unknown substitution.
    assert (
        "      printf '%s' \"$$REFLEX_ACCESS_TOKEN\" > /tmp/reflex-access-token\n"
        in yaml
    )
    assert (
        "      docker build --secret id=reflex_access_token,"
        'src=/tmp/reflex-access-token -t "$_IMAGE" .\n' in yaml
    )
    assert "      rm -f /tmp/reflex-access-token\n" in yaml
    # The staging path sits outside /workspace, so it can't reach the build
    # context (and from there a `COPY . .` layer).
    assert gcp_module.TOKEN_SECRET_STAGE_PATH.startswith("/tmp/")


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
