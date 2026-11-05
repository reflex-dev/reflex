---
tags: Authentication
description: Add Clerk sign-in to your Reflex Build apps, using Clerk as an OpenID Connect provider.
---
# Clerk Integration

The **Clerk Integration** adds user sign-in with Clerk, including its social logins and multi-factor authentication to your app over OpenID Connect (OIDC). Reflex Build wires the app with the Reflex Enterprise auth plugin, so pages, events, and state can require a signed-in user, and the login button reads "Continue with Clerk".

This card replaces the legacy Clerk (legacy) integration. Projects that already have a Clerk (legacy) connection keep it.

## Step 1: Copy Your Redirect URIs

1. In Reflex Build, open the **Integrations** tab and select the **Clerk** card.
2. Click **Add connection**. The form lists the sign-in redirect URIs to register with Clerk: the app's preview URL followed by `/callback`, plus one for each address the app is deployed to.

Keep the form open; you will fill it in after the next step.

## Step 2: Create a Clerk OAuth Application

1. In the Clerk Dashboard, go to **OAuth applications** and select **Add application → Create OAuth application**.
2. Enter a name, select the `openid`, `profile`, and `email` scopes, then select **Add**.
3. Copy the **Client Secret** from the dialog that opens. Clerk does not store it and cannot show it again.
4. On the application's settings page, copy the **Client ID** under **Application credentials**, and add each redirect URI from Step 1 under **Redirect URIs**.
5. On the **API keys** page, copy your **Frontend API URL**.

## Step 3: Connect in Reflex Build

Fill in the form you opened in Step 1:

- **OIDC_ISSUER_URI**: your Frontend API URL, for example `https://your-slug.clerk.accounts.dev`. With a custom domain, use `https://clerk.your-domain.com`.
- **OIDC_CLIENT_ID**: the client ID from Step 2.
- **OIDC_CLIENT_SECRET**: the client secret from Step 2. Leave it blank only for a public client that uses PKCE.
- **OIDC_EXTRA_SCOPES** (optional): extra scopes to request, separated by spaces. `offline_access` keeps users signed in; `groups` enables group-based access.

Click **Connect**. Reflex Build fetches the issuer's discovery document (`/.well-known/openid-configuration`) and refuses an issuer URL that does not serve one.

## Notes

* **Register every redirect URI exactly:** a missing or mistyped URI fails at login with `redirect_uri_mismatch`. The preview URL changes when the sandbox is recreated, so register the new one if sign-in stops working. After you deploy, also register `https://<your-app-domain>/callback`.
* **Scopes:** the application must be allowed to request the `openid`, `profile`, and `email` scopes.
* **Session length:** signed-in sessions last up to 7 days, then users sign in again, whatever your provider's token settings.
