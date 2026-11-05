---
tags: Data Infrastructure
description: Connect your apps to HubSpot to manage contacts, companies, deals, and marketing workflows.
---
# HubSpot Integration

The **HubSpot Integration** allows your app to use [HubSpot](https://www.hubspot.com/) as a CRM and marketing automation platform. Once connected, your app can sync leads, manage contacts, update pipelines, and trigger workflows directly from user actions or automated events.

## Step 1: Obtain a HubSpot Access Token

1. Log in to your [HubSpot account](https://app.hubspot.com/).  
2. Go to **Settings → Integrations → Service Keys** (in some accounts this is under **Development → Keys → Service keys**).  
3. Click **Create service key**, give it a name, add the scopes your app needs (e.g., `crm.objects.contacts.read`, `crm.objects.contacts.write`), and click **Create**.  
4. Click **Show** and copy the key.
   * **Example:** `pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

> 💡 HubSpot no longer allows creating new legacy private apps, but you can still use the access token of an existing one.

## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab and select the **HubSpot** card.
2. Click **Add connection** and paste your access token into **HUBSPOT_ACCESS_TOKEN**.
3. Click **Connect** to save the connection.

Once connected, your app can sync and manage HubSpot data directly from workflows and UI actions.

## Step 3: Notes

* **Keep your token secure:** Do not hardcode your HubSpot token in public code repositories.  
* **Use environment-specific tokens:** Separate dev, staging, and production tokens to manage access.  
* **Secure API access:** The token allows your app to interact with HubSpot endpoints securely and efficiently.

