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
            "link": "/docs/enterprise/ag-grid/",
            "components": [
                ("Overview", "/docs/enterprise/ag-grid/"),
                ("Column Definitions", "/docs/enterprise/ag-grid/column-defs/"),
                ("Aligned Grids", "/docs/enterprise/ag-grid/aligned-grids/"),
                ("Model Wrapper", "/docs/enterprise/ag-grid/model-wrapper/"),
                ("Pivot Mode", "/docs/enterprise/ag-grid/pivot-mode/"),
                ("Theme", "/docs/enterprise/ag-grid/theme/"),
                ("Value Transformers", "/docs/enterprise/ag-grid/value-transformers/"),
            ],
        },
        {
            "title": "AG Chart",
            "description": "Interactive charts and data visualization",
            "link": "/docs/enterprise/ag-chart/",
            "components": [
                ("Overview", "/docs/enterprise/ag-chart/"),
            ],
        },
        {
            "title": "Interactive Components",
            "description": "Drag-and-drop and mapping functionality",
            "link": "/docs/enterprise/drag-and-drop/",
            "components": [
                ("Drag and Drop", "/docs/enterprise/drag-and-drop/"),
                ("Mapping", "/docs/enterprise/map/"),
            ],
        },
        {
            "title": "Mantine",
            "description": "Rich UI components from Mantine library",
            "link": "/docs/enterprise/mantine/",
            "components": [
                ("Overview", "/docs/enterprise/mantine/"),
                ("Autocomplete", "/docs/enterprise/mantine/autocomplete/"),
                ("Collapse", "/docs/enterprise/mantine/collapse/"),
                ("Combobox", "/docs/enterprise/mantine/combobox/"),
                ("JSON Input", "/docs/enterprise/mantine/json-input/"),
                ("Loading Overlay", "/docs/enterprise/mantine/loading-overlay/"),
                ("Multi Select", "/docs/enterprise/mantine/multi-select/"),
                ("Number Formatter", "/docs/enterprise/mantine/number-formatter/"),
                ("Pill", "/docs/enterprise/mantine/pill/"),
                ("Ring Progress", "/docs/enterprise/mantine/ring-progress/"),
                (
                    "Semi Circle Progress",
                    "/docs/enterprise/mantine/semi-circle-progress/",
                ),
                ("Spoiler", "/docs/enterprise/mantine/spoiler/"),
                ("Tags Input", "/docs/enterprise/mantine/tags-input/"),
                ("Timeline", "/docs/enterprise/mantine/timeline/"),
                ("Tree", "/docs/enterprise/mantine/tree/"),
            ],
        },
    ]

    cards = []
    for section in sections:
        cards.append(
            rx.box(
                rx.link(
                    rx.el.h1(
                        section["title"],
                        class_name="font-large text-slate-12",
                    ),
                    rx.icon("arrow_up_right", size=16, class_name="text-slate-11"),
                    href=section["link"],
                    underline="none",
                    class_name="px-4 py-2 bg-slate-1 hover:bg-slate-3 transition-bg flex flex-row justify-between items-center !text-slate-12",
                ),
                rx.text(
                    section["description"],
                    class_name="px-4 py-2 font-small text-slate-9 border-t border-slate-5",
                ),
                rx.box(
                    *[
                        rx.link(
                            comp[0],
                            href=comp[1],
                            class_name="font-small text-slate-11 hover:!text-violet-9 transition-color w-fit",
                        )
                        for comp in section["components"]
                    ],
                    class_name="flex flex-col gap-2.5 px-4 py-2 border-t border-slate-5",
                ),
                class_name="flex flex-col border border-slate-5 rounded-xl bg-slate-2 shadow-large overflow-hidden",
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
    class_name="font-[475] text-secondary-11 max-w-[80%] text-sm",
)
```

```python eval
component_grid
```