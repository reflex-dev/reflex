---
tags: AI
description: Connect your apps to Replicate to run and deploy open-source machine learning models with ease.
---
# Replicate Integration

The **Replicate Integration** allows your app to use [Replicate](https://replicate.com/) to run open-source AI models in the cloud without managing infrastructure. Once connected, you can use Replicate to generate text, images, audio, and more — directly from workflows and UI actions.

## What You Can Do

With Replicate, your app can:
- Run open-source **AI models** without GPU or hosting setup.  
- Access models for **text generation**, **image generation**, **audio**, and **multimodal tasks**.  
- Automate workflows like content generation, data processing, or AI-powered features.  
- Use prebuilt models or deploy your own custom models.  
- Scale effortlessly with serverless infrastructure.

## Step 1: Obtain a Replicate API Token

1. Go to the [Replicate Dashboard](https://replicate.com/account).  
2. Log in or create an account.
3. Navigate to the **API Tokens** section.  
4. Copy your **API Token** from the account page.

   * **Example:** `r8_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Step 2: Configure the Integration in Your App

1. Go to **Integrations → Add Replicate** in your app settings.  
2. Paste your **Replicate API Token** in the input field.  
3. Click **Connect** to validate and save your integration.

Once connected, your app can call Replicate models directly in workflows, UI actions, or automations.

## Step 3: Notes

* **Keep your token secure:** Do not hardcode your Replicate token in public code repositories.  
* **Use environment-specific tokens:** Separate dev, staging, and production environments for security.  
* **Secure API access:** The token allows your app to interact with Replicate endpoints safely and efficiently.  
* **Model flexibility:** You can use community models or deploy your own for full control.
