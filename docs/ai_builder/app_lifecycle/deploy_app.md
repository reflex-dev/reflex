# Deploy App

Deploying publishes the current app to Reflex Cloud or to a connected cloud provider.

```python exec
import reflex as rx
```

## Deploy from the Builder

1. Open the app and wait for the current generation to finish.
2. Select **Deploy** in the upper-right corner.
3. Review the workspace resource check and deployment configuration.
4. Confirm the deployment.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/hosting/builder_deploy_dialog.webp",
    alt="Deploy dialog with hosting provider choices in Reflex Build",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

If the app needs more memory than the active workspace provides, the dialog recommends a larger workspace before deployment. Upgrading the workspace can prevent build failures; deploy anyway only when you understand the resource requirement.

Depending on your plan and organization configuration, the deployment flow can include:

- App name and generated hostname.
- Hosting provider.
- Region and machine size.
- App secrets and environment variables.
- A deployment approval request.

## Project Approvals

When **Require approval to deploy** is enabled for the project, the deployment waits in the **Approvals** queue. It runs automatically after a member with **Approve deployments** permission approves it. See [Project Approvals](/docs/ai/organization/deployment-approvals/).

## After Deployment

Open **Deployments** in the project sidebar to view status, resource allocation, logs, history, domains, and settings. See the [Reflex Cloud quick start](/docs/hosting/deploy-quick-start/) for the current dashboard and CLI workflows.
