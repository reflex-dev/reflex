---
tags: AI
description: Connect your apps to Perplexity to power real-time, retrieval-augmented AI experiences.
---
# Perplexity Integration

The **Perplexity Integration** allows your app to use [Perplexity](https://www.perplexity.ai/) to deliver fast, accurate, retrieval-augmented answers from the web and trusted sources. Once connected, you can use Perplexity to enhance search, summarization, and real-time knowledge in your workflows.

## What You Can Do

With Perplexity, your app can:
- **Retrieve real-time information** from the web to ground model outputs.  
- **Generate concise summaries** and answers with citations.  
- Power **search experiences**, research assistants, and contextual AI features.  
- **Combine Perplexity with other models** for hybrid workflows (e.g., retrieval + reasoning).  
- Enable **trusted, source-backed outputs** for more accurate responses.

## Step 1: Obtain a Perplexity API Key

1. Go to the [Perplexity](https://www.perplexity.ai/).  
2. Log in or create an account.  
3. Navigate to **Account → API → [API Keys](https://www.perplexity.ai/account/api/keys)**.  
4. Click **Generate Key** and copy the generated key.

   * **Example:** `pplx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab and select the **Perplexity** card.
2. Click **Add connection** and paste your API key into **PERPLEXITY_API_KEY**.
3. Click **Connect** to save the connection.

Once connected, your app can use Perplexity for retrieval-augmented AI features across workflows and components.

## Step 3: Notes

* **Keep your key secure:** Do not hardcode your Perplexity API key in public code repositories.  
* **Use environment-specific keys:** Separate dev, staging, and production keys for better control.  
* **Secure API access:** The key allows your app to interact with Perplexity endpoints securely and efficiently.  
* **Real-time power:** Perplexity is ideal for use cases where freshness and factual grounding matter.
