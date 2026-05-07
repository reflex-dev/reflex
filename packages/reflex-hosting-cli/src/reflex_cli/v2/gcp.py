"""GCP Cloud Run deploy commands for the Reflex Cloud CLI.

Fetches a Dockerfile + bash deploy script from flexgen, writes the Dockerfile
into the user's project, prints the script, and runs it via bash after the
user confirms. The script reads its parameters from environment variables
(GCP_PROJECT, GCP_REGION, SERVICE_NAME, AR_REPO, VERSION).
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
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

# Manifest response field names from flexgen.
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


@click.group()
def gcp_cli():
    """Commands for deploying to GCP Cloud Run."""


@gcp_cli.command(name="deploy")
@click.option(
    "--gcp-project",
    "gcp_project",
    required=True,
    help="The GCP project ID to deploy into (sets GCP_PROJECT).",
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
    "--source",
    "source_dir",
    default=".",
    show_default=True,
    type=click.Path(file_okay=False, dir_okay=True),
    help="The directory containing the Reflex app and into which the Dockerfile is written.",
)
@click.option(
    "--overwrite-dockerfile/--no-overwrite-dockerfile",
    default=False,
    show_default=True,
    help="Overwrite an existing Dockerfile without prompting.",
)
@click.option("--token", help="The Reflex authentication token.")
@click.option(
    "--interactive/--no-interactive",
    is_flag=True,
    default=True,
    help="Whether to prompt before overwriting the Dockerfile and running the script.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print the manifest without writing the Dockerfile or running the script.",
)
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
def gcp_deploy(
    gcp_project: str,
    region: str,
    service_name: str,
    ar_repo: str,
    version_tag: str | None,
    source_dir: str,
    overwrite_dockerfile: bool,
    token: str | None,
    interactive: bool,
    dry_run: bool,
    loglevel: str,
):
    """Deploy a Reflex app to GCP Cloud Run.

    Fetches a Dockerfile and bash deploy script from flexgen, writes the Dockerfile
    into the source directory, then asks before running the script.
    """
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

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

    source_path = Path(source_dir).resolve()
    if not source_path.is_dir():
        console.error(f"Source directory does not exist: {source_path}")
        raise click.exceptions.Exit(1)
    dockerfile_path = source_path / DOCKERFILE_NAME

    version_value = version_tag or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    deploy_env = {
        ENV_GCP_PROJECT: gcp_project,
        ENV_GCP_REGION: region,
        ENV_SERVICE_NAME: service_name,
        ENV_AR_REPO: ar_repo,
        ENV_VERSION: version_value,
    }

    console.info("Received deploy manifest from flexgen.")
    console.print("")
    console.print(f"Dockerfile target: {dockerfile_path}")
    console.print("Deploy environment:")
    for key, value in deploy_env.items():
        console.print(f"  {key}={value}")
    console.print("")
    console.print("Deploy script:")
    console.print("─" * 60)
    console.print(deploy_script)
    console.print("─" * 60)
    console.info(
        f"The script runs with a restricted env (only {len(DEPLOY_ENV_ALLOWLIST)} "
        "allowlisted host variables forwarded plus the deploy variables above)."
    )

    if dry_run:
        console.print("")
        console.print("Dockerfile contents:")
        console.print("─" * 60)
        console.print(dockerfile)
        console.print("─" * 60)
        console.info("Dry run — nothing written or executed.")
        return

    if not _write_dockerfile(
        dockerfile_path, dockerfile, overwrite_dockerfile, interactive
    ):
        raise click.exceptions.Exit(1)

    if interactive:
        answer = console.ask(
            "Run the deploy script now?", choices=["y", "n"], default="y"
        )
        if answer != "y":
            console.warn(
                "Aborted by user. The Dockerfile has been written for later use."
            )
            raise click.exceptions.Exit(1)

    exit_code = _run_deploy_script(
        bash_path=bash_path,
        script=deploy_script,
        cwd=source_path,
        env_overrides=deploy_env,
    )
    if exit_code != 0:
        console.error(f"Deploy script exited with status {exit_code}.")
        raise click.exceptions.Exit(exit_code)
    console.success("Deployment finished.")


def _get_active_gcp_account(gcloud_path: str) -> str | None:
    """Return the email of the active gcloud account, or None.

    Args:
        gcloud_path: Resolved path to the gcloud executable.

    Returns:
        The active account email or None if not logged in.

    """
    try:
        result = subprocess.run(
            [
                gcloud_path,
                "auth",
                "list",
                "--filter=status:ACTIVE",
                "--format=value(account)",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as ex:
        console.debug(f"Failed to query gcloud auth list: {ex}")
        return None
    account = result.stdout.strip().splitlines()
    return account[0] if account else None


def _request_manifest(token: str) -> tuple[str, str]:
    """Fetch the Dockerfile + deploy script from flexgen.

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
                "Flexgen denied the request (403). GCP Cloud Run deploys require an "
                "Enterprise tier subscription."
            )
        else:
            console.error(f"Flexgen rejected the manifest request: {detail}")
        raise click.exceptions.Exit(1) from ex
    except httpx.HTTPError as ex:
        console.error(f"Failed to reach flexgen at {url}: {ex}")
        raise click.exceptions.Exit(1) from ex

    try:
        body = response.json()
    except ValueError as ex:
        console.error("Flexgen returned a non-JSON response.")
        raise click.exceptions.Exit(1) from ex

    if not isinstance(body, dict):
        console.error("Flexgen returned an unexpected response shape.")
        raise click.exceptions.Exit(1)

    dockerfile = body.get(FIELD_DOCKERFILE)
    deploy_command = body.get(FIELD_DEPLOY_COMMAND)
    if not isinstance(dockerfile, str) or not dockerfile.strip():
        console.error(
            f"Flexgen response is missing a non-empty {FIELD_DOCKERFILE!r} field."
        )
        raise click.exceptions.Exit(1)
    if not isinstance(deploy_command, str) or not deploy_command.strip():
        console.error(
            f"Flexgen response is missing a non-empty {FIELD_DEPLOY_COMMAND!r} field."
        )
        raise click.exceptions.Exit(1)

    return dockerfile, deploy_command


def _write_dockerfile(
    path: Path, contents: str, overwrite: bool, interactive: bool
) -> bool:
    """Write the Dockerfile to disk, prompting before overwriting in interactive mode.

    Args:
        path: Where to write the Dockerfile.
        contents: The Dockerfile body.
        overwrite: If True, overwrite without prompting.
        interactive: If False, never prompt; require `overwrite` when the file exists.

    Returns:
        True on success, False if the user declined to overwrite or write failed.

    """
    if path.exists() and not overwrite:
        if not interactive:
            console.error(
                f"{path} already exists. Pass --overwrite-dockerfile to replace it "
                "in non-interactive mode."
            )
            return False
        answer = console.ask(
            f"{path} already exists. Overwrite?", choices=["y", "n"], default="n"
        )
        if answer != "y":
            console.warn(
                f"Keeping the existing {path.name}. Re-run with --overwrite-dockerfile "
                "or move the file aside to use the flexgen Dockerfile."
            )
            return False
    try:
        path.write_text(contents)
    except OSError as ex:
        console.error(f"Failed to write {path}: {ex}")
        return False
    console.info(f"Wrote {path}.")
    return True


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
        script: The bash script body received from flexgen.
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
