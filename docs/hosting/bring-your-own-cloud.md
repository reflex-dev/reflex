# Bring Your Own Cloud

Bring Your Own Cloud (BYOC) deploys a Reflex app to your own AWS, Google Cloud, or Azure account. The command uses your local cloud credentials to build the image, store it in your registry, and run it on the cloud's managed container service.

```md alert info
# Enterprise tier only
BYOC is part of the **Enterprise tier** of Reflex Cloud. Contact [sales@reflex.dev](mailto:sales@reflex.dev) to upgrade.
```

## Deployment targets

| Cloud | Command | Runtime |
| --- | --- | --- |
| AWS | `reflex cloud deploy --aws` | ECS |
| Google Cloud | `reflex cloud deploy --gcp --gcp-project <GCP_PROJECT_ID>` | Cloud Run |
| Azure | `reflex cloud deploy --azure` | Container Apps |

## Before you deploy

- Sign in to Reflex with `reflex login`.
- Install the cloud provider's CLI: `aws`, `gcloud`, or `az`.
- For Google Cloud, install Docker and Bash in addition to `gcloud`.
- Sign in to the target cloud account with that CLI.
- Confirm that the account can create builds, registry images, and managed container services.

## Run the deployment

Run the command for your provider. The CLI:

1. Checks the provider CLI and your current login.
2. Loads the Reflex deployment configuration and validates the required command options.
3. Shows the build and deploy commands for confirmation.
4. Uses the provider's build service and registry, then deploys the container.
5. Prints the deployed app URL.

The deployment runs under your cloud identity. Review the displayed commands and selected account before confirming.

For Google Cloud, pass the target project explicitly:

```bash
reflex cloud deploy --gcp --gcp-project <GCP_PROJECT_ID>
```

```md alert warning
# Self-service and managed cloud connections are different
This page covers self-service CLI deployments to AWS, Google Cloud, and Azure. An organization admin can also connect Google Cloud to Reflex for managed deployments with logs, history, rollback, and scaling in the Reflex dashboard. See [Cloud Providers](/docs/hosting/cloud-providers/).
```

## Next steps

- [Deploy to Google Cloud Run](/docs/hosting/deploy-to-gcp/) covers Google Cloud prerequisites, options, and troubleshooting.
- [Cloud Providers](/docs/hosting/cloud-providers/) covers the managed Google Cloud connection.
