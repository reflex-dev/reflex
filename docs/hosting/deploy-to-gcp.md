```python exec
import reflex as rx
```

# Deploy to GCP Cloud Run

The `reflex cloud deploy --gcp` command deploys a Reflex app to your own [Google Cloud Run](https://cloud.google.com/run) service.

The CLI fetches a Cloud Run-ready Dockerfile and deploy script, then submits the build through [Cloud Build](https://cloud.google.com/build/docs/build-config-file-schema). Google Cloud stores the image in Artifact Registry and runs it on Cloud Run. The temporary deployment files do not modify your project tree.

```md alert info
# Enterprise tier only
Self-deploying to GCP Cloud Run is part of the **Enterprise tier** of Reflex Cloud. Contact [sales@reflex.dev](mailto:sales@reflex.dev) to upgrade.
```

```md alert warning
# Self-service vs. managed GCP deploys

This page covers the **self-service** `reflex cloud deploy --gcp` command, which builds and deploys from your own machine using your local `gcloud`. If you'd rather connect a GCP account to your organization once and deploy with the normal `reflex deploy` command — keeping the managed lifecycle (history, rollback, scaling, logs) — see [Cloud Providers](/docs/hosting/cloud-providers/).
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
- Permission to manage Secret Manager secrets in the project (`roles/secretmanager.admin`), so the CLI can stage your access token for the build. Without it the deploy continues with a warning, and only apps using `reflex-enterprise` fail — see [Passing the Reflex access token to the build](#passing-the-reflex-access-token-to-the-build).

## Quick start

From the root of your Reflex app:

```bash
reflex cloud deploy --gcp \
    --gcp-project my-gcp-project-id \
    --service-name my-reflex-app
```

The CLI will:

1. Authenticate with Reflex Cloud and fetch the deployment files.
2. Create a temporary `cloudbuild.yaml`.
3. Print the commands for review.
4. Ask for confirmation, then stage your access token in Secret Manager for the build, enable the required APIs, create the Artifact Registry repository, build the image, and deploy the Cloud Run service.
5. Delete the temporary file and destroy the staged token version.

An existing `Dockerfile` in `--source` remains unchanged and is not used by this workflow.

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
| `--build-token / --no-build-token` | `--build-token` | Whether to make the Reflex access token available to the image build. Needed by `reflex export` for apps that use `reflex-enterprise`. |
| `--token-secret` | `reflex-access-token` | Secret Manager secret the access token is staged in. Pass a full version resource to reference a secret you manage yourself. |
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
- A Secret Manager secret named `reflex-access-token` (labelled `managed-by=reflex-cli`), holding the access token for the duration of the build. See [Passing the Reflex access token to the build](#passing-the-reflex-access-token-to-the-build).

Re-running the command pushes a new image tag and rolls the Cloud Run service forward.

## How the build runs

The generated `cloudbuild.yaml` is a single Cloud Build step that:

1. Writes the Dockerfile into the build workspace via a single-quoted heredoc:
    ```yaml
    - |
      set -e
      cat > Dockerfile <<'REFLEX_DOCKERFILE_EOF'
      FROM python:3.13-slim
      ...
      REFLEX_DOCKERFILE_EOF
      docker build -t "$_IMAGE" .
      docker push "$_IMAGE"
    ```
2. Builds and pushes the image, tagging it with `_IMAGE` (passed to `gcloud builds submit` as `--substitutions=_IMAGE=...`).

Because Cloud Build runs its own substitution pass over `args`, every literal `$` in the Dockerfile is doubled to `$$` before embedding (e.g. `ENV PATH="${UV_PROJECT_ENVIRONMENT}/bin:$PATH"` becomes `ENV PATH="$${UV_PROJECT_ENVIRONMENT}/bin:$$PATH"` in the YAML). Cloud Build's parser converts `$$` back to `$` before bash runs, so the Dockerfile written into the workspace contains the original characters.

## Passing the Reflex access token to the build

The image build runs `reflex export --frontend-only`. For apps that use `reflex-enterprise`, the export refuses to run without a Reflex access token:

```text
`reflex-enterprise` is free to use but you must be logged in. Run `reflex login`
or set the environment variable REFLEX_ACCESS_TOKEN with your token.
```

The build runs inside Cloud Build, not on your machine, so the CLI hands the token over explicitly:

1. It stages the token as a **new Secret Manager version** in your project (creating the secret, enabling `secretmanager.googleapis.com`, and granting the Cloud Build service account `roles/secretmanager.secretAccessor` on that one secret, if needed).
2. The generated `cloudbuild.yaml` references that version by resource name under `availableSecrets`, and Cloud Build injects the value into the step as `REFLEX_ACCESS_TOKEN`:
    ```yaml
    availableSecrets:
      secretManager:
        - versionName: projects/my-project/secrets/reflex-access-token/versions/4
          env: REFLEX_ACCESS_TOKEN
    ```
3. The step writes the value outside the build context and passes it to `docker build` as a [BuildKit secret](https://docs.docker.com/build/building/secrets/), which the export step mounts at `/run/secrets/reflex_access_token`:
    ```dockerfile
    RUN --mount=type=secret,id=reflex_access_token,mode=0444 \
        if [ -s /run/secrets/reflex_access_token ]; then export REFLEX_ACCESS_TOKEN="$(cat /run/secrets/reflex_access_token)"; fi; \
        uv run reflex export --frontend-only ...
    ```
4. When the deploy finishes — successfully or not — the CLI **destroys the staged version**.

This keeps the token out of every durable location it would otherwise leak into: the build config and its substitutions (readable with `roles/cloudbuild.builds.viewer`), the build logs, the uploaded source, and the image layers and `docker history` of the image pushed to Artifact Registry.

To use a secret you manage yourself, pass its full version resource. The CLI then only reads it — no secret is created, no version is added or destroyed — and you grant the Cloud Build service account access:

```bash
reflex cloud deploy --gcp \
    --gcp-project my-gcp-project-id \
    --token-secret projects/my-gcp-project-id/secrets/my-reflex-token/versions/latest
```

Pass `--no-build-token` to skip all of the above. Apps that don't use `reflex-enterprise` export fine without a token.

## Security model

The CLI runs the deploy script under a **restricted environment**. Only an explicit allowlist of host variables is forwarded to `bash` — things like `PATH`, `HOME`, `CLOUDSDK_*`, `DOCKER_*`, and proxy/TLS variables. Unrelated host secrets such as `AWS_*`, `GITHUB_TOKEN`, or arbitrary user variables are **not** forwarded, so a tampered or compromised manifest cannot exfiltrate them. `REFLEX_ACCESS_TOKEN` is not forwarded either: the token reaches the build only through Secret Manager, and only as a BuildKit secret mounted for the export step.

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

**`reflex-enterprise` is free to use but you must be logged in.` during `Step .../...: RUN uv run reflex export`**
The build ran without an access token. Check the CLI output above the build for a warning explaining why: it couldn't create the Secret Manager secret, couldn't grant the Cloud Build service account access to it, or `--no-build-token` was passed. Granting the deploying principal `roles/secretmanager.admin` (or pre-creating the secret and passing `--token-secret`) resolves the first two.

**`Couldn't grant the Cloud Build service account roles/secretmanager.secretAccessor`**
The deploy continues, and the build only fails if the service account has no other path to the secret. Grant it yourself with the `gcloud secrets add-iam-policy-binding` command from the warning; builds use either `PROJECT_NUMBER@cloudbuild.gserviceaccount.com` or `PROJECT_NUMBER-compute@developer.gserviceaccount.com` depending on when the project was created.

**`unknown flag: --secret` or `the --mount option requires BuildKit`**
The Cloud Build worker's Docker predates BuildKit secret support. Deploy with `--no-build-token` (your app then has to export without a Reflex token) and let us know at [support@reflex.dev](mailto:support@reflex.dev).
