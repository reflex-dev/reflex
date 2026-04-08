---
tags: AI
description: Connect your apps to Roboflow to use computer vision models and datasets for image detection, classification, and segmentation.
---
# Roboflow Integration

The **Roboflow Integration** allows your app to use [Roboflow](https://roboflow.com/) to run and deploy computer vision models without complex infrastructure. Once connected, you can use Roboflow to power image detection, object tracking, classification, and segmentation workflows.

## What You Can Do

With Roboflow, your app can:
- Run **pre-trained computer vision models** for detection, classification, or segmentation.  
- Deploy and use **custom-trained models** built in Roboflow.  
- Automate workflows that rely on visual inputs — e.g., quality checks, object detection, image analysis.  
- Ingest and process **images in real time**.  
- Combine vision outputs with other integrations (e.g., AI reasoning, automation flows).

```md alert
## This integration currently supports image inputs only.
Video and streaming inputs are not yet supported.
```

## Step 1: Obtain a Roboflow API Key

1. Go to your [Roboflow Account](https://roboflow.com/).
2. Navigate to **Settings → API Keys**.  
3. Copy your Private API Key.


## Step 2: Set up your Model in Roboflow

1. Go to Workflows and create a new workflow.
2. Set up the workflow you want to use in your app, ensuring that it takes an image as input.
3. Click the `deploy` button, select `Images` and then select `Integrate with my app or website`.
4. Copy the `workspace_name` and `workflow_id` from the provided code snippet.

[!Roboflow](https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/docs/roboflow.webp)

## Step 3: Configure the Integration in Your App

1. Go to **Integrations → Add Roboflow** in your app settings.  
2. Paste your **Roboflow API Key**, **Workspace Name**, and **Workflow ID** in the input fields.  
3. Click **Connect** to validate and save your integration.

Once connected, your app can call Roboflow models directly from workflows, UI actions, or automated triggers.


## Step 4: Notes

* **Keep your key secure:** Never expose your Roboflow key in client-side code.  
* **Use environment-specific keys:** Separate dev, staging, and production keys to control access.  
* **Model flexibility:** Use community models or your own custom-trained models.  
* **Real-time vision:** Ideal for applications involving cameras, inspection, monitoring, or visual AI.
