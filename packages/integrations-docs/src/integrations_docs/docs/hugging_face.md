---
tags: AI
description: Connect your apps to Hugging Face to access thousands of open models for text, vision, and multimodal tasks.
---
# Hugging Face Integration

The **Hugging Face Integration** allows your app to use [Hugging Face](https://huggingface.co/) models for a wide range of AI tasks — including text generation, embeddings, translation, classification, image processing, and more. You can integrate both hosted models (via API) or local open-source models through the Transformers library.

## What You Can Do

With Hugging Face, your app can:
- Access thousands of pre-trained **text, vision, and multimodal models**.  
- Run **text generation**, summarization, translation, and classification tasks.  
- Use **embeddings** for search, retrieval, and similarity.  
- Deploy models locally with `transformers` or connect to hosted inference endpoints.  
- Fine-tune or customize open models for your specific use cases.  
- Integrate community and enterprise models seamlessly into workflows.

## Step 1: Obtain a Hugging Face Access Token (Optional)

1. Go to [Hugging Face](https://huggingface.co/).  
2. Log in or create a free account.  
3. Navigate to **Settings → Access Tokens**.  
4. Click **Create New token**, set its scope, and copy it.
   * **Example:** `hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`


## Step 2: Configure the Integration in Your App

1. Go to **Integrations → Add Hugging Face** in your app settings.  
2. Paste your **Hugging Face Access Token** if required.  
3. Click **Connect** to validate and save your integration.

Once connected, your app can use Hugging Face models directly in workflows, UI actions, or automations.

## Step 3: Notes

* **Keep your token secure:** Never expose your Hugging Face token in client-side code.  
* **Use environment-specific tokens:** Separate dev, staging, and production access.  
* **Open-source flexibility:** Models can be run fully locally or through Hugging Face’s hosted endpoints.  
* **Broad ecosystem:** Hugging Face supports thousands of community and commercial models for rapid prototyping and production use.
