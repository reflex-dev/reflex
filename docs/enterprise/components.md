---
title: Enterprise Components
---

```python exec
import reflex as rx


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

    cards = []
    for section in sections:
        cards.append(
            rx.box(
                rx.link(
                    rx.el.h2(
                        section["title"],
                        class_name="text-lg font-book text-foreground",
                    ),
                    rx.icon("arrow_up_right", size=16, class_name="text-secondary-11"),
                    href=section["link"],
                    underline="none",
                    class_name="px-5 py-4 hover:bg-muted transition-colors flex flex-row justify-between gap-3 items-center !text-foreground focus-visible:outline-2 focus-visible:outline-ring",
                ),
                rx.text(
                    section["description"],
                    class_name="px-5 pb-4 text-sm font-normal leading-6 text-muted-foreground",
                ),
                rx.box(
                    *[
                        rx.link(
                            comp[0],
                            href=comp[1],
                            class_name="text-sm font-book text-muted-foreground hover:!text-foreground transition-colors w-fit rounded-sm focus-visible:outline-2 focus-visible:outline-ring",
                        )
                        for comp in section["components"]
                    ],
                    class_name="flex flex-col gap-2 px-5 pb-5",
                ),
                class_name="flex flex-col border border-border-subtle rounded-card bg-background overflow-hidden",
            )
        )

    return rx.box(
        *cards,
        class_name="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8",
    )


component_grid = enterprise_component_grid()
```

```python eval
rx.el.h1(
    "Enterprise Components",
    class_name="lg:text-5xl text-3xl font-[525] scroll-mt-[113px] my-4 text-secondary-12",
)
```

```python eval
rx.el.span(
    "Advanced UI components and features to enhance your Reflex applications. Available for free with the 'Built with Reflex' badge, or without the badge with an enterprise license.",
    class_name="font-normal text-muted-foreground max-w-2xl text-base leading-7",
)
```

```python eval
component_grid
```
