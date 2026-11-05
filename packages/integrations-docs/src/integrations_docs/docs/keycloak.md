---
tags: Authentication
description: Add Keycloak sign-in to your Reflex Build apps with OpenID Connect.
---
# Keycloak Integration

The **Keycloak Integration** adds user sign-in with a Keycloak realm to your app over OpenID Connect (OIDC). Reflex Build wires the app with the Reflex Enterprise auth plugin, so pages, events, and state can require a signed-in user, and the login button reads "Continue with Keycloak".

## Step 1: Copy Your Redirect URIs

1. In Reflex Build, open the **Integrations** tab and select the **Keycloak** card.
2. Click **Add connection**. The form lists the sign-in redirect URIs to register with Keycloak: the app's preview URL followed by `/callback`, plus one for each address the app is deployed to.

Keep the form open; you will fill it in after the next step.

## Step 2: Create a Keycloak Client

1. In the Keycloak admin console, select your realm, go to **Clients**, and click **Create client**.
2. Keep **OpenID Connect** as the client type, enter a **Client ID**, and click **Next**.
3. Turn on **Client authentication**, keep **Standard flow** enabled, and click **Next**.
4. Under **Valid redirect URIs**, add each redirect URI from Step 1, then save.
5. Copy the **Client Secret** from the client's **Credentials** tab.

Keycloak must be reachable over HTTPS from the internet for Reflex Build and your app to use it.

## Step 3: Connect in Reflex Build

Fill in the form you opened in Step 1:

- **OIDC_ISSUER_URI**: your Keycloak base URL including the realm path, for example `https://your-host/realms/your-realm`.
- **OIDC_CLIENT_ID**: the client ID from Step 2.
- **OIDC_CLIENT_SECRET**: the client secret from Step 2. Leave it blank only for a public client that uses PKCE.
- **OIDC_EXTRA_SCOPES** (optional): extra scopes to request, separated by spaces. `offline_access` keeps users signed in; `groups` enables group-based access.

Click **Connect**. Reflex Build fetches the issuer's discovery document (`/.well-known/openid-configuration`) and refuses an issuer URL that does not serve one.

## Notes

* **Register every redirect URI exactly:** a missing or mistyped URI fails at login with `redirect_uri_mismatch`. The preview URL changes when the sandbox is recreated, so register the new one if sign-in stops working. After you deploy, also register `https://<your-app-domain>/callback`.
* **Scopes:** the application must be allowed to request the `openid`, `profile`, and `email` scopes.
* **Session length:** signed-in sessions last up to 7 days, then users sign in again, whatever your provider's token settings.
