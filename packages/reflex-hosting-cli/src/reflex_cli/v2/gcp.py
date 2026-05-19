"""GCP Cloud Run deploy commands for the Reflex Cloud CLI.

Fetches a Dockerfile + bash deploy script from Reflex and runs the script
against the user's source directory. The Dockerfile is materialized inside
a Cloud Build job (via a ``cloudbuild.yaml`` written to a tempfile and
referenced with ``gcloud builds submit --config=...``) — the user's project
tree is never modified. The script reads its parameters from environment
variables (GCP_PROJECT, GCP_REGION, SERVICE_NAME, AR_REPO, VERSION,
REFLEX_CLOUDBUILD_YAML).
"""

from __future__ import annotations

import contextlib
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
# Path to the Cloud Build config file written by the CLI. The rewritten
# deploy script references it as ``--config="${REFLEX_CLOUDBUILD_YAML}"``.
ENV_REFLEX_CLOUDBUILD_YAML = "REFLEX_CLOUDBUILD_YAML"

# Pattern for the start of the `gcloud builds submit` invocation in the
# Reflex deploy script. We rewrite that whole multi-line command to use
# `--config=` so the Dockerfile lives inside a cloudbuild.yaml instead of
# being staged on disk next to the user's source.
_BUILDS_SUBMIT_PATTERN = re.compile(
    r"(?P<indent>^[ \t]*)gcloud[ \t]+builds[ \t]+submit\b",
    re.MULTILINE,
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
    "--source",
    "source_dir",
    default=".",
    show_default=True,
    type=click.Path(file_okay=False, dir_okay=True),
    help="The directory containing the Reflex app. Uploaded to Cloud Build as the build context; the source tree itself is not modified.",
)
@click.option("--token", help="The Reflex authentication token.")
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
    source_dir: str,
    token: str | None,
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

    cloudbuild_yaml = _build_cloudbuild_yaml(dockerfile)
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
    }

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

    if dry_run:
        console.print("")
        console.print("cloudbuild.yaml contents:")
        console.print("─" * 60)
        console.print(cloudbuild_yaml)
        console.print("─" * 60)
        console.print("")
        console.print("Dockerfile contents (embedded in the build step):")
        console.print("─" * 60)
        console.print(dockerfile)
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

    with _temp_cloudbuild_yaml(cloudbuild_yaml) as cloudbuild_path:
        exit_code = _run_deploy_script(
            bash_path=bash_path,
            script=deploy_script,
            cwd=source_path,
            env_overrides={
                **deploy_env,
                ENV_REFLEX_CLOUDBUILD_YAML: str(cloudbuild_path),
            },
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


def _build_cloudbuild_yaml(dockerfile_contents: str) -> str:
    r"""Generate a Cloud Build config that materializes the Dockerfile inline.

    The Dockerfile body is dropped into a bash heredoc (``cat <<'MARKER' >
    Dockerfile``) inside the build step. The marker is single-quoted so bash
    treats the body literally — no shell-meta expansion of ``$``, `` ` ``, or
    ``\``. YAML literal-block indentation gets stripped uniformly so the
    closing marker line ends up at column 0 where bash expects it.

    Args:
        dockerfile_contents: The Dockerfile body from Reflex.

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
    return (
        "steps:\n"
        "- name: gcr.io/cloud-builders/docker\n"
        "  entrypoint: bash\n"
        "  args:\n"
        "    - -c\n"
        "    - |\n"
        f"{indent}cat > Dockerfile <<'{marker}'\n"
        f"{body}"
        f"{indent}{marker}\n"
        f'{indent}docker build -t "$_IMAGE" .\n'
        f'{indent}docker push "$_IMAGE"\n'
        "images:\n"
        "  - $_IMAGE\n"
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
