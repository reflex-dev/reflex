---
title: api_admin_panel
description: "Interactive dashboard for API requests and response visualization"
author: "Reflex"
image: "api-admin-panel.webp"
demo: "https://api-admin-panel.reflex.run/"
source: "https://github.com/reflex-dev/templates/tree/main/api_admin_panel"
meta: [
    {"name": "keywords", "content": "admin panel, api admin panel, reflex admin panel"},
]
tags: ["API Tools"]
---

The following is an admin panel for reading from and writing to your customer data, built on a REST API. This app lets you look through customers and take custom actions based on the data.

## Setup

To run this app locally, install Reflex and run:

```bash
reflex init --template api_admin_panel
```

To run the app, use:

```bash
reflex run
```

## Usage

To use the app insert the desired endpoint click `New Request` then in the input field and click on the `Send` button. You can optionally add a body, headers, and cookies to the request. The response will be displayed in the table.

When clicking on a row the request and response will be displayed in the respective sections. You can further customize this app by adding custom actions to the rows and `Commit` and `Close` buttons.