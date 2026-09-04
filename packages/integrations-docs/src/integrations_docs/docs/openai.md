---
tags: AI
description: Connect to OpenAI's powerful language models for text generation, analysis, and more.
---
# OpenAI Integration

The **OpenAI Integration** allows your app to use OpenAI APIs for features such as text generation, embeddings, and other AI-powered functionality.

## Step 1: Obtain an OpenAI API Key

1. Go to the [OpenAI Platform](https://platform.openai.com/).
2. Navigate to **API Keys** in your account settings.
3. Click **Create new secret key**.
4. Copy the generated key.
   - Example: `sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`


## Step 2: Configure the Integration in Your App

1. Go to **Integrations → Add OpenAI Integration** in your app settings.
2. Enter your **OpenAI API Key** in the input field.
3. Save the integration. Your app is now ready to make OpenAI API requests.

---

## Step 3: Notes

- Keep your OpenAI key secure; do **not** hardcode it in public code repositories.
- Use environment-specific secrets if you have separate development, staging, and production environments.
- The key allows your app to interact with OpenAI endpoints securely and efficiently.
