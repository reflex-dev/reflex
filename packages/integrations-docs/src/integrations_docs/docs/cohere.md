---
tags: AI
description: Add Cohere’s language models for text generation, classification, retrieval, embeddings, and more.
---
# Cohere Integration

The **Cohere Integration** allows your app to use [Cohere’s](https://cohere.com) state-of-the-art language models for natural language understanding and generation. Once connected, your app can power search, summarization, embeddings, classification, and conversational AI features directly from workflows and triggers.


## Step 1: Obtain a Cohere API Key

1. Go to the [Cohere Dashboard](https://dashboard.cohere.com/).  
2. Log in or create an account.  
3. Navigate to **API Keys** in your account settings.  
4. Click **Create Key**, give it a descriptive name (e.g., “AI Builder”), and copy the key.  


## Step 2: Configure the Integration in Your App

1. Go to **Integrations → Add Cohere** in your app settings.  
2. Paste your **Cohere API Key** in the input field.  
3. Click **Connect** to validate and save your integration.  

Once connected, your app can access Cohere’s endpoints for language tasks like embeddings, classification, chat, and more.


## Step 3: Notes

- **Secure API Access:** Keep your Cohere API key private — do not hardcode it in public repositories.  
- **Environment separation:** Use different keys for development, staging, and production environments.  
- **Performance:** Cohere’s models support fast inference for production-ready experiences.  
- **Observability:** Use the Cohere dashboard to monitor usage, quotas, and request logs.

