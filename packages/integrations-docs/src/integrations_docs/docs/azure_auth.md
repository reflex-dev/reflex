---
tags: Authentication
description: Integrate Azure for secure authentication and access management within your application.
---
# Azure Auth Manager Integration

The **Azure Auth Manager Integration** allows your app to authenticate users through Microsoft Azure Active Directory (Azure AD). This integration provides secure OAuth 2.0 authentication and supports multi-tenant applications with customizable tenant access.

## Step 1: Set Up Azure App Registration

Before connecting, you need to register your app in Azure Portal:

1 - Go to [Azure Portal](https://portal.azure.com) → **App Registrations**

2 - Click **New registration** as shown in the image below:

![Azure App Registration](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/azure_auth_1.webp)

3 - Register your app. Ensure that for the Redirect URI you select **Web** and enter the following URI that you find in the Azure Auth Manager integration settings in AI Builder:
   ```
   https://{your-sandbox}/authorization-code/callback
   ```

![Azure App Registration](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/azure_auth_2.webp)

4 - On the next page get your `client_id` (`AZURE_CLIENT_ID`) and `tenant_id` (`AZURE_VALID_TENANT_IDS`) from the **Overview** tab.

![Azure App Registration](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/azure_auth_3.webp)

5 - Next click `Add a certificate or secret` and copy the generated secret value (`AZURE_CLIENT_SECRET`).

![Azure App Registration](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/azure_auth_4.webp)


## Step 2: Configure the Integration

1. Go to the **Integrations** section in your app settings by clicking **`@`** and then clicking the **Integrations** tab at the top.
2. Click **Add** next to Azure Auth Manager.
3. Fill in the credential fields:
   - Enter your Azure Client ID
   - Enter your Azure Client Secret
   - Enter valid tenant IDs (comma-separated for multiple tenants)
4. Click **Connect** to save the integration.

Your app can now authenticate users through Azure AD with secure OAuth 2.0 flow.
