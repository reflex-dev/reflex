"""GCP Cloud Run deploy commands for the Reflex Cloud CLI.

Fetches a Dockerfile + bash deploy script from Reflex and runs the script
against the user's source directory. The Dockerfile is materialized inside
a Cloud Build job (via a ``cloudbuild.yaml`` written to a tempfile and
referenced with ``gcloud builds submit --config=...``) — the user's project
tree is never modified. The script reads its parameters from environment
variables (GCP_PROJECT, GCP_REGION, SERVICE_NAME, AR_REPO, VERSION,
CLOUD_RUN_CPU, CLOUD_RUN_MEMORY, CLOUD_RUN_MIN_INSTANCES,
CLOUD_RUN_MAX_INSTANCES, CLOUD_RUN_ALLOW_UNAUTHENTICATED,
CLOUD_RUN_SERVICE_ACCOUNT, REFLEX_CLOUDBUILD_YAML,
REFLEX_ENV_VARS_FILE).

The image build runs ``reflex export``, which refuses to run for apps that
use ``reflex-enterprise`` unless a Reflex access token is available. The
token is handed to the build through Secret Manager (referenced by resource
name from the build config, never inlined into it) and mounted into the
``docker build`` as a BuildKit secret, so it stays out of the build metadata,
the build logs, and the pushed image's layers and history.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import click

from reflex_cli import constants
from reflex_cli.utils import console

GCP_MANIFEST_ENDPOINT = "/api/v1/cli/gcp-cloud-run-manifest"

DOCKERFILE_NAME = "Dockerfile"

# Environment variables passed to the deploy script.
ENV_GCP_PROJECT = "GCP_PROJECT"
ENV_GCP_REGION = "GCP_REGION"
ENV_SERVICE_NAME = "SERVICE_NAME"
ENV_AR_REPO = "AR_REPO"
ENV_VERSION = "VERSION"
ENV_CPU = "CLOUD_RUN_CPU"
ENV_MEMORY = "CLOUD_RUN_MEMORY"
ENV_MIN_INSTANCES = "CLOUD_RUN_MIN_INSTANCES"
ENV_MAX_INSTANCES = "CLOUD_RUN_MAX_INSTANCES"
ENV_ALLOW_UNAUTHENTICATED = "CLOUD_RUN_ALLOW_UNAUTHENTICATED"
ENV_SERVICE_ACCOUNT = "CLOUD_RUN_SERVICE_ACCOUNT"
# Path to the Cloud Build config file written by the CLI. The rewritten
# deploy script references it as ``--config="${REFLEX_CLOUDBUILD_YAML}"``.
ENV_REFLEX_CLOUDBUILD_YAML = "REFLEX_CLOUDBUILD_YAML"
# Path to a YAML file with user-supplied env vars. When set, the deploy
# script passes it to ``gcloud run deploy --env-vars-file=...``.
ENV_REFLEX_ENV_VARS_FILE = "REFLEX_ENV_VARS_FILE"

# Env var `reflex export` reads the Reflex access token from, both in the
# Cloud Build step (populated from Secret Manager) and inside the image build.
ENV_REFLEX_ACCESS_TOKEN = "REFLEX_ACCESS_TOKEN"
# BuildKit secret id and the path it is mounted at inside the image build.
TOKEN_SECRET_ID = "reflex_access_token"
TOKEN_SECRET_MOUNT_PATH = f"/run/secrets/{TOKEN_SECRET_ID}"
# Where the build step stages the token for `docker build --secret src=`.
# Outside /workspace so it is never part of the docker build context.
TOKEN_SECRET_STAGE_PATH = "/tmp/reflex-access-token"
# Default Secret Manager secret the token is staged in.
DEFAULT_TOKEN_SECRET_NAME = "reflex-access-token"
# Applied to secrets this CLI creates, so they're identifiable in the project.
TOKEN_SECRET_LABEL = "managed-by=reflex-cli"
SECRETMANAGER_SERVICE = "secretmanager.googleapis.com"
SECRET_ACCESSOR_ROLE = "roles/secretmanager.secretAccessor"

# Pattern for the start of the `gcloud builds submit` invocation in the
# Reflex deploy script. We rewrite that whole multi-line command to use
# `--config=` so the Dockerfile lives inside a cloudbuild.yaml instead of
# being staged on disk next to the user's source.
_BUILDS_SUBMIT_PATTERN = re.compile(
    r"(?P<indent>^[ \t]*)gcloud[ \t]+builds[ \t]+submit\b",
    re.MULTILINE,
)

# A whole `RUN` instruction in the Reflex Dockerfile, backslash continuations
# included, so the one that runs `reflex export` can be given the token secret.
# Dockerfile instructions are case-insensitive.
_RUN_INSTRUCTION_PATTERN = re.compile(
    r"^(?P<indent>[ \t]*)RUN[ \t]+(?P<body>(?:[^\n]*\\\r?\n)*[^\n]*)",
    re.MULTILINE | re.IGNORECASE,
)
# The command that needs the Reflex access token.
_REFLEX_EXPORT_PATTERN = re.compile(r"\breflex[ \t]+export\b")

# `--token-secret` accepts a bare secret name or a full version resource.
_SECRET_NAME_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,255}")
_SECRET_VERSION_PATTERN = re.compile(
    r"projects/[^/\s]+/secrets/[A-Za-z0-9_-]{1,255}/versions/[A-Za-z0-9_-]+"
)

# Manifest response field names from Reflex.
FIELD_DOCKERFILE = "dockerfile"
FIELD_DEPLOY_COMMAND = "deploy_command"

# Allowlist of host environment variables forwarded to the deploy script.
# We deliberately exclude things like AWS_*/GITHUB_TOKEN/SSH agent sockets so a
# compromised or tampered manifest cannot exfiltrate unrelated credentials.
DEPLOY_ENV_ALLOWLIST = frozenset({
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "TERM",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TMPDIR",
    "TEMP",
    "TMP",
    "XDG_CONFIG_HOME",
    # gcloud configuration
    "CLOUDSDK_CONFIG",
    "CLOUDSDK_ACTIVE_CONFIG_NAME",
    "CLOUDSDK_CORE_PROJECT",
    "CLOUDSDK_CORE_ACCOUNT",
    "CLOUDSDK_AUTH_ACCESS_TOKEN_FILE",
    "GOOGLE_APPLICATION_CREDENTIALS",
    # docker configuration
    "DOCKER_HOST",
    "DOCKER_TLS_VERIFY",
    "DOCKER_CERT_PATH",
    "DOCKER_CONFIG",
    "DOCKER_BUILDKIT",
    # corporate proxy / TLS trust
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
})


@click.command(name="deploy")
@click.option(
    "--gcp",
    "use_gcp",
    is_flag=True,
    default=False,
    help="Deploy to GCP Cloud Run. Required (the only supported target today).",
)
@click.option(
    "--gcp-project",
    "gcp_project",
    default=None,
    help="The GCP project ID to deploy into (sets GCP_PROJECT). Required with --gcp.",
)
@click.option(
    "--region",
    default="us-central1",
    show_default=True,
    help="The GCP region for Cloud Run (sets GCP_REGION).",
)
@click.option(
    "--service-name",
    default="reflex-app",
    show_default=True,
    help="The Cloud Run service name (sets SERVICE_NAME).",
)
@click.option(
    "--ar-repo",
    default="reflex",
    show_default=True,
    help="The Artifact Registry repository name (sets AR_REPO).",
)
@click.option(
    "--version",
    "version_tag",
    default=None,
    help="The image version tag (sets VERSION). Defaults to a UTC timestamp.",
)
@click.option(
    "--cpu",
    "cpu",
    default="1",
    show_default=True,
    help="Cloud Run CPU allocation, e.g. '1', '2', '4' (sets CLOUD_RUN_CPU).",
)
@click.option(
    "--memory",
    "memory",
    default="1Gi",
    show_default=True,
    help="Cloud Run memory allocation, e.g. '512Mi', '1Gi', '2Gi' (sets CLOUD_RUN_MEMORY).",
)
@click.option(
    "--min-instances",
    "min_instances",
    default=1,
    show_default=True,
    type=click.IntRange(min=0),
    help="Minimum number of Cloud Run instances to keep warm (sets CLOUD_RUN_MIN_INSTANCES). Set to 0 to scale to zero.",
)
@click.option(
    "--max-instances",
    "max_instances",
    default=100,
    show_default=True,
    type=click.IntRange(min=1),
    help="Maximum number of Cloud Run instances during autoscaling (sets CLOUD_RUN_MAX_INSTANCES). Caps cost under traffic spikes.",
)
@click.option(
    "--allow-unauthenticated/--no-allow-unauthenticated",
    "allow_unauthenticated",
    default=True,
    show_default=True,
    help="Whether to make the Cloud Run service publicly reachable (sets CLOUD_RUN_ALLOW_UNAUTHENTICATED). Use --no-allow-unauthenticated for internal / IAP-fronted services; callers will then need a roles/run.invoker IAM binding.",
)
@click.option(
    "--service-account",
    "service_account",
    default=None,
    help="IAM service account email the Cloud Run service runs as (sets CLOUD_RUN_SERVICE_ACCOUNT). If omitted, Cloud Run uses the project's default compute SA. The deploying principal needs roles/iam.serviceAccountUser on the target SA.",
)
@click.option(
    "--envfile",
    default=None,
    help="Path to a .env file. Loaded into the Cloud Run service as env vars. Takes precedence over --env.",
)
@click.option(
    "--env",
    "envs",
    multiple=True,
    help="Environment variable to set on the Cloud Run service: <key>=<value>. Repeat for multiple, e.g. --env K1=V1 --env K2=V2. Plain Cloud Run env vars — visible to anyone with roles/run.viewer; for sensitive values use Secret Manager separately.",
)
@click.option(
    "--source",
    "source_dir",
    default=".",
    show_default=True,
    type=click.Path(file_okay=False, dir_okay=True),
    help="The directory containing the Reflex app. Uploaded to Cloud Build as the build context; the source tree itself is not modified.",
)
@click.option("--token", help="The Reflex authentication token.")
@click.option(
    "--build-token/--no-build-token",
    "build_token",
    default=True,
    show_default=True,
    help="Whether to make the Reflex access token available to the image build. "
    "`reflex export` needs it to validate a reflex-enterprise license. The token is "
    "staged as a Secret Manager version, referenced by resource name from the build "
    "config, mounted into `docker build` as a BuildKit secret (so it never reaches an "
    "image layer, `docker history`, or the build logs), and destroyed when the deploy "
    "finishes. Use --no-build-token to deploy without it.",
)
@click.option(
    "--token-secret",
    "token_secret",
    default=DEFAULT_TOKEN_SECRET_NAME,
    show_default=True,
    help="Secret Manager secret to stage the access token in, created on first use. "
    "Pass a full version resource (projects/P/secrets/S/versions/V) to reference a "
    "secret you manage yourself; the CLI then only reads it and never creates, "
    "updates, or destroys anything, and the Cloud Build service account needs "
    f"{SECRET_ACCESSOR_ROLE} on it.",
)
@click.option(
    "--interactive/--no-interactive",
    is_flag=True,
    default=True,
    help="Whether to prompt before running the deploy script.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print the manifest and generated cloudbuild.yaml without writing the tempfile or running the script.",
)
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
def deploy_command(
    use_gcp: bool,
    gcp_project: str | None,
    region: str,
    service_name: str,
    ar_repo: str,
    version_tag: str | None,
    cpu: str,
    memory: str,
    min_instances: int,
    max_instances: int,
    allow_unauthenticated: bool,
    service_account: str | None,
    envfile: str | None,
    envs: tuple[str, ...],
    source_dir: str,
    token: str | None,
    build_token: bool,
    token_secret: str,
    interactive: bool,
    dry_run: bool,
    loglevel: str,
):
    """Deploy a Reflex app to a cloud target.

    Currently the only supported target is GCP Cloud Run via --gcp. The
    command fetches a Dockerfile and bash deploy script from Reflex, embeds
    the Dockerfile inside a generated ``cloudbuild.yaml`` (written to a
    tempfile), rewrites the script's ``gcloud builds submit`` invocation to
    reference that config, then runs the script with cwd= your source dir.
    Your project tree is never modified.
    """
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

    if not use_gcp:
        console.error(
            "Specify a deploy target. Currently supported: --gcp (GCP Cloud Run)."
        )
        raise click.exceptions.Exit(2)
    if not gcp_project:
        console.error("--gcp-project is required when using --gcp.")
        raise click.exceptions.Exit(2)
    if max_instances < min_instances:
        console.error(
            f"--max-instances ({max_instances}) must be >= --min-instances ({min_instances})."
        )
        raise click.exceptions.Exit(2)

    # A secret the user manages themselves is referenced as-is; a bare name is
    # one we create/stage/destroy versions in.
    user_managed_secret = "/" in token_secret
    pattern = _SECRET_VERSION_PATTERN if user_managed_secret else _SECRET_NAME_PATTERN
    if not pattern.fullmatch(token_secret):
        console.error(
            "--token-secret must be a Secret Manager secret name "
            "([A-Za-z0-9_-], up to 255 chars) or a full version resource "
            "(projects/PROJECT/secrets/SECRET/versions/VERSION)."
        )
        raise click.exceptions.Exit(2)

    parsed_envs = _parse_envs(envfile=envfile, envs=envs)

    authenticated_client = hosting.get_authenticated_client(
        token=token, interactive=interactive
    )

    bash_path = shutil.which("bash")
    if not bash_path:
        console.error(
            "`bash` was not found on PATH; required to run the deploy script."
        )
        raise click.exceptions.Exit(1)

    gcloud_path = shutil.which("gcloud")
    if not gcloud_path:
        console.error(
            "The `gcloud` CLI was not found on PATH. Install it from "
            "https://cloud.google.com/sdk/docs/install and run `gcloud auth login` "
            "and `gcloud auth application-default login` before retrying."
        )
        raise click.exceptions.Exit(1)

    if not shutil.which("docker"):
        console.error(
            "The `docker` CLI was not found on PATH; required to build the image."
        )
        raise click.exceptions.Exit(1)

    if not _get_active_gcp_account(gcloud_path):
        console.error(
            "No active GCP account found. Run `gcloud auth login` and "
            "`gcloud auth application-default login`, then retry."
        )
        raise click.exceptions.Exit(1)

    dockerfile, deploy_script = _request_manifest(authenticated_client.token)

    # If the user asks for a private service, abort when the fetched script
    # doesn't reference CLOUD_RUN_ALLOW_UNAUTHENTICATED. Without that backend
    # support the deploy would silently use the script's hard-coded
    # --allow-unauthenticated, producing a public service when the user
    # explicitly asked for a private one — a silent privacy flip we'd rather
    # fail loud on.
    if not allow_unauthenticated and ENV_ALLOW_UNAUTHENTICATED not in deploy_script:
        console.error(
            "The Reflex backend's deploy script doesn't yet recognize "
            f"{ENV_ALLOW_UNAUTHENTICATED} — without it, --no-allow-unauthenticated "
            "would be silently ignored and the service would deploy as PUBLIC. "
            "Upgrade the Reflex backend, or remove --no-allow-unauthenticated."
        )
        raise click.exceptions.Exit(1)

    source_path = Path(source_dir).resolve()
    if not source_path.is_dir():
        console.error(f"Source directory does not exist: {source_path}")
        raise click.exceptions.Exit(1)

    # `reflex export` needs the access token for reflex-enterprise licensing, so
    # the RUN that exports the frontend gets a BuildKit secret mount. None means
    # nothing in the Dockerfile consumes a token, so none has to be staged.
    token_dockerfile = _inject_token_secret_mount(dockerfile) if build_token else None
    if build_token and token_dockerfile is None:
        console.warn(
            "Reflex's Dockerfile has no `reflex export` step to hand the access "
            "token to, so the build runs without it. Apps using reflex-enterprise "
            "will fail the frontend export — upgrade `reflex-hosting-cli` (or pass "
            "--no-build-token to silence this)."
        )
    # The version we stage doesn't exist until the user confirms the run, so the
    # preview stands in for it. Building the config now also fails fast on a
    # Dockerfile we can't embed, before anything is created in the project.
    preview_secret_version = None
    if token_dockerfile is not None:
        preview_secret_version = (
            token_secret
            if user_managed_secret
            else f"projects/{gcp_project}/secrets/{token_secret}/versions/NEW"
        )
    try:
        preview_yaml = _build_cloudbuild_yaml(
            token_dockerfile if token_dockerfile is not None else dockerfile,
            token_secret_version=preview_secret_version,
        )
    except ValueError as ex:
        console.error(str(ex))
        raise click.exceptions.Exit(1) from ex
    try:
        deploy_script = _rewrite_builds_submit(deploy_script)
    except ValueError as ex:
        console.error(str(ex))
        raise click.exceptions.Exit(1) from ex

    version_value = version_tag or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    deploy_env = {
        ENV_GCP_PROJECT: gcp_project,
        ENV_GCP_REGION: region,
        ENV_SERVICE_NAME: service_name,
        ENV_AR_REPO: ar_repo,
        ENV_VERSION: version_value,
        ENV_CPU: cpu,
        ENV_MEMORY: memory,
        ENV_MIN_INSTANCES: str(min_instances),
        ENV_MAX_INSTANCES: str(max_instances),
        ENV_ALLOW_UNAUTHENTICATED: "true" if allow_unauthenticated else "false",
    }
    if service_account is not None:
        if not service_account:
            console.error("--service-account cannot be an empty string.")
            raise click.exceptions.Exit(2)
        deploy_env[ENV_SERVICE_ACCOUNT] = service_account

    console.info("Received deploy manifest from Reflex.")
    console.print("")
    console.print(f"Source: {source_path}")
    console.print("Deploy environment:")
    for key, value in deploy_env.items():
        console.print(f"  {key}={value}")
    console.print("")
    console.print("Deploy script (rewritten to use cloudbuild.yaml):")
    console.print("─" * 60)
    console.print(deploy_script)
    console.print("─" * 60)
    console.info(
        f"The script runs with a restricted env (only {len(DEPLOY_ENV_ALLOWLIST)} "
        "allowlisted host variables forwarded plus the deploy variables above)."
    )
    console.info(
        "The Dockerfile is embedded in a Cloud Build config written to a "
        "tempfile; your source directory is not modified."
    )
    if preview_secret_version is not None:
        if user_managed_secret:
            console.info(
                f"The Reflex access token is read from {token_secret} and mounted into "
                "the image build as a BuildKit secret. The Cloud Build service account "
                f"needs {SECRET_ACCESSOR_ROLE} on that secret."
            )
        else:
            console.info(
                "The Reflex access token is staged as a new version of Secret Manager "
                f"secret '{token_secret}' in {gcp_project}, mounted into the image "
                "build as a BuildKit secret (so it never lands in an image layer), and "
                "destroyed when the deploy finishes."
            )

    env_vars_yaml = _format_env_vars_yaml(parsed_envs) if parsed_envs else None

    if dry_run:
        console.print("")
        console.print("cloudbuild.yaml contents:")
        console.print("─" * 60)
        console.print(preview_yaml)
        console.print("─" * 60)
        console.print("")
        console.print("Dockerfile contents (embedded in the build step):")
        console.print("─" * 60)
        console.print(token_dockerfile if token_dockerfile is not None else dockerfile)
        console.print("─" * 60)
        if env_vars_yaml is not None:
            console.print("")
            console.print(f"env-vars file contents ({len(parsed_envs)} variable(s)):")
            console.print("─" * 60)
            console.print(env_vars_yaml)
            console.print("─" * 60)
        console.info("Dry run — nothing staged or executed.")
        return

    if interactive:
        answer = console.ask(
            "Run the deploy script now?", choices=["y", "n"], default="y"
        )
        if answer != "y":
            console.warn("Aborted by user.")
            raise click.exceptions.Exit(1)

    with contextlib.ExitStack() as stack:
        secret_version = None
        if token_dockerfile is not None:
            secret_version = (
                token_secret
                if user_managed_secret
                else stack.enter_context(
                    _staged_token_secret(
                        gcloud_path=gcloud_path,
                        project=gcp_project,
                        secret_name=token_secret,
                        token=authenticated_client.token,
                    )
                )
            )
        # Staging can fail on a project without Secret Manager access; fall back
        # to a build without the token rather than blocking the deploy.
        if secret_version is None or token_dockerfile is None:
            cloudbuild_yaml = _build_cloudbuild_yaml(dockerfile)
        else:
            cloudbuild_yaml = _build_cloudbuild_yaml(
                token_dockerfile, token_secret_version=secret_version
            )
        cloudbuild_path = stack.enter_context(_temp_cloudbuild_yaml(cloudbuild_yaml))
        env_overrides = {
            **deploy_env,
            ENV_REFLEX_CLOUDBUILD_YAML: str(cloudbuild_path),
        }
        if env_vars_yaml is not None:
            env_vars_path = stack.enter_context(_temp_env_vars_yaml(env_vars_yaml))
            env_overrides[ENV_REFLEX_ENV_VARS_FILE] = str(env_vars_path)

        exit_code = _run_deploy_script(
            bash_path=bash_path,
            script=deploy_script,
            cwd=source_path,
            env_overrides=env_overrides,
        )
    if exit_code != 0:
        console.error(f"Deploy script exited with status {exit_code}.")
        raise click.exceptions.Exit(exit_code)
    console.success("Deployment finished.")


def _run_gcloud(
    gcloud_path: str,
    args: list[str],
    input_text: str | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str] | None:
    """Run a gcloud command, capturing its output.

    Secret values are passed on stdin via ``input_text`` rather than in argv,
    which is visible to other processes on the machine.

    Args:
        gcloud_path: Resolved path to the gcloud executable.
        args: Arguments to pass to gcloud.
        input_text: Data to write to the command's stdin.
        timeout: Seconds to wait before giving up on the command.

    Returns:
        The completed process, or None if gcloud could not be run at all.

    """
    try:
        return subprocess.run(
            [gcloud_path, *args],
            input=input_text,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as ex:
        console.debug(f"Failed to run `gcloud {' '.join(args)}`: {ex}")
        return None


def _gcloud_error(result: subprocess.CompletedProcess[str] | None) -> str:
    """Summarize a failed gcloud invocation for a user-facing message.

    Args:
        result: The completed process, or None if gcloud could not be run.

    Returns:
        The command's stderr, or a generic message when there is none.

    """
    if result is None:
        return "gcloud could not be run."
    return result.stderr.strip() or f"gcloud exited with status {result.returncode}."


def _get_active_gcp_account(gcloud_path: str) -> str | None:
    """Return the email of the active gcloud account, or None.

    Args:
        gcloud_path: Resolved path to the gcloud executable.

    Returns:
        The active account email or None if not logged in.

    """
    result = _run_gcloud(
        gcloud_path,
        ["auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
        timeout=10,
    )
    if result is None or result.returncode != 0:
        return None
    account = result.stdout.strip().splitlines()
    return account[0] if account else None


def _request_manifest(token: str) -> tuple[str, str]:
    """Fetch the Dockerfile + deploy script from Reflex.

    Args:
        token: The Reflex API token to authenticate with.

    Returns:
        A `(dockerfile, deploy_command)` tuple.

    Raises:
        Exit: If the request fails or the response shape is invalid.

    """
    import httpx

    from reflex_cli.utils import hosting

    url = urljoin(constants.Hosting.HOSTING_SERVICE, GCP_MANIFEST_ENDPOINT)
    try:
        response = httpx.get(
            url,
            headers=hosting.authorization_header(token),
            timeout=constants.Hosting.TIMEOUT,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        detail = ex.response.text
        with contextlib.suppress(ValueError):
            detail = ex.response.json().get("detail", detail)
        if ex.response.status_code == 403:
            console.error(
                "Reflex denied the request (403). GCP Cloud Run deploys require an "
                "Enterprise tier subscription."
            )
        else:
            console.error(f"Reflex rejected the manifest request: {detail}")
        raise click.exceptions.Exit(1) from ex
    except httpx.HTTPError as ex:
        console.error(f"Failed to reach Reflex at {url}: {ex}")
        raise click.exceptions.Exit(1) from ex

    try:
        body = response.json()
    except ValueError as ex:
        console.error("Reflex returned a non-JSON response.")
        raise click.exceptions.Exit(1) from ex

    if not isinstance(body, dict):
        console.error("Reflex returned an unexpected response shape.")
        raise click.exceptions.Exit(1)

    dockerfile = body.get(FIELD_DOCKERFILE)
    deploy_command = body.get(FIELD_DEPLOY_COMMAND)
    if not isinstance(dockerfile, str) or not dockerfile.strip():
        console.error(
            f"Reflex response is missing a non-empty {FIELD_DOCKERFILE!r} field."
        )
        raise click.exceptions.Exit(1)
    if not isinstance(deploy_command, str) or not deploy_command.strip():
        console.error(
            f"Reflex response is missing a non-empty {FIELD_DEPLOY_COMMAND!r} field."
        )
        raise click.exceptions.Exit(1)

    return dockerfile, deploy_command


def _inject_token_secret_mount(dockerfile: str) -> str | None:
    """Give the Dockerfile's `reflex export` step access to the Reflex token.

    ``reflex export`` refuses to run when the app uses ``reflex-enterprise`` and
    no Reflex access token is available, so the token has to reach the image
    build. It is mounted as a BuildKit secret and read inside the RUN rather
    than passed as a build arg or ``ENV``, so it never becomes part of an image
    layer, of ``docker history``, or of the image pushed to Artifact Registry.

    Args:
        dockerfile: The Dockerfile body from Reflex.

    Returns:
        The Dockerfile with the secret wired into the export step, or None if
        no instruction consumes the token (nothing has to be staged then).

    """
    if f"id={TOKEN_SECRET_ID}" in dockerfile:
        # Reflex's Dockerfile already declares the mount itself.
        return dockerfile

    injected = False

    def rewrite(match: re.Match[str]) -> str:
        nonlocal injected
        instruction = match.group(0)
        if not _REFLEX_EXPORT_PATTERN.search(instruction):
            return instruction
        injected = True
        indent = match.group("indent")
        # mode=0444 so the mount is still readable if the export runs as a
        # non-root USER; the secret only exists inside the ephemeral build.
        return (
            f"{indent}RUN --mount=type=secret,id={TOKEN_SECRET_ID},mode=0444 \\\n"
            f"{indent}    if [ -s {TOKEN_SECRET_MOUNT_PATH} ]; then export "
            f'{ENV_REFLEX_ACCESS_TOKEN}="$(cat {TOKEN_SECRET_MOUNT_PATH})"; fi; \\\n'
            f"{indent}    {match.group('body')}"
        )

    rewritten = _RUN_INSTRUCTION_PATTERN.sub(rewrite, dockerfile)
    return rewritten if injected else None


def _build_cloudbuild_yaml(
    dockerfile_contents: str, token_secret_version: str | None = None
) -> str:
    r"""Generate a Cloud Build config that materializes the Dockerfile inline.

    The Dockerfile body is dropped into a bash heredoc (``cat <<'MARKER' >
    Dockerfile``) inside the build step. The marker is single-quoted so bash
    treats the body literally — no shell-meta expansion of ``$``, `` ` ``, or
    ``\``. YAML literal-block indentation gets stripped uniformly so the
    closing marker line ends up at column 0 where bash expects it.

    When ``token_secret_version`` is given, the step pulls the Reflex access
    token from Secret Manager into ``secretEnv`` and hands it to ``docker build``
    as a BuildKit secret. Only the secret's resource name goes into the config —
    the value itself never appears in the build config (readable by anyone with
    ``roles/cloudbuild.builds.viewer``) or in the build logs.

    Args:
        dockerfile_contents: The Dockerfile body from Reflex.
        token_secret_version: Fully-qualified Secret Manager version holding the
            Reflex access token, or None to build without one.

    Returns:
        A complete ``cloudbuild.yaml`` body, ready to write to disk.

    Raises:
        ValueError: If the Dockerfile contains a line that exactly matches the
            heredoc marker (would terminate the heredoc early).

    """
    marker = "REFLEX_DOCKERFILE_EOF"
    if any(line.rstrip() == marker for line in dockerfile_contents.splitlines()):
        raise ValueError(
            f"Dockerfile content contains the reserved heredoc marker {marker!r}."
        )
    # Cloud Build runs its own substitution pass over `args`, so any `$NAME` or
    # `${NAME}` in the Dockerfile (e.g. `ENV PATH="${UV_PROJECT_ENVIRONMENT}/bin"`)
    # would be treated as a Cloud Build variable and fail with
    # "not a valid built-in substitution". Escape literal `$` to `$$` so the
    # parser restores `$` before bash runs.
    escaped = dockerfile_contents.replace("$", "$$")
    # 6 spaces to fit inside the YAML literal block under `args:\n  - -c\n  - |`.
    indent = "      "
    body = "".join(f"{indent}{line}\n" for line in escaped.splitlines())
    step_env = ""
    stage_secret = ""
    build_flags = ""
    discard_secret = ""
    available_secrets = ""
    if token_secret_version:
        # `--secret` needs BuildKit; `$$` escapes Cloud Build's substitution pass
        # so bash sees the secretEnv variable.
        step_env = (
            "  env:\n"
            "    - DOCKER_BUILDKIT=1\n"
            "  secretEnv:\n"
            f"    - {ENV_REFLEX_ACCESS_TOKEN}\n"
        )
        stage_secret = (
            f"{indent}umask 077\n"
            f"{indent}printf '%s' \"$${ENV_REFLEX_ACCESS_TOKEN}\" "
            f"> {TOKEN_SECRET_STAGE_PATH}\n"
        )
        build_flags = f" --secret id={TOKEN_SECRET_ID},src={TOKEN_SECRET_STAGE_PATH}"
        discard_secret = f"{indent}rm -f {TOKEN_SECRET_STAGE_PATH}\n"
        available_secrets = (
            "availableSecrets:\n"
            "  secretManager:\n"
            f"    - versionName: {token_secret_version}\n"
            f"      env: {ENV_REFLEX_ACCESS_TOKEN}\n"
        )
    return (
        "steps:\n"
        "- name: gcr.io/cloud-builders/docker\n"
        "  entrypoint: bash\n"
        f"{step_env}"
        "  args:\n"
        "    - -c\n"
        "    - |\n"
        f"{indent}set -e\n"
        f"{indent}cat > Dockerfile <<'{marker}'\n"
        f"{body}"
        f"{indent}{marker}\n"
        f"{stage_secret}"
        f'{indent}docker build{build_flags} -t "$_IMAGE" .\n'
        f"{discard_secret}"
        f'{indent}docker push "$_IMAGE"\n'
        "images:\n"
        "  - $_IMAGE\n"
        f"{available_secrets}"
    )


def _rewrite_builds_submit(script: str) -> str:
    """Rewrite the Reflex script's `gcloud builds submit` invocation to use --config=.

    Replaces the (possibly multi-line) ``gcloud builds submit --tag X .``
    command with one that references our generated cloudbuild.yaml via the
    ``REFLEX_CLOUDBUILD_YAML`` environment variable and passes the image tag
    through ``--substitutions=_IMAGE=...``.

    Args:
        script: The Reflex deploy script body.

    Returns:
        The script with the build-submit step rewritten.

    Raises:
        ValueError: If `gcloud builds submit` cannot be located in the script.

    """
    match = _BUILDS_SUBMIT_PATTERN.search(script)
    if not match:
        raise ValueError(
            "Couldn't find `gcloud builds submit` in the deploy script. The "
            "manifest format may have changed; Contact support@reflex.dev"
        )
    indent = match.group("indent")
    line_start = script.rfind("\n", 0, match.start()) + 1
    # Consume continuation lines (trailing backslash) until we hit a final line.
    cursor = match.end()
    while True:
        nl = script.find("\n", cursor)
        if nl == -1:
            cmd_end = len(script)
            break
        if not script[cursor:nl].rstrip().endswith("\\"):
            cmd_end = nl
            break
        cursor = nl + 1

    replacement = (
        f"{indent}gcloud builds submit \\\n"
        f'{indent}    --config="${{{ENV_REFLEX_CLOUDBUILD_YAML}}}" \\\n'
        f'{indent}    --substitutions=_IMAGE="${{IMAGE}}" \\\n'
        f'{indent}    --project "${{GCP_PROJECT}}" \\\n'
        f"{indent}    ."
    )
    return script[:line_start] + replacement + script[cmd_end:]


@contextlib.contextmanager
def _staged_token_secret(gcloud_path: str, project: str, secret_name: str, token: str):
    """Stage the Reflex access token in Secret Manager for the duration of the build.

    Cloud Build can only read secrets from Secret Manager — a value passed
    through the build config or ``--substitutions`` would be readable from the
    build's metadata afterwards. The version is destroyed on the way out so the
    token isn't left sitting in the user's project.

    Args:
        gcloud_path: Resolved path to the gcloud executable.
        project: The GCP project ID to stage the secret in.
        secret_name: Name of the Secret Manager secret to add a version to.
        token: The Reflex access token to store.

    Yields:
        The fully-qualified version resource name, or None if staging failed.

    """
    version = _stage_token_secret(gcloud_path, project, secret_name, token)
    try:
        yield version
    finally:
        if version is not None:
            _destroy_secret_version(gcloud_path, project, secret_name, version)


def _stage_token_secret(
    gcloud_path: str, project: str, secret_name: str, token: str
) -> str | None:
    """Add the Reflex access token as a new version of a Secret Manager secret.

    Args:
        gcloud_path: Resolved path to the gcloud executable.
        project: The GCP project ID to stage the secret in.
        secret_name: Name of the Secret Manager secret to add a version to.
        token: The Reflex access token to store.

    Returns:
        The fully-qualified version resource name, or None if any step failed.

    """
    if not _ensure_secret_exists(gcloud_path, project, secret_name):
        return None
    result = _run_gcloud(
        gcloud_path,
        [
            "secrets",
            "versions",
            "add",
            secret_name,
            "--project",
            project,
            "--data-file=-",
            "--format=value(name)",
        ],
        input_text=token,
        timeout=60,
    )
    if result is None or result.returncode != 0:
        console.warn(
            f"Couldn't store the Reflex access token in Secret Manager secret "
            f"'{secret_name}': {_gcloud_error(result)}\nBuilding without it — the "
            "frontend export will fail if your app uses reflex-enterprise."
        )
        return None
    # `versions add` prints the created resource name; fall back to the alias if
    # a future gcloud stops doing that.
    version = result.stdout.strip().splitlines()
    version_name = (
        version[0]
        if version
        else f"projects/{project}/secrets/{secret_name}/versions/latest"
    )
    _grant_secret_access(gcloud_path, project, secret_name)
    return version_name


def _ensure_secret_exists(gcloud_path: str, project: str, secret_name: str) -> bool:
    """Create the Secret Manager secret if it doesn't exist yet.

    Args:
        gcloud_path: Resolved path to the gcloud executable.
        project: The GCP project ID the secret lives in.
        secret_name: Name of the Secret Manager secret.

    Returns:
        Whether the secret exists and can be written to.

    """
    describe = _run_gcloud(
        gcloud_path,
        [
            "secrets",
            "describe",
            secret_name,
            "--project",
            project,
            "--format=value(name)",
        ],
    )
    if describe is not None and describe.returncode == 0:
        return True

    create_args = [
        "secrets",
        "create",
        secret_name,
        "--project",
        project,
        "--replication-policy=automatic",
        f"--labels={TOKEN_SECRET_LABEL}",
        "--quiet",
    ]
    create = _run_gcloud(gcloud_path, create_args, timeout=60)
    if _secret_created(create):
        return True

    # The most likely reason a first create fails is the Secret Manager API not
    # being enabled on the project; enable it (the deploy script does the same
    # for the APIs it needs) and try once more.
    console.info(f"Enabling {SECRETMANAGER_SERVICE} on {project}...")
    enable = _run_gcloud(
        gcloud_path,
        ["services", "enable", SECRETMANAGER_SERVICE, "--project", project, "--quiet"],
        timeout=180,
    )
    if enable is None or enable.returncode != 0:
        console.warn(
            f"Couldn't enable {SECRETMANAGER_SERVICE} on {project}: "
            f"{_gcloud_error(enable)}\nBuilding without the Reflex access token — the "
            "frontend export will fail if your app uses reflex-enterprise."
        )
        return False
    retry = _run_gcloud(gcloud_path, create_args, timeout=60)
    if _secret_created(retry):
        return True
    console.warn(
        f"Couldn't create Secret Manager secret '{secret_name}' in {project}: "
        f"{_gcloud_error(retry)}\nBuilding without the Reflex access token — the "
        "frontend export will fail if your app uses reflex-enterprise. Pass "
        "--token-secret with a secret you manage yourself, or --no-build-token."
    )
    return False


def _secret_created(result: subprocess.CompletedProcess[str] | None) -> bool:
    """Report whether a `gcloud secrets create` left the secret in place.

    Args:
        result: The completed process, or None if gcloud could not be run.

    Returns:
        True when the secret was created, or already existed.

    """
    if result is None:
        return False
    return result.returncode == 0 or "already exists" in result.stderr.lower()


def _grant_secret_access(gcloud_path: str, project: str, secret_name: str) -> None:
    """Let the Cloud Build service accounts read the staged secret.

    Builds run as either the legacy Cloud Build service account or the project's
    default compute service account depending on when the project was created,
    so both are granted access to this one secret; whichever doesn't exist just
    fails its own binding.

    Args:
        gcloud_path: Resolved path to the gcloud executable.
        project: The GCP project ID the secret lives in.
        secret_name: Name of the Secret Manager secret.

    """
    project_number = _get_project_number(gcloud_path, project)
    if project_number is None:
        console.debug(f"Couldn't resolve the project number for {project}.")
        return
    granted = False
    for account in (
        f"{project_number}@cloudbuild.gserviceaccount.com",
        f"{project_number}-compute@developer.gserviceaccount.com",
    ):
        result = _run_gcloud(
            gcloud_path,
            [
                "secrets",
                "add-iam-policy-binding",
                secret_name,
                "--project",
                project,
                f"--member=serviceAccount:{account}",
                f"--role={SECRET_ACCESSOR_ROLE}",
                "--condition=None",
                "--quiet",
            ],
            timeout=60,
        )
        if result is not None and result.returncode == 0:
            granted = True
        else:
            console.debug(
                f"Couldn't grant {SECRET_ACCESSOR_ROLE} on '{secret_name}' to "
                f"{account}: {_gcloud_error(result)}"
            )
    if not granted:
        console.warn(
            f"Couldn't grant the Cloud Build service account {SECRET_ACCESSOR_ROLE} "
            f"on '{secret_name}'. If the build fails to access the secret, run:\n"
            f"  gcloud secrets add-iam-policy-binding {secret_name} "
            f"--project {project} --role={SECRET_ACCESSOR_ROLE} "
            "--member=serviceAccount:<cloud-build-service-account>"
        )


def _get_project_number(gcloud_path: str, project: str) -> str | None:
    """Look up the numeric project number for a project ID.

    Args:
        gcloud_path: Resolved path to the gcloud executable.
        project: The GCP project ID.

    Returns:
        The project number, or None if it couldn't be resolved.

    """
    result = _run_gcloud(
        gcloud_path,
        ["projects", "describe", project, "--format=value(projectNumber)"],
    )
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _destroy_secret_version(
    gcloud_path: str, project: str, secret_name: str, version_name: str
) -> None:
    """Destroy the secret version staged for this deploy.

    Args:
        gcloud_path: Resolved path to the gcloud executable.
        project: The GCP project ID the secret lives in.
        secret_name: Name of the Secret Manager secret.
        version_name: Fully-qualified version resource name to destroy.

    """
    version_id = version_name.rsplit("/", 1)[-1]
    result = _run_gcloud(
        gcloud_path,
        [
            "secrets",
            "versions",
            "destroy",
            version_id,
            f"--secret={secret_name}",
            "--project",
            project,
            "--quiet",
        ],
        timeout=60,
    )
    if result is None or result.returncode != 0:
        console.warn(
            f"Couldn't destroy the staged access token ({version_name}): "
            f"{_gcloud_error(result)}\nDestroy it with: gcloud secrets versions "
            f"destroy {version_id} --secret={secret_name} --project {project}"
        )
        return
    console.debug(f"Destroyed staged access token version {version_name}.")


@contextlib.contextmanager
def _temp_cloudbuild_yaml(contents: str):
    """Write a cloudbuild.yaml to a tempfile and yield its path; always clean up.

    Args:
        contents: The cloudbuild.yaml body to write.

    Yields:
        The path to the written tempfile.

    """
    fd, path_str = tempfile.mkstemp(prefix="reflex-cloudbuild-", suffix=".yaml")
    path = Path(path_str)
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(contents)
        yield path
    finally:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()


@contextlib.contextmanager
def _temp_env_vars_yaml(contents: str):
    """Write the env-vars YAML to a tempfile and yield its path; always clean up.

    Args:
        contents: The YAML body to write (one ``KEY: "value"`` line per env var).

    Yields:
        The path to the written tempfile.

    """
    fd, path_str = tempfile.mkstemp(prefix="reflex-env-vars-", suffix=".yaml")
    path = Path(path_str)
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(contents)
        yield path
    finally:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()


def _parse_envs(envfile: str | None, envs: tuple[str, ...]) -> dict[str, str]:
    """Resolve --envfile + --env into a single dict of env vars.

    Mirrors the precedence of the existing `reflex deploy` / `reflex secrets
    update` flow: when both are provided, --envfile wins and --env is
    discarded with a warning. Empty values are preserved as empty strings;
    keys defined without a value in the envfile (``FOO`` with no ``=``)
    become empty strings rather than ``None``.

    Args:
        envfile: Path to a .env file, or None.
        envs: Tuple of ``KEY=VALUE`` strings from repeated --env flags.

    Returns:
        Dict of env var name → string value. Empty when neither input is set.

    """
    from reflex_cli.utils import hosting

    if envfile and envs:
        console.warn("--envfile is set; ignoring --env")

    if envfile:
        try:
            from dotenv import dotenv_values  # pyright: ignore[reportMissingImports]
        except ImportError:
            console.error(
                'The `python-dotenv` package is required for --envfile. Run `pip install "python-dotenv>=1.0.1"`.'
            )
            raise click.exceptions.Exit(1) from None
        return {
            k: (v if v is not None else "") for k, v in dotenv_values(envfile).items()
        }

    if envs:
        return hosting.process_envs(list(envs))

    return {}


def _format_env_vars_yaml(envs: dict[str, str]) -> str:
    """Format env vars as YAML for gcloud ``--env-vars-file``.

    Uses ``json.dumps`` per value so any string — quotes, backslashes,
    newlines, unicode — is encoded safely. JSON strings are valid YAML, so
    the output round-trips through gcloud's YAML loader.

    Args:
        envs: Dict of env var name → string value.

    Returns:
        YAML body with one ``KEY: "value"`` line per env var.

    """
    return "".join(f"{k}: {json.dumps(v)}\n" for k, v in envs.items())


def _run_deploy_script(
    bash_path: str,
    script: str,
    cwd: Path,
    env_overrides: dict[str, str],
) -> int:
    """Run the bash deploy script, streaming output to the user's terminal.

    The script's environment is restricted to ``DEPLOY_ENV_ALLOWLIST`` (plus the
    explicit ``env_overrides``) so unrelated host secrets like ``AWS_*`` or
    ``GITHUB_TOKEN`` cannot be exfiltrated by a tampered or compromised manifest.

    Args:
        bash_path: Resolved path to the bash executable.
        script: The bash script body received from Reflex.
        cwd: Working directory to run the script in.
        env_overrides: Environment variables required by the deploy script.

    Returns:
        The exit code of the bash process.

    """
    env = {
        name: value
        for name, value in os.environ.items()
        if name in DEPLOY_ENV_ALLOWLIST
    }
    env.update(env_overrides)
    try:
        result = subprocess.run(
            [bash_path, "-s"],
            input=script,
            text=True,
            cwd=cwd,
            env=env,
            check=False,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
    except OSError as ex:
        console.error(f"Failed to launch bash: {ex}")
        return 1
    return result.returncode
