```python exec
import reflex as rx
```

# Compute

## How compute usage works

Reflex Cloud measures compute while an app instance is running. Usage depends on:

- The selected [machine size](/docs/hosting/machine-types/).
- The number of [regions](/docs/hosting/regions/) in the deployment.
- How long each instance runs.

An app can become idle when it has no active users. Idle instances do not accrue compute usage and wake when the app receives another request.

Compute is based on instance runtime, not the number of people using the app. For example, one instance running for an hour uses the same compute time whether it serves one person or several people during that hour.

## Persistent machines

The deployment form may show a disabled **Persistent Machine** option. This feature is not available yet. When disabled, Reflex manages app instances and can scale them down when idle.

## Monitor usage

Open **Usage** in the organization sidebar, then select **Cloud** to review deployment usage. Choose a project and app to narrow the charts. Select an app-region series in a chart legend to show or hide it.

See [Billing](/docs/hosting/billing/) for how compute and seats contribute to billing.
