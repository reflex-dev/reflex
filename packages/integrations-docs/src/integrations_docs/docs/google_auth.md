---
tags: Authentication
description: Enable secure authentication using Google sign-in and OAuth 2.0 workflows.
---

# Google Auth Integration

The **Google Auth Integration** allows your app to authenticate users using their Google accounts. This provides a secure, familiar login experience and simplifies user management.


## Step 1: Create a Google OAuth Client

1 - Go to the [Google Cloud Console](https://console.cloud.google.com/)

2 - Navigate to **APIs & Services → Credentials**

3 - Click **Create Credentials**

![Creating credentials in Google Cloud Console](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/google_auth_1.webp)

4 - Choose **OAuth client ID**.

![Choosing OAuth client ID credential type](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/google_auth_2.webp)

5 - Choose **Web Application** as the application type, name the application and enter your sandbox URL, which you get from the Google Auth integration panel, as the **Authorized JavaScript Origin** and **Authorized Redirect URIs**.

![Configuring Google OAuth web application origins](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/google_auth_3.webp)

6 - Copy the generated **Client ID** (`GOOGLE_CLIENT_ID`) and **Client Secret** (`GOOGLE_CLIENT_SECRET`).

![Copying Google client ID and secret](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/google_auth_4.webp)


## Step 2: Configure the Integration in Your App

1. Go to **Integrations → Add Google Auth** in your app settings.
2. Enter your **Google Client ID** and **Google Client Secret**.
3. Save the integration. Your app is now configured to use Google Auth for login.

## Step 3: Notes

- The integration supports multiple environments (development, staging, production). Use environment-specific secrets for the client ID and secret.
- Google Auth handles token refresh automatically when users log in via OAuth.
- Users will see a standard Google login screen, ensuring familiarity and trust.
- Ensure your app domain matches the authorized JavaScript origin and redirect URIs; otherwise, authentication will fail.
