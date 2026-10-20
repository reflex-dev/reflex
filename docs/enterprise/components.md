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
                        class_name="font-large text-foreground",
                    ),
                    rx.icon(
                        "arrow_up_right", size=16, class_name="text-muted-foreground"
                    ),
                    href=section["link"],
                    underline="none",
                    class_name="px-4 py-2 bg-background hover:bg-accent transition-bg flex flex-row justify-between items-center !text-foreground",
                ),
                rx.text(
                    section["description"],
                    class_name="px-4 py-2 font-small text-subtle-foreground border-t border-border",
                ),
                rx.box(
                    *[
                        rx.link(
                            comp[0],
                            href=comp[1],
                            class_name="font-small text-muted-foreground hover:!text-primary transition-color w-fit",
                        )
                        for comp in section["components"]
                    ],
                    class_name="flex flex-col gap-2.5 px-4 py-2 border-t border-border",
                ),
                class_name="flex flex-col border border-border rounded-xl bg-muted shadow-large overflow-hidden",
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
    class_name="lg:text-5xl text-3xl font-[525] scroll-mt-[113px] my-4 text-foreground",
)
```

```python eval
rx.el.span(
    "Advanced UI components and features to enhance your Reflex applications. Available for free with the 'Built with Reflex' badge, or without the badge with an enterprise license.",
    class_name="font-[475] text-muted-foreground max-w-[80%] text-sm",
)
```

```python eval
component_grid
```