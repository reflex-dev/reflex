---
title: Reflex Enterprise
---

# Reflex Enterprise

```python exec
from pcweb.pages.docs import enterprise
import reflex as rx
try:
    import reflex_enterprise as rxe
    from reflex_enterprise.components.ag_grid.resource import RendererParams
except ImportError:
    rxe = None
    RendererParams = None
```

Reflex Enterprise is a package containing paid features built on top of Reflex.

```md alert info
# Despite being an enterprise package, free users can use the components from this package. A badge "Built with Reflex" will be shown in the bottom right corner of the app.
For more information on the badge, visit [Built with Reflex]({enterprise.built_with_reflex.path}).
```

## Installation

`reflex-enterprise` must be installed alongside `reflex` to access the enterprise features.

You can install it from pypi with the following command:

```bash
pip install reflex-enterprise
```

## Features

```python exec
# Create master data organized by category
categories_data = [
    {
        "category": "Configuration",
        "description": "Core enterprise features for deployment and branding",
        "count": 2,
        "components": [
            {
                "feature": "show_built_with_reflex", 
                "description": "Toggle the 'Built with Reflex' badge in your app", 
                "cloud_tier": "Enterprise", 
                "self_hosted_tier": "Enterprise",
                "link": "/docs/enterprise/built-with-reflex",
            },
            {
                "feature": "use_single_port", 
                "description": "Enable single-port deployment by proxying backend to frontend", 
                "cloud_tier": "Free", 
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/single-port-proxy",
            },
        ]
    },
    {
        "category": "AGGrid and AGChart",
        "description": "Advanced data visualization and grid components",
        "count": 2,
        "components": [
            {
                "feature": "AgGrid",
                "description": "Advanced data grid with enterprise features (sorting, filtering, grouping)",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/ag-grid",
            },
            {
                "feature": "AGCharts",
                "description": "Interactive charts and data visualization components",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/ag-chart",
            },
        ]
    },    
    {
        "category": "Interactive Components",
        "description": "Interactive UI features including drag-and-drop and mapping",
        "count": 2,
        "components": [
            {
                "feature": "Drag and Drop",
                "description": "Drag and drop functionality for interactive UI elements",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/drag-and-drop",
            },
            {
                "feature": "Mapping",
                "description": "Interactive maps with markers, layers, and controls",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/map",
            },
        ]
    },
    {
        "category": "Mantine",
        "description": "Rich UI components from Mantine library",
        "count": 15,
        "components": [
            {
                "feature": "Autocomplete",
                "description": "Auto-completing text input with dropdown suggestions",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/mantine/autocomplete",
            },
            {
                "feature": "Combobox",
                "description": "Searchable dropdown with custom options and filtering",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/mantine/combobox",
            },
            {
                "feature": "Multi Select",
                "description": "Multi-selection dropdown with tags and search",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/mantine/multi-select",
            },
            {
                "feature": "Tags Input",
                "description": "Input field for creating and managing tags",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/mantine/tags-input",
            },
            {
                "feature": "Json Input",
                "description": "JSON editor with syntax highlighting and validation",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/mantine/json-input",
            },
            {
                "feature": "Pill",
                "description": "Small rounded elements for tags, badges, and labels",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/mantine/pill",
            },
            {
                "feature": "Tree",
                "description": "Hierarchical tree view with expandable nodes",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/mantine/tree",
            },
            {
                "feature": "Timeline",
                "description": "Timeline component for displaying chronological events",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/mantine/timeline",
            },
            {
                "feature": "Number Formatter",
                "description": "Format and display numbers with customizable formatting",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/mantine/number-formatter",
            },
            {
                "feature": "Ring Progress",
                "description": "Circular progress indicator with customizable styling",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/mantine/ring-progress",
            },
            {
                "feature": "Semi Circle Progress",
                "description": "Semi-circular progress indicator for dashboards",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/mantine/semi-circle-progress",
            },
            {
                "feature": "Loading Overlay",
                "description": "Loading overlay with spinner for async operations",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/mantine/loading-overlay",
            },
            {
                "feature": "Spoiler",
                "description": "Collapsible content container with show/hide toggle",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/mantine/spoiler",
            },
            {
                "feature": "Collapse",
                "description": "Animated collapsible content with smooth transitions",
                "cloud_tier": "Free",
                "self_hosted_tier": "Free",
                "link": "/docs/enterprise/mantine/collapse",
            },
        ]
    },
]

if rxe is not None:
    @rxe.arrow_func
    def custom_link_renderer(params: RendererParams):
        """Custom cell renderer for links in AG Grid."""
        return rx.link(
            params.value,
            href=params.data.link,
        )

    grid = rxe.ag_grid(
    column_defs=[
        {
            "field": "category", 
            "header_name": "Category", 
            "cell_renderer": "agGroupCellRenderer",
            "suppress_menu": True,
            "width": 220,
        },
        {
            "field": "description",
            "width": 500,
        },
        {
            "field": "count",
            "header_name": "Components",
            "width": 150,
        },
    ],
    row_data=categories_data,
    master_detail=True,
    detail_cell_renderer_params={
        "detail_grid_options": {
            "column_defs": [
                {
                    "field": "feature", 
                    "header_name": "Component/Feature", 
                    "cell_renderer": custom_link_renderer, 
                    "width": 250
                },
                {"field": "description", "header_name": "Description", "width": 350},
                {"field": "cloud_tier", "header_name": "Cloud Tier", "width": 120},
                {"field": "self_hosted_tier", "header_name": "Self-hosted Tier", "width": 140},
            ],
            "suppress_context_menu": True,
            "row_height": 35,
        },
        "get_detail_row_data": lambda params: rx.vars.function.FunctionStringVar(
            "params.successCallback"
        ).call(params.data.components),
    },
    id="features-grid",
    width="100%",
    detail_row_height=200,
    detail_row_auto_height=True,
    height="400px",
    loading=False,
)
    grid.api.set_grid_option("suppressContextMenu", True)
else:
    grid = rx.text("Reflex Enterprise not available. Install with: pip install reflex-enterprise")
```

```python eval
grid
```

## Usage of reflex_enterprise.

Using `rxe.App` as your `app` is required to use any of the components provided by the enterprise package, as well as config options provided by `rxe.Config`.

### In the main file

Instead of the usual `rx.App()` to create your app, use the following:
```python
import reflex_enterprise as rxe
app = rxe.App()
```

### In rxconfig.py
```python
import reflex_enterprise as rxe
config = rxe.Config(
    app_name="MyApp",
    ... # you can pass all rx.Config arguments as well as the one specific to rxe.Config
)
```