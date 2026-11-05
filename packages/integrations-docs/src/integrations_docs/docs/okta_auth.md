---
tags: Authentication
description: Use Okta for secure identity and access management via Single Sign-On provisioning.
---

# Okta Auth Integration

> **Legacy integration.** New connections use the [Okta](https://reflex.dev/docs/ai/integrations/okta/) card instead: selecting Okta Auth in Reflex Build opens it. This page is for projects that already have an Okta Auth connection.

The **Okta Auth Integration** allows your app to authenticate users through [Okta](https://okta.com). This integration provides secure OAuth 2.0 / OIDC authentication and supports multi-tenant environments with customizable access policies.


## What You Can Do

With Okta, your app can:
- Authenticate users securely through Okta’s identity platform.  
- Enable **SSO** for enterprise users.  
- Manage user roles, groups, and access permissions.  
- Protect sensitive data and actions with **OAuth 2.0** and **OpenID Connect (OIDC)**.  
- Integrate with other identity workflows like MFA or adaptive policies.


## Step 1: Set Up Okta OIDC App

Before connecting, you need to create an OIDC application in the Okta Admin Console:

1 - Go to [Okta Admin Console](https://login.okta.com) → **Applications** → **Applications**


2 - Click **Create App Integration**

![Creating an Okta app integration](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/okta_auth_1.png)

3 - Select **OIDC – OpenID Connect** and choose **Web Application**

![Selecting OIDC web application in Okta](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/okta_auth_2.png)

4 - Configure your app settings:
   - **Allow wildcard * in sign-in redirect URIs**
   - **Sign-in redirect URIs**: the redirect URI shown on the Okta Auth connection in Reflex Build, which has this form:
     `https://{your-sandbox}/_reflex_oidc_okta/authorization-code/callback`
   - **Sign-out redirect URIs**:
     `https://{your-sandbox}`
   - Assign to the correct **Group** or **Everyone** depending on your access control

![Configuring Okta sign-in redirect URIs](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/okta_auth_3.png)

5 - Save the app integration.

6 - Copy your **Client ID** (`OKTA_CLIENT_ID`) and **Client Secret** (`OKTA_CLIENT_SECRET`) from the app settings.

![Copying Okta client ID and secret](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/okta_auth_4.png)


## Step 2: Finding Your Okta Issuer URI

1. In the Okta Admin Console, go to **Security** → **API** → **Authorization Servers**
2. Click on the **default** server and copy the **Issuer URI**, including `/oauth2/default`. This is your **Okta Issuer URI** (`OKTA_ISSUER_URI`).

Example: `https://{yourOktaDomain}.okta.com/oauth2/default`

![Finding the Okta issuer URI](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/okta_auth_5.png)


> **Note:** Always use separate Okta apps for dev, staging, and production environments to avoid mixing credentials.


## Step 3: Configure the Integration

1. In Reflex Build, open the **Integrations** tab and select your existing **Okta Auth** connection.
2. Fill in the credential fields:
   - **OKTA_CLIENT_ID**: your Client ID
   - **OKTA_CLIENT_SECRET**: your Client Secret
   - **OKTA_ISSUER_URI**: your Issuer URI
3. Click **Save Changes**.

Your app can now authenticate users through Okta using the secure OAuth 2.0 / OIDC flow.
