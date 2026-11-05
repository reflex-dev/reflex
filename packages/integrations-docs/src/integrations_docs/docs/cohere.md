---
tags: AI
description: Add Cohere’s language models for text generation, classification, retrieval, embeddings, and more.
---
# Cohere Integration

The **Cohere Integration** allows your app to use [Cohere’s](https://cohere.com) state-of-the-art language models for natural language understanding and generation. Once connected, your app can power search, summarization, embeddings, classification, and conversational AI features directly from workflows and triggers.


## Step 1: Obtain a Cohere API Key

1. Go to the [Cohere Dashboard](https://dashboard.cohere.com/).  
2. Log in or create an account.  
3. Open the [API Keys](https://dashboard.cohere.com/api-keys) page.
4. Create a trial key (free, limited to 1,000 API calls a month) or a production key (paid), give it a descriptive name (e.g., “AI Builder”), and copy the key.  


## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab and select the **Cohere** card.
2. Click **Add connection** and paste your API key into **COHERE_API_KEY**.
3. Click **Connect** to save the connection.

Once connected, your app can access Cohere’s endpoints for language tasks like embeddings, classification, chat, and more.


## Step 3: Notes

- **Secure API Access:** Keep your Cohere API key private — do not hardcode it in public repositories.  
- **Environment separation:** Use different keys for development, staging, and production environments.  
- **Performance:** Cohere’s models support fast inference for production-ready experiences.  
- **Observability:** Use the Cohere dashboard to monitor usage, quotas, and request logs.

