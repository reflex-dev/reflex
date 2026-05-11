```python exec
import reflex as rx
```

# Deploy to GCP Cloud Run

The `reflex cloud deploy --gcp` command deploys a Reflex app to your own [Google Cloud Run](https://cloud.google.com/run) service. Reflex Cloud fetches a Cloud Run-ready Dockerfile and a `gcloud` deploy script, wraps the Dockerfile inside a [Cloud Build config (`cloudbuild.yaml`)](https://cloud.google.com/build/docs/build-config-file-schema), and runs the script against the Google Cloud project you specify. The image is built on Cloud Build (so it works from any host OS, including Apple Silicon) and pushed to Artifact Registry. Your project tree is never modified — the Dockerfile lives only inside the build config that's submitted to Cloud Build.

```md alert info
# Enterprise tier only.

Self-deploying to GCP Cloud Run is part of the **Enterprise tier** of Reflex Cloud. The control plane will return `403` to non-Enterprise tokens, and the CLI surfaces a clear error pointing at this. Contact [sales@reflex.dev](mailto:sales@reflex.dev) to upgrade.
```

## Prerequisites

Before running the command, install and authenticate the local tools the deploy script invokes:

- `gcloud` — install from the [Google Cloud SDK docs](https://cloud.google.com/sdk/docs/install), then run:
  - `gcloud auth login`
  - `gcloud auth application-default login`
- `docker` — required by `gcloud builds submit` for source upload.
- `bash` — used to run the deploy script.

You also need:

- A GCP project with **billing enabled**. Without it, `gcloud services enable` fails with `UREQ_PROJECT_BILLING_NOT_FOUND`.
- An Enterprise-tier Reflex Cloud subscription and a logged-in Reflex CLI (`reflex login`).

## Quick start

From the root of your Reflex app:

```bash
reflex cloud deploy --gcp \
    --gcp-project my-gcp-project-id \
    --service-name my-reflex-app
```

The CLI will:

1. Authenticate against Reflex Cloud and fetch the deploy manifest (Dockerfile + `gcloud` script).
2. Generate a `cloudbuild.yaml` that embeds the Dockerfile as a build step, write it to a tempfile, and rewrite the script's `gcloud builds submit` invocation to use `--config="$REFLEX_CLOUDBUILD_YAML"`.
3. Print the (rewritten) script so you can review it.
4. Ask for confirmation, then run the script with `cwd=` your source directory: enable the required APIs, create the Artifact Registry repository, build the image on Cloud Build (which materializes the Dockerfile inside the build step from the `cloudbuild.yaml`), and deploy a public Cloud Run service.
5. Delete the tempfile after the script finishes.

Your source tree is never written to — if you have an existing `Dockerfile` in `--source`, it's left in place and ignored. The Reflex-provided Dockerfile only exists inside the `cloudbuild.yaml` tempfile (and inside the Cloud Build job).

When it's done, you'll get a service URL like `https://my-reflex-app-<project-number>.us-central1.run.app`.

## Options

| Option | Default | Description |
| --- | --- | --- |
| `--gcp` | _(required)_ | Selects the GCP Cloud Run target. |
| `--gcp-project` | _(required)_ | The GCP **project ID** to deploy into. Project numbers are **not** accepted by `gcloud artifacts repositories`; use the project ID. |
| `--region` | `us-central1` | Cloud Run region. |
| `--service-name` | `reflex-app` | Cloud Run service name. |
| `--ar-repo` | `reflex` | Artifact Registry repository name (created on first deploy). |
| `--version` | UTC timestamp (`YYYYMMDD-HHMMSS`) | Image version tag. |
| `--source` | `.` | Directory containing the Reflex app. Uploaded to Cloud Build as the build context; the source tree itself is not modified. |
| `--token` | _from `~/.reflex` config_ | Reflex authentication token. |
| `--interactive / --no-interactive` | `--interactive` | Whether to prompt before running the deploy script. |
| `--dry-run` | _off_ | Print the manifest, the generated `cloudbuild.yaml`, and the rewritten script without writing the tempfile or running the script. |
| `--loglevel` | `info` | Log verbosity. |

## What gets created in your GCP project

The deploy script enables these APIs (if not already enabled):

- `cloudbuild.googleapis.com`
- `run.googleapis.com`
- `artifactregistry.googleapis.com`

It then creates (idempotently) and uses:

- An Artifact Registry Docker repository at `${REGION}-docker.pkg.dev/${GCP_PROJECT}/${AR_REPO}`.
- A Cloud Build job that builds and pushes the image.
- A Cloud Run service named `${SERVICE_NAME}`, deployed with `--allow-unauthenticated`, port 8080, 1 vCPU, 1 GiB memory, `--min-instances 1`, and `--session-affinity`.

Re-running the command pushes a new image tag and rolls the Cloud Run service forward.

## How the build runs

The generated `cloudbuild.yaml` is a single Cloud Build step that:

1. Writes the Dockerfile into the build workspace via a single-quoted heredoc:
    ```yaml
    - |
      cat > Dockerfile <<'REFLEX_DOCKERFILE_EOF'
      FROM python:3.13-slim
      ...
      REFLEX_DOCKERFILE_EOF
      docker build -t "$_IMAGE" .
      docker push "$_IMAGE"
    ```
2. Builds and pushes the image, tagging it with `_IMAGE` (passed to `gcloud builds submit` as `--substitutions=_IMAGE=...`).

Because Cloud Build runs its own substitution pass over `args`, every literal `$` in the Dockerfile is doubled to `$$` before embedding (e.g. `ENV PATH="${UV_PROJECT_ENVIRONMENT}/bin:$PATH"` becomes `ENV PATH="$${UV_PROJECT_ENVIRONMENT}/bin:$$PATH"` in the YAML). Cloud Build's parser converts `$$` back to `$` before bash runs, so the Dockerfile written into the workspace contains the original characters.

## Security model

The CLI runs the deploy script under a **restricted environment**. Only an explicit allowlist of host variables is forwarded to `bash` — things like `PATH`, `HOME`, `CLOUDSDK_*`, `DOCKER_*`, and proxy/TLS variables. Unrelated host secrets such as `AWS_*`, `GITHUB_TOKEN`, or arbitrary user variables are **not** forwarded, so a tampered or compromised manifest cannot exfiltrate them.

You can preview the rewritten script, generated `cloudbuild.yaml`, and Dockerfile before anything runs by using `--dry-run`:

```bash
reflex cloud deploy --gcp \
    --gcp-project my-gcp-project-id \
    --dry-run
```

## Non-interactive use (CI)

For automated pipelines, pass `--no-interactive` and an explicit `--token`:

```bash
reflex cloud deploy --gcp \
    --gcp-project "$GCP_PROJECT_ID" \
    --service-name my-reflex-app \
    --token "$REFLEX_TOKEN" \
    --no-interactive
```

In non-interactive mode the CLI will not prompt, and it will exit non-zero if a token cannot be resolved.

## Troubleshooting

**`Reflex denied the request (403). GCP Cloud Run deploys require an Enterprise tier subscription.`**
Your account is not on the Enterprise tier. Contact [sales@reflex.dev](mailto:sales@reflex.dev).

**`Billing must be enabled for activation of service(s) ...` (`UREQ_PROJECT_BILLING_NOT_FOUND`)**
Attach a billing account to the GCP project, or use a different `--gcp-project`.

**`The value of '--project' flag was set to Project number. To use this command, set it to PROJECT ID instead.`**
Pass the project ID (e.g. `my-app-123456`), not the numeric project number.

**`No active GCP account found.`**
Run `gcloud auth login` and `gcloud auth application-default login`.

**`The 'gcloud' / 'docker' / 'bash' CLI was not found on PATH.`**
Install the missing tool and ensure it's on `PATH` for the shell you're invoking the CLI from.

**`Dockerfile content contains the reserved heredoc marker 'REFLEX_DOCKERFILE_EOF'.`**
Vanishingly unlikely — the Dockerfile from Reflex Cloud happens to contain a line that exactly matches the heredoc terminator the CLI uses to embed it. Re-run after the next CLI release, or open an issue.

**`Couldn't find 'gcloud builds submit' in the deploy script.`**
The CLI rewrites the `gcloud builds submit` block in the Reflex-supplied deploy script to use `--config=`. If Reflex Cloud changes the shape of that script before the CLI is updated to match, you'll see this error — upgrade `reflex-hosting-cli` (`uv tool upgrade reflex-hosting-cli` or `pip install -U reflex-hosting-cli`).
