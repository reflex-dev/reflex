---
tags: Data Infrastructure
description: Connect with Databricks to run data pipelines and advanced analytics seamlessly.
---


# Databricks Integration

The **Databricks Integration** allows your app to connect to [Databricks](https://www.databricks.com/) for secure data access, querying, and analytics. Once connected, you can run SQL queries, retrieve results, and power data-driven workflows directly from your app.

## What You Can Do

With Databricks, your app can:
- Connect securely to your Databricks workspace.  
- Run **SQL queries** or fetch data programmatically.  
- Build **dashboards and data visualizations** on top of your Databricks tables.  
- Automate workflows triggered by new or updated data.  
- Combine Databricks with AI models for advanced analytics.



## Step 1: Get Your Databricks Credentials

### 1 - Log in to your [Databricks Workspace](https://databricks.com/).

### 2 - Get your **DATABRICKS_HOST** and **DATABRICKS_WAREHOUSE_ID**:

   - Go to `SQL Warehouses` from the sidebar.
   - Select your desired warehouse.
   - Click `Connection details`.
   - Copy the Server hostname (this is your **DATABRICKS_HOST**).
   - Copy the HTTP path removing the `/sql/1.0/warehouses/` prefix (this is your **DATABRICKS_WAREHOUSE_ID**).

![Databricks SQL Warehouse connection details](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/databricks_integration_1.webp)

### 3 - Get your **DATABRICKS_CATALOG** and **DATABRICKS_SCHEMA**:
   - Click the SQL Editor from the sidebar.
   - Choose the **DATABRICKS_CATALOG** and **DATABRICKS_SCHEMA** from the dropdowns as shown below.

![Selecting Databricks catalog and schema in SQL Editor](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/databricks_integration_4.webp)


### 4 - Obtain your authentication credentials:

There are two methods to authenticate your app with Databricks: using interactive U2M **OAuth** or via registered M2M **Service Principal**. Choose one of the methods below to obtain the necessary credentials.


`````md tabs

## OAuth with Databricks

#### Interactive Login with your Databricks Account

If your workspace administrator has already added Reflex as a Connected App in your Databricks workspace, you should see a "Login with Databricks" button after entering your DATABRICKS_HOST.


## Service Principal

#### M2M Service Principal (DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET)

- Open the dropdown in the top right corner and select **Manage Account**.

![Opening Manage Account in Databricks](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/databricks_integration_oauth_1.webp)

- Select `Users and Groups`

![Selecting Users and Groups in Databricks account](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/databricks_integration_oauth_2.webp)

- Select the `Service Principals` tab and click `Add Service Principal`.

![Adding a Databricks service principal](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/databricks_integration_oauth_3.webp)

- Fill in the details and click `Add Service Principal`.

![Entering Databricks service principal details](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/databricks_integration_oauth_4.webp)

- Click the `Credentials and Secrets` tab and click `Generate Secret`.

![Generating a Databricks service principal secret](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/databricks_integration_oauth_5.webp)

- Set a lifetime for the secrets and click `Generate`.

![Setting Databricks secret lifetime](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/databricks_integration_oauth_6.webp)

- Copy the generated **DATABRICKS_CLIENT_ID** and **DATABRICKS_CLIENT_SECRET**.

![Copying Databricks client ID and secret](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/databricks_integration_oauth_7.webp)

`````



## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab, select the **Databricks** card, and click **Add connection**.
2. Paste your **DATABRICKS_HOST**.
3. Select your authentication method:
   - **OAuth**: click **Login with Databricks**. This button appears once a workspace admin has registered the Connected App (see [How to Enable Login as an Admin](#how-to-enable-login-as-an-admin)).
   - **Service Principal**: provide the client ID and secret gathered previously.
4. Optionally pick a **DATABRICKS_WAREHOUSE_ID**, **DATABRICKS_CATALOG**, and **DATABRICKS_SCHEMA** from the dropdowns, which list what your credentials can access.
5. Click **Connect** to save the connection.

Once connected, the AI Builder can execute queries directly against your Databricks environment.


## Step 3: Notes

* **Secure your credentials:** Never expose client secrets in public code.  
* **Permissions:** Ensure your user or service principal has access to the workspace, **CAN USE** on the SQL warehouse, and Unity Catalog permissions on the catalogs and tables the app queries.
* **Combine with AI:** Use query outputs to power models, summaries, or alerts in real time.


## How to Enable Login as an Admin

- Login to Databricks
- Go to manage account

![Opening Manage Account as Databricks admin](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/databricks_admin_auth_1.webp)

- Go to **Settings** → **App connections** → **Add connection**

![Adding a new app connection in Databricks settings](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/databricks_admin_auth_2.webp)

- Give it a name, enter the redirect URL that Reflex Build provides, Click `All APIs` and uncheck `Generate a client secret` and then add.
   - URL: `https://build.reflex.dev/_reflex_oidc_databricks/authorization-code/callback`

![Configuring the Reflex redirect URL in Databricks](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/databricks_admin_auth_3.webp)

- Copy the generated client ID and give it to whoever is connecting in Reflex Build. On the Databricks card's **OAuth** tab, they paste it into **client_id** and click **Add**; **Login with Databricks** then appears.
