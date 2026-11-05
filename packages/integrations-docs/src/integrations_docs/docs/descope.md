---
tags: Authentication
description: Add Descope’s identity and authentication platform to your apps to manage user sign-in, onboarding, MFA, SSO, and flows with ease.
---
# Descope Integration

> **Legacy integration.** New connections use the [Custom OIDC](https://reflex.dev/docs/ai/integrations/custom-oidc/) card instead: selecting Descope in Reflex Build opens it. This page is for projects that already have a Descope connection.

The **Descope Integration** enables your app to leverage Descope’s full Customer Identity & Access Management (CIAM) features—visual authentication flows, identity management, SSO, MFA, tenant isolation, and more. Once set up, you can orchestrate secure user journeys across your application with minimal coding.


```md alert warning
# You must open your app in a new tab from the builder to test the Descope integration.
```

## What You Can Do

With Descope Integration, your app can:
- Handle user sign-up, login, and passwordless flows seamlessly  
- Enable multifactor authentication (MFA), passkeys, and social login  
- Support single sign-on (SSO) via OIDC/SAML  
- Manage users, roles, tenants, and permissions via management APIs  
- Orchestrate onboarding, branding, and multi-tenant flows via drag-and-drop workflows  
- Sync user data with tools like HubSpot or Segment via built-in connectors


## Step 1: Obtain Descope Credentials

![Descope Credentials](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/descope.webp)

1. Log in to the [**Descope Console** (or sign up)](https://www.descope.com/sign-up).
2. Create your first Project. 
3. Go to the Project page under Settings.
4. Copy the `Project ID`.


## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab and select your existing **Descope** connection.
2. Enter your **DESCOPE_PROJECT_ID**.  
3. (Optional) Set **DESCOPE_FLOW_ID** (defaults to `sign-up-or-in`) and **SESSION_SECRET_KEY**, or use the fill button to generate a random secret.  
4. Click **Save Changes**.

![Descope Integration](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/descope_2.webp)


