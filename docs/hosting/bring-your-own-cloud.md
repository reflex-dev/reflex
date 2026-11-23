# Bring Your Own Cloud

Bring Your Own Cloud (BYOC) deploys a Reflex app into your own cloud account instead of Reflex-managed infrastructure. Google Cloud is the supported target: the `reflex cloud gcp-standalone` command uses your local `gcloud` credentials to build the image with Cloud Build, store it in Artifact Registry, and run it on Cloud Run.

```md alert info
# Enterprise tier only
BYOC is part of the **Enterprise tier** of Reflex Cloud. Contact [sales@reflex.dev](mailto:sales@reflex.dev) to upgrade.
```

## Deployment targets

| Cloud | Command | Runtime |
| --- | --- | --- |
| Google Cloud | `reflex cloud gcp-standalone --gcp --gcp-project <GCP_PROJECT_ID>` | Cloud Run |

The CLI has no AWS or Azure target. To run a Reflex app on those clouds, follow [Self Hosting](/docs/hosting/self-hosting/).

## Before you deploy

- Sign in to Reflex with `reflex login`.
- Install `gcloud`, Docker, and Bash.
- Sign in with `gcloud auth login` and `gcloud auth application-default login`.
- Confirm that the project has billing enabled and that your account can enable services, push to Artifact Registry, and deploy Cloud Run services.

## Run the deployment

From the root of your Reflex app, pass the target project explicitly:

```bash
reflex cloud gcp-standalone --gcp --gcp-project <GCP_PROJECT_ID>
```

The CLI:

1. Checks for `bash`, `gcloud`, and `docker` and authenticates with Reflex.
2. Fetches the Dockerfile and deploy script and generates a temporary `cloudbuild.yaml`.
3. Shows the commands for confirmation.
4. Builds the image with Cloud Build, pushes it to Artifact Registry, and deploys the Cloud Run service.
5. Prints the deployed service URL.

The deployment runs under your Google Cloud identity, and Reflex Cloud does not record the resulting app. Review the displayed commands and selected project before confirming.

```md alert warning
# Self-service and managed cloud connections are different
This page covers self-service CLI deployments to Google Cloud. An organization admin can also connect Google Cloud to Reflex so `reflex deploy --provider gcp` deploys into it with logs, history, rollback, and scaling in the Reflex dashboard. See [Cloud Providers](/docs/hosting/cloud-providers/).
```

## Next steps

- [Deploy to Google Cloud Run](/docs/hosting/deploy-to-gcp/) covers Google Cloud prerequisites, options, and troubleshooting.
- [Cloud Providers](/docs/hosting/cloud-providers/) covers the managed Google Cloud connection.
