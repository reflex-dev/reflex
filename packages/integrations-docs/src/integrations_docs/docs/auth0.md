---
tags: Authentication
description: Add Auth0 sign-in to your Reflex Build apps with OpenID Connect.
---
# Auth0 Integration

The **Auth0 Integration** adds user sign-in with your Auth0 tenant, including its social, passwordless, and enterprise connections to your app over OpenID Connect (OIDC). Reflex Build wires the app with the Reflex Enterprise auth plugin, so pages, events, and state can require a signed-in user, and the login button reads "Continue with Auth0".

## Step 1: Copy Your Redirect URIs

1. In Reflex Build, open the **Integrations** tab and select the **Auth0** card.
2. Click **Add connection**. The form lists the sign-in redirect URIs to register with Auth0: the app's preview URL followed by `/callback`, plus one for each address the app is deployed to.

Keep the form open; you will fill it in after the next step.

## Step 2: Create an Auth0 Application

1. In the Auth0 Dashboard, go to **Applications → Applications** and click **Create Application**.
2. Choose **Regular Web Applications** and create it.
3. On the **Settings** tab, under **Application URIs**, add each redirect URI from Step 1 to **Allowed Callback URLs** (comma-separated) and save.
4. Under **Basic Information** on the same tab, copy the **Domain**, **Client ID**, and **Client Secret**.

## Step 3: Connect in Reflex Build

Fill in the form you opened in Step 1:

- **OIDC_ISSUER_URI**: `https://<your-domain>/`, using the Domain from Step 2. Enter it exactly as the `issuer` value in `https://<your-domain>/.well-known/openid-configuration`, which for Auth0 ends with a slash.
- **OIDC_CLIENT_ID**: the client ID from Step 2.
- **OIDC_CLIENT_SECRET**: the client secret from Step 2. Leave it blank only for a public client that uses PKCE.
- **OIDC_EXTRA_SCOPES** (optional): extra scopes to request, separated by spaces. `offline_access` keeps users signed in; `groups` enables group-based access.

Click **Connect**. Reflex Build fetches the issuer's discovery document (`/.well-known/openid-configuration`) and refuses an issuer URL that does not serve one.

## Notes

* **Register every redirect URI exactly:** a missing or mistyped URI fails at login with `redirect_uri_mismatch`. The preview URL changes when the sandbox is recreated, so register the new one if sign-in stops working. After you deploy, also register `https://<your-app-domain>/callback`.
* **Scopes:** the application must be allowed to request the `openid`, `profile`, and `email` scopes.
* **Session length:** signed-in sessions last up to 7 days, then users sign in again, whatever your provider's token settings.
