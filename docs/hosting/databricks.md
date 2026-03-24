```python exec
import reflex as rx
from pcweb import constants
from pcweb.styles.styles import get_code_style, cell_style

```

# Deploy Reflex to Databricks

This guide walks you through deploying a Reflex web application on Databricks using the Apps platform.

## Prerequisites

- Databricks workspace with Unity Catalog enabled
- GitHub repository containing your Reflex application
- Reflex Enterprise license (for single-port deployment)

## Step 1: Connect Your Repository

1. **Link GitHub Repository**
   - Navigate to your Databricks workspace
   - Go to your user directory
   - Click **Create** → **Git folder**
   - Paste the URL of your GitHub repository containing the Reflex application

## Step 2: Configure Application Settings

### Create Configuration File

Create a new file called `app.yaml` directly in Databricks (not in GitHub):

```yaml
command: [
  "reflex", 
  "run",
  "--env",
  "prod",
  "--backend-port",
  "$DATABRICKS_APP_PORT"
]

env:
  - name: "HOME"
    value: "/tmp/reflex"
  - name: "REFLEX_ACCESS_TOKEN"
    value: "your-token-here"
  - name: "DATABRICKS_WAREHOUSE_ID"
    value: "your-sql-warehouse-id"
  - name: "DATABRICKS_CATALOG"
    value: "your-catalog-name"
  - name: "DATABRICKS_SCHEMA"
    value: "your-schema-name"
  - name: "REFLEX_SHOW_BUILT_WITH_REFLEX"
    value: 0
```

### Obtain Required Tokens

1. **Reflex Access Token**
   - Visit [Reflex Cloud Tokens]({constants.REFLEX_CLOUD_URL.rstrip("/")}/tokens/)
   - Navigate to Account Settings → Tokens
   - Create a new token and copy the value
   - Replace `your-token-here` in the configuration
2. **Databricks Resources**
   - Update `DATABRICKS_WAREHOUSE_ID` with your SQL warehouse ID
   - Update `DATABRICKS_CATALOG` with your target catalog name
   - Update `DATABRICKS_SCHEMA` with your target schema name

## Step 3: Enable Single-Port Deployment

Update your Reflex application for Databricks compatibility:

### Update rxconfig.py

```python
import reflex as rx
import reflex_enterprise as rxe

rxe.Config(app_name="app", use_single_port=True)
```

### Update Application Entry Point

Modify your main application file where you define `rx.App`:

```python
import reflex_enterprise as rxe

app = rxe.App(
    # your app configuration
)
```

```md alert info
# Also add  `reflex-enterprise` and `asgiproxy`  to your `requirements.txt` file.
```

## Step 4: Create Databricks App

1. **Navigate to Apps**
   - Go to **Compute** → **Apps**
   - Click **Create App**
2. **Configure Application**
   - Select **Custom App**
   - Configure SQL warehouse for your application

## Step 5: Set Permissions

If you are using the `samples` Catalog then you can skip the permissions section.

### Catalog Permissions

1. Navigate to **Catalog** → Select your target catalog
2. Go to **Permissions**
3. Add the app's service principal user
4. Grant the following permissions:
   - **USE CATALOG**
   - **USE SCHEMA**

### Schema Permissions

1. Navigate to the specific schema
2. Go to **Permissions**
3. Grant the following permissions:
   - **USE SCHEMA**
   - **EXECUTE**
   - **SELECT**
   - **READ VOLUME** (if required)

## Step 6: Deploy Application

1. **Initiate Deployment**
   - Click **Deploy** in the Apps interface
   - When prompted for the code path, provide your Git folder path or select your repository folder
2. **Monitor Deployment**
   - The deployment process will begin automatically
   - Monitor logs for any configuration issues

## Updating Your Application

To deploy updates from your GitHub repository:

1. **Pull Latest Changes**
   - In the deployment interface, click **Deployment Source**
   - Select **main** branch
   - Click **Pull** to fetch the latest changes from GitHub
2. **Redeploy**
   - Click **Deploy** again to apply the updates

## Configuration Reference

```python eval
rx.table.root(
    rx.table.header(
        rx.table.row(
            rx.table.column_header_cell("Environment Variable"),
            rx.table.column_header_cell("Description"),
            rx.table.column_header_cell("Example"),
        ),
    ),
    rx.table.body(
        rx.table.row(
            rx.table.cell(rx.code("HOME")),
            rx.table.cell("Application home directory"),
            rx.table.cell(rx.code("/tmp/reflex")),
        ),
        rx.table.row(
            rx.table.cell(rx.code("REFLEX_ACCESS_TOKEN")),
            rx.table.cell("Authentication for Reflex Cloud"),
            rx.table.cell(rx.code("rx_token_...")),
        ),
        rx.table.row(
            rx.table.cell(rx.code("DATABRICKS_WAREHOUSE_ID")),
            rx.table.cell("SQL warehouse identifier"),
            rx.table.cell("Auto-assigned"),
        ),
        rx.table.row(
            rx.table.cell(rx.code("DATABRICKS_CATALOG")),
            rx.table.cell("Target catalog name"),
            rx.table.cell(rx.code("main")),
        ),
        rx.table.row(
            rx.table.cell(rx.code("DATABRICKS_SCHEMA")),
            rx.table.cell("Target schema name"),
            rx.table.cell(rx.code("default")),
        ),
        rx.table.row(
            rx.table.cell(rx.code("REFLEX_SHOW_BUILT_WITH_REFLEX")),
            rx.table.cell("Show Reflex branding (Enterprise only)"),
            rx.table.cell([rx.code("0"), " or ", rx.code("1")]),
        ),
    ),
    variant="surface",
    margin_y="1em",
)
```

## Troubleshooting

- **Permission Errors**: Verify that all catalog and schema permissions are correctly set
- **Port Issues**: Ensure you're using `$DATABRICKS_APP_PORT` and single-port configuration
- **Token Issues**: Verify your Reflex access token is valid and properly configured
- **Deployment Failures**: Check the deployment logs for specific error messages

## Notes

- Single-port deployment requires Reflex Enterprise
- Configuration must be created directly in Databricks, not pushed from GitHub
- Updates require manual pulling from the deployment interface
