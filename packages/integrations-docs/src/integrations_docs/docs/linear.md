---
tags: DevTools
description: Connect your apps to Linear to manage issues, projects, and sprints directly from workflows.
---
# Linear Integration

The **Linear Integration** allows your app to connect to [Linear](https://linear.app/) to create, update, and track issues and projects seamlessly. Once connected, your app can trigger Linear actions from user interactions or automated workflows.

## What You Can Do

With Linear, your app can:
- **Create and assign issues** automatically from user actions or AI workflows.  
- **Update status and priority** of tickets and projects.  
- **Sync with sprints and cycles** to keep work organized.  
- **Fetch project and issue data** for dashboards, summaries, or automation.  
- **Integrate with other tools** like Slack or GitHub through workflows.  
- Power intelligent workflows (e.g., auto-triage or auto-summarize bug reports).

## Step 1: Obtain a Linear API Key

1. Go to your [Linear account](https://linear.app/).  
2. Navigate to **Settings → Account → Security & access**.  
3. Create a new **personal API key**, give it a name, and copy the key.

> 💡 If you're a Member and can't create a key, ask a workspace Admin to allow member API keys.

   * **Example:** `lin_api_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab and select the **Linear** card.
2. Click **Add connection** and paste your API key into **LINEAR_API_KEY**.
3. Click **Connect** to save the connection.

If the card offers a **Connect account** tab, you can sign in with Linear there instead of pasting a key.

Once connected, your app can interact with Linear to automate issue tracking and project management.

## Step 3: Notes

* **Keep your key secure:** Never expose your Linear API key in client-side code.  
* **Use environment-specific keys:** Separate dev, staging, and production keys.  
* **Streamlined workflows:** Automate ticket creation, status updates, and reporting directly from your app.  
* **Real-time visibility:** Fetch and sync project data to power internal tools or dashboards.

