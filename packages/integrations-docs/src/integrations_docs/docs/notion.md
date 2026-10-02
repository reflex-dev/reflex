---
tags: Data Infrastructure
description: Connect your apps to Notion to create, update, and query pages, databases, and documents.
---
# Notion Integration

The **Notion Integration** allows your app to connect to [Notion](https://www.notion.so/) to manage content, automate workflows, and build dynamic interfaces on top of Notion workspaces. Once connected, your app can read and write pages, sync databases, and trigger actions based on user activity.

## What You Can Do

With Notion, your app can:
- **Create and update pages** in workspaces automatically.  
- **Read and query databases** to power dashboards, workflows, or automations.  
- **Sync structured content** like tasks, notes, or documentation with other tools.  
- Trigger **actions from AI workflows** (e.g., creating meeting notes, logging issues).  
- Integrate with other services (e.g., Slack, Linear, HubSpot) for seamless collaboration.

## Step 1: Obtain a Notion API Token

1. Go to the [Notion Developers](https://www.notion.so/my-integrations) page.  
2. Click **+ New Integration**, give it a name, and copy the generated **Internal Integration Token**.  
3. Share the integration with the relevant pages or databases in your workspace to grant access.

   * **Example:** `ntn_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Step 2: Configure the Integration in Your App

1. Go to **Integrations → Add Notion** in your app settings.  
2. Paste your **Notion API Token** in the input field.  
3. Click **Connect** to validate and save your integration.

Once connected, your app can read and write to Notion directly from workflows and UI actions.

## Step 3: Notes

* **Keep your token secure:** Never expose your Notion token in client-side code.  
* **Use environment-specific tokens:** Separate dev, staging, and production access.  
* **Granular permissions:** Only share the integration with the pages or databases it needs to access.  
* **Powerful building block:** Use Notion as a single source of truth for content, tasks, or structured data.

