---
title: sales
description: "Sales app with interactive charts and real-time data updates"
author: "Reflex"
image: "sales.webp"
demo: "https://sales-new.reflex.run/"
source: "https://github.com/reflex-dev/templates/tree/main/sales"
meta: [
    {"name": "keywords", "content": ""},
]
tags: ["Marketing", "Dashboard"]
---

The following is a sales app that displays sales data. The table tab allows filtering and live updates. The graph tab shows the relationship between sales data.

## Setup

To run this app locally, install Reflex and run:

```bash
reflex init --template sales
```

To run the app, use:

Set the OpenAI API key:
```
export OPEN_AI_KEY=your-openai-api-key
```

```bash
pip install -r requirements.txt
reflex run
```

## Customizing the Inference

Note: You can get your OpenAI API key [here](https://platform.openai.com/account/api-keys).

You can customize the app by modifying the `sales/sales/backend/backend.py` file replacing OpenAI's API with that of other LLM providers.