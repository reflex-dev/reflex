```python exec
from pcweb.pages import docs
import reflex as rx
from pcweb.styles.styles import get_code_style, cell_style

github_actions_configs = [
    {
        "name": "auth_token",
        "description": "Reflex authentication token stored in GitHub Secrets.",
        "required": True,
        "default": "N/A"
    },
    {
        "name": "project_id",
        "description": "The ID of the project you want to deploy to.",
        "required": True,
        "default": "N/A"
    },
    {
        "name": "app_directory",
        "description": "The directory containing your Reflex app.",
        "required": False,
        "default": ". (root)"
    },
    {
        "name": "extra_args",
        "description": "Additional arguments to pass to the `reflex deploy` command.",
        "required": False,
        "default": "N/A"
    },
    {
        "name": "python_version",
        "description": "The Python version to use for the deployment environment.",
        "required": False,
        "default": "3.12"
    }
]
```

# Deploy with Github Actions

This GitHub Action simplifies the deployment of Reflex applications to Reflex Cloud. It handles setting up the environment, installing the Reflex CLI, and deploying your app with minimal configuration.

```md alert info
# This action requires `reflex>=0.6.6`
```

**Features:**
- Deploy Reflex apps directly from your GitHub repository to Reflex Cloud.
- Supports subdirectory-based app structures.
- Securely uses authentication tokens via GitHub Secrets.

## Usage
### Add the Action to Your Workflow
Create a `.github/workflows/deploy.yml` file in your repository and add the following:

```yaml
name: Deploy Reflex App

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Reflex Cloud
        uses: reflex-dev/reflex-deploy-action@v1
        with:
          auth_token: ${\{ secrets.REFLEX_PROJECT_ID }}
          project_id: ${\{ secrets.REFLEX_PROJECT_ID }}
          app_directory: "my-app-folder" # Optional, defaults to root
          extra_args: "--env THIRD_PARTY_APIKEY=***" # Optional
          python_version: "3.12" # Optional
```

### Set Up Your Secrets
Store your Reflex authentication token securely in your repository's secrets:


1. Go to your GitHub repository.
2. Navigate to Settings > Secrets and variables > Actions > New repository secret.
3. Create new secrets for `REFLEX_AUTH_TOKEN` and `REFLEX_PROJECT_ID`. 

(Create a `REFLEX_AUTH_TOKEN` in the tokens tab of your UI, check out these [docs]({docs.hosting.tokens.path}#tokens). 

The `REFLEX_PROJECT_ID` can be found in the UI when you click on the How to deploy button on the top right when inside a project and copy the ID after the `--project` flag.)



### Inputs

```python eval
rx.table.root(
    rx.table.header(
        rx.table.row(
            rx.table.column_header_cell("Name"),
            rx.table.column_header_cell("Description"),
            rx.table.column_header_cell("required"),
            rx.table.column_header_cell("Default"),
        ),
    ),
    rx.table.body(
        *[
            rx.table.row(
                rx.table.cell(rx.code(github_config["name"], style=get_code_style("violet"))),
                rx.table.cell(github_config["description"], style=cell_style),
                rx.table.cell(rx.code(github_config["required"], style=get_code_style("violet"))),
                rx.table.cell(rx.code(github_config["default"], style=get_code_style("violet")), min_width="100px"),
            )
            for github_config in github_actions_configs
        ]
    ),
    variant="surface",
)
```
