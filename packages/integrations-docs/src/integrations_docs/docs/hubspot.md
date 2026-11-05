---
tags: Data Infrastructure
description: Connect your apps to HubSpot to manage contacts, companies, deals, and marketing workflows.
---
# HubSpot Integration

The **HubSpot Integration** allows your app to use [HubSpot](https://www.hubspot.com/) as a CRM and marketing automation platform. Once connected, your app can sync leads, manage contacts, update pipelines, and trigger workflows directly from user actions or automated events.

## Step 1: Obtain a HubSpot Access Token

1. Go to your [HubSpot Developer Account](https://developers.hubspot.com/).  
2. Navigate to **App → Private Apps** in your account settings.  
3. Click **Create Private App**, configure scopes (e.g., `crm.objects.contacts.read/write`, `crm.schemas.companies.read`), and save.  
4. Copy the **Access Token** from the Auth tab.
   * **Example:** `pat-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab and select the **HubSpot** card.
2. Click **Add connection** and paste your access token into **HUBSPOT_ACCESS_TOKEN**.
3. Click **Connect** to save the connection.

Once connected, your app can sync and manage HubSpot data directly from workflows and UI actions.

## Step 3: Notes

* **Keep your token secure:** Do not hardcode your HubSpot token in public code repositories.  
* **Use environment-specific tokens:** Separate dev, staging, and production tokens to manage access.  
* **Secure API access:** The token allows your app to interact with HubSpot endpoints securely and efficiently.

