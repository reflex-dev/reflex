---
tags: Authentication
description: Integrate Azure for secure authentication and access management within your application.
---
# Azure Auth Integration

> **Legacy integration.** New connections use the [Microsoft Entra ID](https://reflex.dev/docs/ai/integrations/microsoft-entra-id/) card instead: selecting Azure Auth in Reflex Build opens it. This page is for projects that already have an Azure Auth connection.

The **Azure Auth Integration** allows your app to authenticate users through Microsoft Entra ID (formerly Azure Active Directory). This integration provides secure OAuth 2.0 authentication and supports multi-tenant applications with customizable tenant access.

## Step 1: Set Up Azure App Registration

Before connecting, you need to register your app in Azure Portal:

1 - Go to [Azure Portal](https://portal.azure.com) → **App Registrations**

2 - Click **New registration** as shown in the image below:

![Azure App Registration](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/azure_auth_1.webp)

3 - Register your app. Ensure that for the Redirect URI you select **Web** and enter the redirect URI shown on the Azure Auth connection in Reflex Build, which has this form:
   ```
   https://{your-sandbox}/_reflex_oidc_azure/authorization-code/callback
   ```

![Azure App Registration](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/azure_auth_2.webp)

4 - On the next page get your `client_id` (`AZURE_CLIENT_ID`) and `tenant_id` (`AZURE_VALID_TENANT_IDS`) from the **Overview** tab. To accept personal Microsoft accounts instead of a specific directory, use `consumers` as `AZURE_VALID_TENANT_IDS`; that requires registering the app for personal Microsoft accounts.

![Azure App Registration](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/azure_auth_3.webp)

5 - Next click `Add a certificate or secret` and copy the generated secret **Value**, not the Secret ID (`AZURE_CLIENT_SECRET`).

![Azure App Registration](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/azure_auth_4.webp)


## Step 2: Configure the Integration

1. In Reflex Build, open the **Integrations** tab and select your existing **Azure Auth** connection.
2. Fill in the credential fields:
   - **AZURE_CLIENT_ID**: your Application (client) ID
   - **AZURE_CLIENT_SECRET**: your client secret value
   - **AZURE_VALID_TENANT_IDS**: your tenant IDs (comma-separated), or `consumers`
3. Click **Save Changes**.

Your app can now authenticate users through Microsoft Entra ID with a secure OAuth 2.0 flow.
