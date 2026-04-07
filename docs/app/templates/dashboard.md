---
title: dashboard
description: "Interactive dashboard with real-time data visualization"
author: "Reflex"
image: "dashboard.webp"
demo: "https://dashboard-new.reflex.run/"
source: "https://github.com/reflex-dev/templates/tree/main/dashboard"
meta: [
    {"name": "keywords", "content": ""},
]
tags: ["Dashboard", "Data Visualization"]
---

The following is a dashboard to interactively display data some data. It is a good starting point for building more complex apps that require data visualization.

## Setup

To run this app locally, install Reflex and run:

```bash
reflex init --template dashboard
```

To run the app, use:

```bash
reflex run
```

## Customizing to your data

Right now the apps reads from a local CSV file. You can modify this by changing the `DATA_FILE` variable in the `dashboard/dashboard/backend/table_state.py` file.

Additionally you will want to change the `Item` class to match the data in your CSV file.

```python
import dataclasses

@dataclasses.dataclass
class Item:
    """The item class."""

    name: str
    payment: float
    date: str
    status: str
```
