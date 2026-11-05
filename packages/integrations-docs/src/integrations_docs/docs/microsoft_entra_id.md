---
tags: Authentication
description: Add Microsoft Entra ID (Azure AD) sign-in to your Reflex Build apps with OpenID Connect.
---
# Microsoft Entra ID Integration

The **Microsoft Entra ID Integration** adds user sign-in with Microsoft Entra ID (formerly Azure Active Directory) work and school accounts to your app over OpenID Connect (OIDC). Reflex Build wires the app with the Reflex Enterprise auth plugin, so pages, events, and state can require a signed-in user, and the login button reads "Continue with Microsoft Entra ID".

This card replaces the legacy Azure Auth integration. Projects that already have an Azure Auth connection keep it.

## Step 1: Copy Your Redirect URIs

1. In Reflex Build, open the **Integrations** tab and select the **Microsoft Entra ID** card.
2. Click **Add connection**. The form lists the sign-in redirect URIs to register with Microsoft Entra ID: the app's preview URL followed by `/callback`, plus one for each address the app is deployed to.

Keep the form open; you will fill it in after the next step.

## Step 2: Register an Application in Microsoft Entra ID

1. In the [Microsoft Entra admin center](https://entra.microsoft.com/), go to **Entra ID → App registrations** and click **New registration**.
2. Name the application and choose which account types can sign in.
3. Under **Redirect URI**, select **Web** and enter the first redirect URI from Step 1, then click **Register**. Add the remaining redirect URIs under **Authentication**.
4. On the **Overview** page, copy the **Application (client) ID** and the **Directory (tenant) ID**.
5. Under **Certificates & secrets**, click **New client secret** and copy its **Value** (not the Secret ID). It is only shown once.

## Step 3: Connect in Reflex Build

Fill in the form you opened in Step 1:

- **OIDC_ISSUER_URI**: `https://login.microsoftonline.com/<tenant-id>/v2.0`, with your Directory (tenant) ID from Step 2.
- **OIDC_CLIENT_ID**: the client ID from Step 2.
- **OIDC_CLIENT_SECRET**: the client secret from Step 2. Leave it blank only for a public client that uses PKCE.
- **OIDC_EXTRA_SCOPES** (optional): extra scopes to request, separated by spaces. `offline_access` keeps users signed in; `groups` enables group-based access.

Click **Connect**. Reflex Build fetches the issuer's discovery document (`/.well-known/openid-configuration`) and refuses an issuer URL that does not serve one.

## Notes

* **Register every redirect URI exactly:** a missing or mistyped URI fails at login with `redirect_uri_mismatch`. The preview URL changes when the sandbox is recreated, so register the new one if sign-in stops working. After you deploy, also register `https://<your-app-domain>/callback`.
* **Scopes:** the application must be allowed to request the `openid`, `profile`, and `email` scopes.
* **Session length:** signed-in sessions last up to 7 days, then users sign in again, whatever your provider's token settings.
