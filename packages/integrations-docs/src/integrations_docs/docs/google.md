---
tags: Authentication
description: Add Google account sign-in to your Reflex Build apps with OpenID Connect.
---
# Google Integration

The **Google Integration** adds user sign-in with Google accounts to your app over OpenID Connect (OIDC). Reflex Build wires the app with the Reflex Enterprise auth plugin, so pages, events, and state can require a signed-in user, and the login button reads "Continue with Google".

This card replaces the legacy Google Auth integration. Projects that already have a Google Auth connection keep it.

## Step 1: Copy Your Redirect URIs

1. In Reflex Build, open the **Integrations** tab and select the **Google** card.
2. Click **Add connection**. The form lists the sign-in redirect URIs to register with Google: the app's preview URL followed by `/callback`, plus one for each address the app is deployed to.

Keep the form open; you will fill it in after the next step.

## Step 2: Create a Google OAuth Client

1. In the [Google Cloud Console](https://console.cloud.google.com/), open **Google Auth Platform**. If you have not configured it for this project yet, click **Get started** and complete the app setup first.
2. Go to **Clients** and click **Create client**.

   ![The Clients page of Google Auth Platform](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/google_1.webp)

3. Choose **Web application** as the application type and give it a name.
4. Under **Authorized redirect URIs**, add each redirect URI from Step 1.

   ![Adding a redirect URI to a Google OAuth client](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/google_2.webp)

5. Click **Create**, then copy the **Client ID** and **Client secret**. Store the secret somewhere safe: Google only shows it in full when the client is created.

   ![Google's dialog with the new client ID and secret](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/google_3.webp)

## Step 3: Connect in Reflex Build

Fill in the form you opened in Step 1:

- **OIDC_ISSUER_URI**: prefilled with `https://accounts.google.com`. Google's issuer is fixed, so leave it as it is.
- **OIDC_CLIENT_ID**: the client ID from Step 2.
- **OIDC_CLIENT_SECRET**: the client secret from Step 2.
- **OIDC_EXTRA_SCOPES** (optional): extra scopes to request, separated by spaces. Google has no `offline_access` or `groups` scope, so leave this blank unless you need other Google OAuth scopes.

Click **Connect**. Reflex Build fetches the issuer's discovery document (`/.well-known/openid-configuration`) and refuses an issuer URL that does not serve one.

## Notes

* **Register every redirect URI exactly:** a missing or mistyped URI fails at login with `redirect_uri_mismatch`. The preview URL changes when the sandbox is recreated, so register the new one if sign-in stops working. After you deploy, also register `https://<your-app-domain>/callback`.
* **Scopes:** the application must be allowed to request the `openid`, `profile`, and `email` scopes.
* **Session length:** signed-in sessions last up to 7 days, then users sign in again, whatever your provider's token settings.
