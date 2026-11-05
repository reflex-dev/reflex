---
tags: AI
description: Connect your apps to Hugging Face to access thousands of open models for text, vision, and multimodal tasks.
---
# Hugging Face Integration

The **Hugging Face Integration** allows your app to use [Hugging Face](https://huggingface.co/) models for a wide range of AI tasks — including text generation, embeddings, translation, classification, image processing, and more. Your app calls hosted models through the `huggingface_hub` client.

## What You Can Do

With Hugging Face, your app can:
- Access thousands of pre-trained **text, vision, and multimodal models**.  
- Run **text generation**, summarization, translation, and classification tasks.  
- Use **embeddings** for search, retrieval, and similarity.  
- Call hosted models through Hugging Face Inference Providers or your own Inference Endpoints.  
- Fine-tune or customize open models for your specific use cases.  
- Integrate community and enterprise models seamlessly into workflows.

## Step 1: Obtain a Hugging Face Access Token

1. Go to [Hugging Face](https://huggingface.co/).  
2. Log in or create a free account.  
3. Navigate to **Settings → Access Tokens**.  
4. Click **Create New token**, set its scope, and copy it.
   * **Example:** `hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`


## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab and select the **Hugging Face** card.
2. Click **Add connection** and paste your access token into **HUGGINGFACE_API_KEY** (required).
3. Click **Connect** to save the connection.

Once connected, your app can use Hugging Face models directly in workflows, UI actions, or automations.

## Step 3: Notes

* **Keep your token secure:** Never expose your Hugging Face token in client-side code.  
* **Use environment-specific tokens:** Separate dev, staging, and production access.  
* **Hosted inference:** Requests run on Hugging Face’s hosted infrastructure, so your app needs no GPU.  
* **Broad ecosystem:** Hugging Face supports thousands of community and commercial models for rapid prototyping and production use.
