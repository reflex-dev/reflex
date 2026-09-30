# Cloud Providers

By default, `reflex deploy` runs your app on Reflex Cloud's managed infrastructure. If your organization has connected its own cloud account, you can instead deploy the same app — with the same `reflex deploy` command and the same managed lifecycle (logs, scaling, history, rollbacks) — into **your own cloud account**. Today this is supported for **Google Cloud (GCP)**, where your app runs on [Cloud Run](https://cloud.google.com/run) in your GCP project.

```md alert info
# Enterprise tier only.

Deploying to a connected cloud provider is part of the **Enterprise tier** of Reflex Cloud. Contact [sales@reflex.dev](mailto:sales@reflex.dev) to upgrade.
```

```md alert warning
# Managed vs. self-service GCP deploys

This page covers the **managed** flow: an admin connects a GCP account to your organization once, and Reflex Cloud deploys into it for you using the normal `reflex deploy` command, giving you the full managed lifecycle (history, rollback, scaling, logs). This is different from the self-service [`reflex cloud deploy --gcp`](/docs/hosting/deploy-to-gcp/) command, which builds and deploys from your own machine using your local `gcloud`.
```

## Connecting Google Cloud

An organization admin connects the GCP account from **Cloud Providers** in the organization sidebar. See [Bring Your Own Cloud](/docs/ai/organization/cloud-providers/) for the setup, credential, and removal steps.

After it is connected, check availability from the CLI:

```bash
reflex cloud providers status
```

This reports whether GCP is connected, whether your plan allows GCP deploys, and the connected project and region. List all connected provider accounts with:

```bash
reflex cloud providers list
```

## Choosing a provider at deploy time

When your org has GCP connected, `reflex deploy` asks where you want to deploy:

```console
$ reflex deploy
This organization has Google Cloud connected (region us-central1).
Where would you like to deploy? [reflex-cloud/gcp] (reflex-cloud):
```

Choose `reflex-cloud` for Reflex's managed infrastructure or `gcp` for your connected Google Cloud account. To skip the prompt (for example in CI), pass `--provider`:

```bash
reflex deploy --provider gcp
reflex deploy --provider reflex-cloud
```

You can also pin the provider in your `cloud.yml` / `pyproject.toml` so every deploy targets the same place:

```yaml
provider: gcp
```

When you deploy to GCP, the region and machine sizing come from the connected GCP account, so `--region` and `--vmtype` are ignored.

## Switching providers

An app remembers its provider between deploys. Choose a different provider on the next `reflex deploy`, or pass `--provider`, to switch it.

Switching a deployed app removes its resources from the previous provider and redeploys it to the new one. In interactive mode, the CLI shows a warning and asks for confirmation first.

## What runs where

| | Reflex Cloud | Google Cloud (managed) |
| --- | --- | --- |
| Runtime | Reflex-managed | Cloud Run in your GCP project |
| Compute billing | Reflex Cloud | Your GCP account |
| Region / sizing | `--region` / `--vmtype` | From the connected GCP account |
| Logs, history, rollback, scaling | ✅ | ✅ |

Deployment descriptions and rollbacks work the same way on both providers — see [App management](/docs/hosting/app-management/).
