---
tags: Authentication
description: Add Okta sign-in and enterprise single sign-on to your Reflex Build apps with OpenID Connect.
---
# Okta Integration

The **Okta Integration** adds user sign-in with Okta to your app over OpenID Connect (OIDC). Reflex Build wires the app with the Reflex Enterprise auth plugin, so pages, events, and state can require a signed-in user, and the login button reads "Continue with Okta".

This card replaces the legacy Okta Auth integration. Projects that already have an Okta Auth connection keep it.

## Step 1: Copy Your Redirect URIs

1. In Reflex Build, open the **Integrations** tab and select the **Okta** card.
2. Click **Add connection**. The form lists the sign-in redirect URIs to register with Okta: the app's preview URL followed by `/callback`, plus one for each address the app is deployed to.

Keep the form open; you will fill it in after the next step.

## Step 2: Create an Okta App Integration

1. In the Okta Admin Console, go to **Applications → Applications** and click **Create App Integration**.
2. Select **OIDC - OpenID Connect** as the sign-in method and **Web Application** as the application type.
3. Under **Sign-in redirect URIs**, add each redirect URI from Step 1.
4. Under **Assignments**, choose who can sign in, then save.
5. Copy the **Client ID** and **Client secret** from the app's **General** tab.
6. Go to **Security → API → Authorization Servers** and copy the **Issuer URI** of the server you use (usually **default**).

## Step 3: Connect in Reflex Build

Fill in the form you opened in Step 1:

- **OIDC_ISSUER_URI**: the Issuer URI from Step 2, including the authorization server path, for example `https://your-org.okta.com/oauth2/default`.
- **OIDC_CLIENT_ID**: the client ID from Step 2.
- **OIDC_CLIENT_SECRET**: the client secret from Step 2. Leave it blank only for a public client that uses PKCE.
- **OIDC_EXTRA_SCOPES** (optional): extra scopes to request, separated by spaces. `offline_access` keeps users signed in; `groups` enables group-based access.

Click **Connect**. Reflex Build fetches the issuer's discovery document (`/.well-known/openid-configuration`) and refuses an issuer URL that does not serve one.

## Notes

* **Register every redirect URI exactly:** a missing or mistyped URI fails at login with `redirect_uri_mismatch`. The preview URL changes when the sandbox is recreated, so register the new one if sign-in stops working. After you deploy, also register `https://<your-app-domain>/callback`.
* **Scopes:** the application must be allowed to request the `openid`, `profile`, and `email` scopes.
* **Session length:** signed-in sessions last up to 7 days, then users sign in again, whatever your provider's token settings.
