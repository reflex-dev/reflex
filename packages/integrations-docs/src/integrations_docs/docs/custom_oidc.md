---
tags: Authentication
description: Add sign-in with any OpenID Connect identity provider to your Reflex Build apps.
---
# Custom OIDC Integration

The **Custom OIDC Integration** adds user sign-in to your app with any OpenID Connect (OIDC) identity provider that does not have its own card, such as Amazon Cognito, PingFederate, Authentik, or Descope. Reflex Build wires the app with the Reflex Enterprise auth plugin, so pages, events, and state can require a signed-in user.

This card replaces the legacy Descope integration. Projects that already have a Descope connection keep it.

## Step 1: Copy Your Redirect URIs

1. In Reflex Build, open the **Integrations** tab and select the **Custom OIDC** card.
2. Click **Add connection**. The form lists the sign-in redirect URIs to register with your provider: the app's preview URL followed by `/callback`, plus one for each address the app is deployed to.

Keep the form open; you will fill it in after the next step.

## Step 2: Register an Application With Your Provider

1. In your identity provider, create an application (sometimes called a client) that uses the **authorization code** flow.
2. Add each redirect URI from Step 1 as an allowed redirect or callback URI.
3. Copy the application's **client ID** and, for a confidential client, its **client secret**.
4. Find your provider's **issuer URL**: it is the `issuer` value in the provider's `/.well-known/openid-configuration` document.

## Step 3: Connect in Reflex Build

Fill in the form you opened in Step 1:

- **OIDC_ISSUER_URI**: your provider's issuer URL, exactly as it appears in its discovery document.
- **OIDC_CLIENT_ID**: the client ID from Step 2.
- **OIDC_CLIENT_SECRET**: the client secret from Step 2. Leave it blank only for a public client that uses PKCE.
- **OIDC_EXTRA_SCOPES** (optional): extra scopes to request, separated by spaces. `offline_access` keeps users signed in after their access token expires, up to the 7-day session limit; `groups` enables group-based access if your provider offers that scope.

Click **Connect**. Reflex Build fetches the issuer's discovery document (`/.well-known/openid-configuration`) and refuses an issuer URL that does not serve one.

## Notes

* **Register every redirect URI exactly:** a missing or mistyped URI fails at login with `redirect_uri_mismatch`. The preview URL changes when the sandbox is recreated, so register the new one if sign-in stops working. After you deploy, also register `https://<your-app-domain>/callback`.
* **Scopes:** the application must be allowed to request the `openid`, `profile`, and `email` scopes.
* **Session length:** signed-in sessions last up to 7 days, then users sign in again, whatever your provider's token settings.
