---
title: ai_image_gen
description: "Generate AI images using Replicate's API"
author: "Reflex"
image: "image-gen.webp"
demo: "https://ai-image-gen.reflex.run/"
source: "https://github.com/reflex-dev/templates/tree/main/ai_image_gen"
meta: [
    {"name": "keywords", "content": "image generation, ai image generation, reflex image generation, Replicate image generation"},
]
tags: ["AI/ML", "Image Generation"]
---

The following is an app that allows you to generate AI images. The current map uses replicate's api to generate images but can be easily modified to use other image generation services.

## Setup

To run this app locally, install Reflex and run:

```bash
reflex init --template ai_image_gen
```

To run the app, set the `REPLICATE_API_TOKEN`:

```bash
export REPLICATE_API_TOKEN=your_api_token_here
```

Then run:

```bash
pip install -r requirements.txt
reflex run
```

Note: You can get your replicate api token [here](https://replicate.com/account/api-tokens).

## Customizing the Inference

You can customize the app by modifying the [`generation.py`](https://github.com/reflex-dev/templates/blob/main/ai_image_gen/ai_image_gen/backend/generation.py) file replacing replicate's api with that of other image generation services.