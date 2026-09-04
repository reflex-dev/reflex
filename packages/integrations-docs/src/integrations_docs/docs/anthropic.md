---
tags: AI
description: Connect your apps to Anthropic's Claude models for advanced AI capabilities.
---
# Anthropic Integration

The **Anthropic Integration** allows your app to use [Anthropic’s Claude models](https://www.anthropic.com/claude) for tasks such as text generation, summarization, reasoning, and other advanced AI capabilities. Once connected, you can call Claude directly from your workflows, UI actions, or automated triggers.


## Step 1: Obtain an Anthropic API Key

1. Go to the [Anthropic Console](https://console.anthropic.com/).
2. Navigate to **API Keys** in your account settings.
3. Click **Create Key** and give it a descriptive name (e.g., “AI Builder”).
4. Copy the generated key.

   * **Example:** `sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`


## Step 2: Configure the Integration in Your App

1. Go to **Integrations → Add Anthropic** in your app settings.
2. Paste your **Anthropic API Key** in the input field.
3. Click **Connect** to validate and save your integration.

Once connected, your app can use Claude for AI-powered features across workflows and components.


## Step 3: Notes

* **Keep your key secure:** Do not hardcode your Anthropic API key in public code repositories.
* **Use environment-specific keys:** Separate dev, staging, and production keys help manage access and security.
* **Secure API access:** The key allows your app to interact with Anthropic endpoints securely and efficiently.


