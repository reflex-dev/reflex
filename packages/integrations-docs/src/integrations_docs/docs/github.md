---
tags: Developer Tools
description: Connect your app to GitHub to automate workflows, manage repositories, and integrate developer operations.
---
# GitHub Integration

The **GitHub Integration** lets your app connect directly to [GitHub](https://github.com) to automate actions, fetch data, and build powerful developer workflows. Once connected, your app can interact with repositories, issues, pull requests, and more.

## What You Can Do

With GitHub, your app can:
- Fetch and display repository data (commits, branches, issues, etc.).  
- Create or update issues, pull requests, and discussions.  
- Trigger workflows or CI/CD pipelines.  
- Sync GitHub activity into your app’s dashboards or automations.  
- Build custom developer tools using GitHub’s API.

## Step 1: Generate a Personal Access Token

1. Go to **Settings → Developer settings → Personal access tokens** on GitHub.  
2. Choose a token type:
   * **Fine-grained (recommended):** at [github.com/settings/personal-access-tokens](https://github.com/settings/personal-access-tokens), click **Generate new token**, pick the resource owner and repositories, and grant only the permissions you need (e.g., **Contents**, **Issues**, **Pull requests**).
   * **Classic:** at [github.com/settings/tokens](https://github.com/settings/tokens), click **Generate new token → Generate new token (classic)** and select scopes (e.g., `repo`, `workflow`, `read:user`).
3. Click **Generate token** and copy it.  
   **Example tokens** (fine-grained, then classic):  
```
github_pat_xxxxxxxxxxxxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
(Note: Replace the above value with your actual GitHub token)

> 💡 GitHub recommends fine-grained tokens. They don't yet support every API, so use a classic token only if you need one of those.

## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab and select the **GitHub** card.
2. Click **Add connection** and paste your personal access token into **GITHUB_TOKEN**.
3. Click **Connect** to save the connection.

Once connected, your app can start interacting with GitHub through workflows and actions.

## Step 3: Notes

* **Keep your token secure:** Never expose your GitHub token in public code.  
* **Use fine-grained permissions:** Limit access to only what’s needed.  
* **API rate limits:** GitHub imposes API limits, so plan automations accordingly.  
* **Combine with AI:** For example, auto-generate release notes from commits or summarize PRs with LLMs.

