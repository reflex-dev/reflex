```python exec
import reflex as rx
```

# Cloud Config File

## Create `cloud.yml`

Run:

```bash
reflex cloud config
```

The command creates `cloud.yml`, which defines how Reflex Cloud should deploy the app.

## File structure

Every field is optional:

```yaml
# Basic deployment settings
name: my-app-prod                    # Optional: defaults to project folder name
description: 'Production deployment' # Optional: empty by default
projectname: my-client-project          # Optional: defaults to personal project

# Infrastructure settings
regions:                            # Optional: defaults to sjc: 1
  sjc: 1                           # San Jose (# of machines)
  lhr: 2                           # London (# of machines)
vmtype: c2m2                       # Optional: defaults to c1m1

# Custom domain and environment
hostname: myapp                    # Optional: myapp.reflex.dev
envfile: .env.production           # Optional: defaults to .env

# Google Cloud (Enterprise, requires a connected GCP account)
provider: gcp                      # Optional: defaults to reflex-cloud
gcp_connection: eu-prod            # Optional: omit to keep the app's current connection
full_deploy: true                  # Optional: omit to leave the app's hosting mode unchanged

# Additional dependencies
packages:                          # Optional: empty by default
  - procps
```

## Options reference

```python demo-only
rx.table.root(
    rx.table.header(
        rx.table.row(
            rx.table.column_header_cell(
                rx.text("Option", size="1", weight="bold", color=rx.color("slate", 11))
            ),
            rx.table.column_header_cell(
                rx.text("Type", size="1", weight="bold", color=rx.color("slate", 11))
            ),
            rx.table.column_header_cell(
                rx.text("Default", size="1", weight="bold", color=rx.color("slate", 11))
            ),
            rx.table.column_header_cell(
                rx.text(
                    "Description", size="1", weight="bold", color=rx.color("slate", 11)
                )
            ),
            align="center",
        )
    ),
    rx.table.body(*[
        rx.table.row(
            rx.table.cell(rx.text(option, class_name="text-sm")),
            rx.table.cell(rx.text(type_, class_name="text-sm")),
            rx.table.cell(rx.text(default, class_name="text-sm")),
            rx.table.cell(
                rx.link(description, href=link, class_name="text-sm")
                if link
                else rx.text(description, size="1", weight="regular")
            ),
            align="center",
        )
        for option, type_, default, description, link in [
            (
                "name",
                "string",
                "folder name",
                "Deployment identifier in dashboard",
                None,
            ),
            ("description", "string", "empty", "Description of deployment", None),
            (
                "regions",
                "object",
                "sjc: 1",
                "Region deployment mapping",
                "/hosting/regions",
            ),
            (
                "vmtype",
                "string",
                "c1m1",
                "Virtual machine specifications",
                "/hosting/machine-types",
            ),
            ("hostname", "string", "null", "Custom subdomain", None),
            (
                "envfile",
                "string",
                ".env",
                "Environment variables file path",
                "/hosting/secrets-environment-vars",
            ),
            ("project", "uuid", "null", "Project uuid", None),
            ("projectname", "string", "null", "Project name", None),
            ("packages", "array", "empty", "Additional system packages", None),
            ("include_db", "boolean", "false", "Include local sqlite", None),
            ("strategy", "string", "auto", "Deployment strategy", None),
            (
                "provider",
                "string",
                "reflex-cloud",
                "Where the app deploys: reflex-cloud or gcp",
                None,
            ),
            (
                "gcp_connection",
                "string",
                "unset",
                "Connected GCP account to deploy through (see below)",
                None,
            ),
            (
                "full_deploy",
                "boolean",
                "unset",
                "Serve the frontend from the GCP container (see below)",
                None,
            ),
        ]
    ]),
    variant="ghost",
    size="2",
    width="100%",
    max_width="800px",
)
```

## Configuration details

### Projects

Organize deployments using projects:

```yaml
projectname: client-alpha    # Groups related deployments
```

You can also specify a project uuid instead of name:
```yaml
project: 12345678-1234-1234-1234-1234567890ab
```

Copy the project ID from the project's settings in Reflex Build.

### Apt Packages

Install additional system packages your application requires. Package names are based on the apt package manager:

```yaml
packages:
  - procps=2.0.32-1  # Version pinning is optional
  - imagemagick 
  - ffmpeg      
```

### Include SQLite

Include local sqlite database:

```yaml
include_db: true
```

This database is not persistent and is lost when the app restarts. Use a database service for production data.

### Strategy

Deployment strategy:
Available strategies:
- `immediate`: [Default] Deploy immediately
- `rolling`: Deploy in a rolling manner
- `bluegreen`: Deploy in a blue-green manner
- `canary`: Deploy in a canary manner, boot as single machine verify its health and then restart the rest.

```yaml
strategy: immediate
```

### Google Cloud

Deploy to a Google Cloud account connected to your organization instead of
Reflex Cloud. Requires the Enterprise tier and a GCP account connected under
Organization → Cloud Providers.

```yaml
provider: gcp
```

An organization can connect more than one GCP account. Name which one an app
deploys through:

```yaml
gcp_connection: eu-prod
```

Run `reflex cloud providers connections` to list the connections available to
you, with the project, region and runtime service account of each.

Leaving `gcp_connection` unset keeps the app on the connection it already uses.
An app that has never deployed to GCP has no connection yet, so for that first
deploy the unset value means your organization's default connection — which is
why the options table above lists no fixed default. A connection can only be
changed before the app has been deployed; afterwards, switch providers instead
so the old project is torn down properly.

Two settings are ignored on this target: `regions` (the region comes from the
connected account) and `hostname`. `vmtype` is honored — it maps onto Cloud Run
CPU and memory limits.

### Full deploy

By default a GCP-deployed app serves its frontend from Reflex's CDN. In full
deploy mode the frontend is bundled into the GCP container and served on the
same origin as the backend, so the whole app runs in your cloud account:

```yaml
full_deploy: true
```

GCP only, Enterprise tier, and incompatible with a custom domain or multiple
environments. Leaving `full_deploy` unset leaves the app's hosting mode
unchanged — it is deliberately three-valued, so a config file that never
mentions it does not switch an app out of full deploy. Changing the mode stops
a running app so the next deploy brings it back up in the new one, and its
earlier deployments stop being rollback targets: they were built for the mode
it left.

## Multi-Environment Setup

**Development (`cloud-dev.yml`):**
```yaml
name: myapp-dev
description: 'Development environment'
vmtype: c1m1
envfile: .env.development
```

**Staging (`cloud-staging.yml`):**
```yaml
name: myapp-staging
description: 'Staging environment'
regions:
  sjc: 1
vmtype: c2m2
envfile: .env.staging
```

**Production (`cloud-prod.yml`):**
```yaml
name: myapp-production
description: 'Production environment'
regions:
  sjc: 2
  lhr: 1
vmtype: c4m4
hostname: myapp
envfile: .env.production
```

Deploy with specific configuration files:

```bash
# Use default cloud.yml
reflex deploy

# Use specific configuration file
reflex deploy --config cloud-prod.yml
reflex deploy --config cloud-staging.yml
```
