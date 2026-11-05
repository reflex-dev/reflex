---
tags: AI
description: Connect your apps to Groq’s ultra-fast inference API for lightning-speed AI responses.
---
# Groq Integration

The **Groq Integration** allows your app to use [Groq’s API](https://groq.com/) for ultra-fast AI inference. Once connected, your app can leverage Groq’s hosted models (including open models like Llama, OpenAI’s gpt-oss, and Qwen) to power real-time workflows, chat experiences, and other AI-driven features.

## Step 1: Obtain a Groq API Key

1. Go to the [Groq Console](https://console.groq.com/).  
2. Open the [API Keys](https://console.groq.com/keys) page.  
3. Click **Create API Key** and give it a descriptive name (e.g., “AI Builder”).  
4. Copy the generated key.
   * **Example:** `gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab and select the **Groq** card.
2. Click **Add connection** and paste your API key into **GROQ_API_KEY**.
3. Click **Connect** to save the connection.

Once connected, your app can use Groq to deliver ultra-low latency AI responses across workflows and components.

## Step 3: Notes

* **Keep your key secure:** Do not hardcode your Groq API key in public code repositories.  
* **Use environment-specific keys:** Separate dev, staging, and production keys help manage access and security.  
* **Secure API access:** The key allows your app to interact with Groq endpoints securely and efficiently.
