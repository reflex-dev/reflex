---
tags: AI
description: Connect your apps to Groq’s ultra-fast inference API for lightning-speed AI responses.
---
# Groq Integration

The **Groq Integration** allows your app to use [Groq’s API](https://groq.com/) for ultra-fast AI inference. Once connected, your app can leverage Groq’s hosted models (including open models like Llama 4 and Qwen) to power real-time workflows, chat experiences, and other AI-driven features.

## Step 1: Obtain a Groq API Key

1. Go to the [Groq Console](https://console.groq.com/).  
2. Navigate to **API Keys** in your account settings.  
3. Click **Create API Key** and give it a descriptive name (e.g., “AI Builder”).  
4. Copy the generated key.
   * **Example:** `gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Step 2: Configure the Integration in Your App

1. Go to **Integrations → Add Groq** in your app settings.  
2. Paste your **Groq API Key** in the input field.  
3. Click **Connect** to validate and save your integration.

Once connected, your app can use Groq to deliver ultra-low latency AI responses across workflows and components.

## Step 3: Notes

* **Keep your key secure:** Do not hardcode your Groq API key in public code repositories.  
* **Use environment-specific keys:** Separate dev, staging, and production keys help manage access and security.  
* **Secure API access:** The key allows your app to interact with Groq endpoints securely and efficiently.
