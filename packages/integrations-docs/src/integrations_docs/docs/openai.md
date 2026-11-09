---
tags: AI
description: Connect to OpenAI's powerful language models for text generation, analysis, and more.
---
# OpenAI Integration

The **OpenAI Integration** allows your app to use OpenAI APIs for features such as text generation, embeddings, and other AI-powered functionality.

## Step 1: Obtain an OpenAI API Key

1. Go to the [OpenAI Platform](https://platform.openai.com/).
2. Open the [API keys](https://platform.openai.com/settings/organization/api-keys) page in your organization settings.
3. Click **Create new secret key**.
4. Copy the generated key.
   - Example: `sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`


## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab and select the **OpenAI** card.
2. Click **Add connection** and paste your API key into **OPENAI_API_KEY**.
3. Click **Connect** to save the connection.

Leave **OPENAI_BASE_URL** at its default (`https://api.openai.com/v1`) unless you send requests through a proxy or gateway.

---

## Step 3: Notes

- Keep your OpenAI key secure; do **not** hardcode it in public code repositories.
- Use environment-specific secrets if you have separate development, staging, and production environments.
- The key allows your app to interact with OpenAI endpoints securely and efficiently.
