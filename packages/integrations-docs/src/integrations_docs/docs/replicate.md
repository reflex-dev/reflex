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

1. Go to [Replicate](https://replicate.com/).
2. Log in or create an account.
3. Open the [API tokens](https://replicate.com/account/api-tokens) page.
4. Copy the default token created when you signed up, or create a new one.

   * **Example:** `r8_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab and select the **Replicate** card.
2. Click **Add connection** and paste your API token into **REPLICATE_API_TOKEN**.
3. Click **Connect** to save the connection.

Once connected, your app can call Replicate models directly in workflows, UI actions, or automations.

## Step 3: Notes

* **Keep your token secure:** Do not hardcode your Replicate token in public code repositories.  
* **Use environment-specific tokens:** Separate dev, staging, and production environments for security.  
* **Secure API access:** The token allows your app to interact with Replicate endpoints safely and efficiently.  
* **Model flexibility:** You can use community models or deploy your own for full control.
