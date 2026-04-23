---
title: customer_data_app
description: "A Reflex app for customer data management with visualizations"
author: "Reflex"
image: "customer-app.webp"
demo: "https://customer-data-app.reflex.run/"
source: "https://github.com/reflex-dev/templates/tree/main/customer_data_app"
meta: [
    {"name": "keywords", "content": ""},
]
tags: ["Data Visualization"]
---

The following is a python dashboard to interactively display some data, i.e. customer data. The app allows you to add, edit, and delete customer data in a table, as well as visualize the changes in data over time. All the data is stored in a database. It is a good starting point for building more complex apps that require data visualization and editing.

## Setup

To run this app locally, install Reflex and run:

```bash
reflex init --template customer_data_app
```

To run the app, use:

```bash
pip install -r requirements.txt
reflex db migrate
reflex run
```


## Setting an external Database

It is also possible to set an external database so that your data is not lost every time the app closes and so you can deploy your app and maintain data.

In the `rxconfig.py` file we accept a `DATABASE_URL` environment variable.

To set one run the following command in your terminal:

```bash
export DATABASE_URL="<YOUR URL KEY>"
```


## Customizing the Database Model

We define our `Customer` model in the `customer_data_app/customer_data_app/backend/backend.py` file. The model is used to store customer data in the database. You can customize the model to input your own data here.

It will also be necessary to edit some of the event handlers inside of `State` in the same file and to edit some of the UI components in `customer_data_app/customer_data_app/views/table.py` to reflect the changes in the model.
