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

1. Go to the [Notion developer portal](https://app.notion.com/developers/connections) (you must be a Workspace Owner).  
2. Under **Internal connections**, click **Create a new connection**, give it a name, and choose your workspace.  
3. Open the **Configuration** tab and copy the **API token**.  
4. Give the connection access to the pages or databases it needs: in the **Content access** tab click **Edit access**, or in Notion open the page's **•••** menu → **Connections** → **+ Add connection**.

   * **Example:** `ntn_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab and select the **Notion** card.
2. Click **Add connection** and paste your token into **NOTION_API_KEY**.
3. Click **Connect** to save the connection.

If the card offers a **Connect account** tab, you can sign in with Notion there instead of pasting a key.

Once connected, your app can read and write to Notion directly from workflows and UI actions.

## Step 3: Notes

* **Keep your token secure:** Never expose your Notion token in client-side code.  
* **Use environment-specific tokens:** Separate dev, staging, and production access.  
* **Granular permissions:** Only give the connection access to the pages or databases it needs to access.  
* **Powerful building block:** Use Notion as a single source of truth for content, tasks, or structured data.

