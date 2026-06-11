# Bring Your Own Cloud

Bring Your Own Cloud (BYOC) lets you deploy Reflex apps to your own **AWS**, **GCP**, or **Azure** account with the same `reflex cloud deploy` command you already use. Everything runs inside your account: the build runs on your cloud's builders, the image is pushed to your internal registry, and the app runs on your cloud's managed runtime. Reflex never holds standing credentials into your account, and nothing about the app or its data leaves your perimeter.

```md alert info
# Enterprise tier only.

BYOC is part of the **Enterprise tier** of Reflex Cloud. Contact [sales@reflex.dev](mailto:sales@reflex.dev) to upgrade.
```

## Why BYOC

Reflex Cloud takes you from a Python file to a live app in one command, but that app runs on Reflex's infrastructure — a non-starter for teams whose cloud is fixed by security review, procurement, or data-residency policy. If the deployment target isn't approved, the app doesn't ship.

The alternative is to build the deploy yourself on Cloud Run, ECS, or Container Apps: a Dockerfile, a build pipeline, a registry, runtime config, infrastructure-as-code, and ongoing maintenance. That's its own engineering project, and most of it has nothing to do with your app.

BYOC keeps the Reflex Cloud workflow your team already uses — app lifecycle, autoscaling, environment variables, and the deploy CLI all behave the way they always have. The only thing that changes is where the container ends up running.

## Deploy targets

The same `reflex cloud deploy` command works against each cloud with a single flag:

```bash
reflex cloud deploy --aws
reflex cloud deploy --gcp
reflex cloud deploy --azure
```

| Cloud | Flag | Managed runtime |
| --- | --- | --- |
| AWS | `--aws` | ECS |
| GCP | `--gcp` | Cloud Run |
| Azure | `--azure` | Container Apps |

## How the deploy command works

Running `reflex cloud deploy --<cloud>` kicks off a short interactive flow:

1. **Authenticate.** The CLI checks that your cloud's own CLI (`aws`, `gcloud`, or `az`) is installed and that you're logged in, and walks you through `aws configure`, `gcloud auth login`, or `az login` if you're not. From there everything runs under your credentials.
2. **Configure.** It pulls the latest Reflex Cloud config for your app and prompts you for any flags it needs.
3. **Review.** Before anything runs, it prints the exact build and deploy commands it's about to execute and asks for approval.
4. **Deploy.** On approval, it builds the container image with your cloud's native builders, pushes it to your internal artifact registry, and deploys the app to the managed runtime.

The final output is the URL of the live app, running in your own account. The whole flow takes about three minutes the first time, and under a minute on subsequent deploys.

## What's in scope today

BYOC is generally available on AWS, GCP, and Azure for Reflex Enterprise customers. It supports:

- Reflex apps on Cloud Run, ECS, and Container Apps
- Authentication through your existing cloud CLI
- The standard set of Reflex Cloud configuration flags

## Next steps

- For a detailed walkthrough of the GCP target — prerequisites, options, the security model, and troubleshooting — see [Deploy to GCP Cloud Run](/docs/hosting/deploy-to-gcp/).
- If you're on Reflex Enterprise, update the CLI and run `reflex cloud deploy --<cloud>`.
- If you're not, see [reflex.dev/pricing](https://reflex.dev/pricing/) for the comparison and a demo link.
