---
title: Enterprise Components
---

```python exec
import reflex as rx

from reflex_docs.components.component_catalog import component_category
from reflex_docs.templates.docpage import h1_comp, text_comp_2


def enterprise_component_grid():
    sections = [
        {
            "title": "AG Grid",
            "description": "Advanced data grid with sorting, filtering, editing, and pagination",
            "link": "/enterprise/ag-grid/",
            "components": [
                ("Overview", "/enterprise/ag-grid/"),
                ("Column Definitions", "/enterprise/ag-grid/column-defs/"),
                ("Aligned Grids", "/enterprise/ag-grid/aligned-grids/"),
                ("Model Wrapper", "/enterprise/ag-grid/model-wrapper/"),
                ("Pivot Mode", "/enterprise/ag-grid/pivot-mode/"),
                ("Theme", "/enterprise/ag-grid/theme/"),
                ("Value Transformers", "/enterprise/ag-grid/value-transformers/"),
            ],
        },
        {
            "title": "AG Chart",
            "description": "Interactive charts and data visualization",
            "link": "/enterprise/ag-chart/",
            "components": [
                ("Overview", "/enterprise/ag-chart/"),
            ],
        },
        {
            "title": "Interactive Components",
            "description": "Drag-and-drop and mapping functionality",
            "link": "/enterprise/drag-and-drop/",
            "components": [
                ("Drag and Drop", "/enterprise/drag-and-drop/"),
                ("Mapping", "/enterprise/map/"),
            ],
        },
        {
            "title": "Mantine",
            "description": "Rich UI components from Mantine library",
            "link": "/enterprise/mantine/",
            "components": [
                ("Overview", "/enterprise/mantine/"),
                ("Autocomplete", "/enterprise/mantine/autocomplete/"),
                ("Collapse", "/enterprise/mantine/collapse/"),
                ("Combobox", "/enterprise/mantine/combobox/"),
                ("JSON Input", "/enterprise/mantine/json-input/"),
                ("Loading Overlay", "/enterprise/mantine/loading-overlay/"),
                ("Multi Select", "/enterprise/mantine/multi-select/"),
                ("Number Formatter", "/enterprise/mantine/number-formatter/"),
                ("Pill", "/enterprise/mantine/pill/"),
                ("Ring Progress", "/enterprise/mantine/ring-progress/"),
                (
                    "Semi Circle Progress",
                    "/enterprise/mantine/semi-circle-progress/",
                ),
                ("Spoiler", "/enterprise/mantine/spoiler/"),
                ("Tags Input", "/enterprise/mantine/tags-input/"),
                ("Timeline", "/enterprise/mantine/timeline/"),
                ("Tree", "/enterprise/mantine/tree/"),
            ],
        },
    ]

    return rx.box(
        *[
            component_category(
                title=section["title"],
                href=section["link"],
                description=section["description"],
                links=section["components"],
            )
            for section in sections
        ],
        class_name="docs-enterprise-catalog flex flex-col mt-8 mb-12",
    )


component_grid = enterprise_component_grid()
```

```python eval
h1_comp(text="Enterprise Components")
```

```python eval
text_comp_2(
    text="Advanced UI components and features to enhance your Reflex applications. Available for free with the 'Built with Reflex' badge, or without the badge with an enterprise license.",
)
```

```python eval
component_grid
```
