---
tags: AI
description: Connect your apps to Google’s Gemini models for advanced AI capabilities.
---
# Gemini Integration

The **Gemini Integration** allows your app to use [Google’s Gemini models](https://aistudio.google.com/) for text generation, reasoning, multimodal analysis, and other advanced AI capabilities. Once connected, you can call Gemini directly from your workflows, UI actions, or automated triggers.

## Step 1: Obtain a Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/).
2. Navigate to **Get API Key** or create a new key for your project.
3. Copy the generated key.


## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab and select the **Gemini** card.
2. Click **Add connection** and paste your Gemini API key into **GOOGLE_API_KEY**.
3. Click **Connect** to save the connection.

Leave **GEMINI_BASE_URL** at its default (`https://generativelanguage.googleapis.com`) unless you send requests through a proxy or gateway.

Once connected, your app can use Gemini for AI-powered features across workflows and components.

## Step 3: Notes

* **Keep your key secure:** Do not hardcode your Gemini API key in public code repositories.  
* **Use environment-specific keys:** Separate dev, staging, and production keys help manage access and security.  
* **Secure API access:** The key allows your app to interact with Gemini endpoints securely and efficiently.
