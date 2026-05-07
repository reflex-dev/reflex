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
2. Navigate to **Workspace Settings → API**.  
3. Click **Create API Key**, give it a name, and copy the key.

   * **Example:** `lin_api_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Step 2: Configure the Integration in Your App

1. Go to **Integrations → Add Linear** in your app settings.
2. Paste your **Linear API Key** in the input field.  
3. Click **Connect** to validate and save your integration.

Once connected, your app can interact with Linear to automate issue tracking and project management.

## Step 3: Notes

* **Keep your key secure:** Never expose your Linear API key in client-side code.  
* **Use environment-specific keys:** Separate dev, staging, and production keys.  
* **Streamlined workflows:** Automate ticket creation, status updates, and reporting directly from your app.  
* **Real-time visibility:** Fetch and sync project data to power internal tools or dashboards.

