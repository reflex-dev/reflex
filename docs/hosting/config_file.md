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
                "/docs-preview/hosting/regions",
            ),
            (
                "vmtype",
                "string",
                "c1m1",
                "Virtual machine specifications",
                "/docs-preview/hosting/machine-types",
            ),
            ("hostname", "string", "null", "Custom subdomain", None),
            (
                "envfile",
                "string",
                ".env",
                "Environment variables file path",
                "/docs-preview/hosting/secrets-environment-vars",
            ),
            ("project", "uuid", "null", "Project uuid", None),
            ("projectname", "string", "null", "Project name", None),
            ("packages", "array", "empty", "Additional system packages", None),
            ("include_db", "boolean", "false", "Include local sqlite", None),
            ("strategy", "string", "auto", "Deployment strategy", None),
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
