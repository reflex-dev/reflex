```python exec
import reflex as rx

code_style = {
    "color": rx.color("violet", 11),
    "border_radius": "0.25rem",
    "border": f"1px solid {rx.color('violet', 5)}",
    "background": rx.color("violet", 3),
}

cell_style = {
    "font_family": "Instrument Sans",
    "font_style": "normal",
    "font_weight": "500",
    "font_size": "14px",
    "line_height": "1.5",
    "letter_spacing": "-0.0125em",
    "color": "var(--secondary-11)",
}

github_actions_configs = [
    {
        "name": "auth_token",
        "description": "Reflex authentication token stored in GitHub Secrets.",
        "required": True,
        "default": "N/A",
    },
    {
        "name": "project_id",
        "description": "The ID of the project you want to deploy to.",
        "required": True,
        "default": "N/A",
    },
    {
        "name": "app_directory",
        "description": "The directory containing your Reflex app.",
        "required": False,
        "default": ". (root)",
    },
    {
        "name": "extra_args",
        "description": "Additional arguments to pass to the `reflex deploy` command.",
        "required": False,
        "default": "N/A",
    },
    {
        "name": "python_version",
        "description": "The Python version to use for the deployment environment.",
        "required": False,
        "default": "3.12",
    },
]
```

# Deploy with GitHub Actions

Use the Reflex deploy action to deploy an app to Reflex Cloud from a GitHub Actions workflow.

```md alert info
# This action requires `reflex>=0.6.6`
```

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
          auth_token: ${{ secrets.REFLEX_AUTH_TOKEN }}
          project_id: ${{ secrets.REFLEX_PROJECT_ID }}
          app_directory: "my-app-folder" # Optional, defaults to root
          extra_args: "--region sjc" # Optional
          python_version: "3.12" # Optional
```

### Set Up Your Secrets

Store the Reflex authentication token and project ID as GitHub repository secrets:

1. Go to your GitHub repository.
2. Open **Settings > Secrets and variables > Actions**.
3. From the organization's **Tokens** page, create a token from the **Deploy** template and limit it to the target project. Store it as `REFLEX_AUTH_TOKEN`. See [Tokens](/docs/hosting/tokens/).
4. Create `REFLEX_PROJECT_ID` with the project ID copied from the project's settings in Reflex Build.

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
    rx.table.body(*[
        rx.table.row(
            rx.table.cell(rx.code(github_config["name"], style=code_style)),
            rx.table.cell(github_config["description"], style=cell_style),
            rx.table.cell(rx.code(github_config["required"], style=code_style)),
            rx.table.cell(
                rx.code(github_config["default"], style=code_style), min_width="100px"
            ),
        )
        for github_config in github_actions_configs
    ]),
    variant="surface",
)
```
