---
title: Enterprise Components
---

```python exec
import reflex as rx
from pcweb.pages.docs import enterprise
from pcweb.templates.docpage import h1_comp, text_comp_2
from pcweb.components.icons import get_icon

def enterprise_component_grid():
    sections = [
        {
            "title": "AG Grid",
            "description": "Advanced data grid with sorting, filtering, editing, and pagination",
            "link": enterprise.ag_grid.index.path,
            "components": [
                ("Overview", enterprise.ag_grid.index.path),
                ("Column Definitions", enterprise.ag_grid.column_defs.path),
                ("Aligned Grids", enterprise.ag_grid.aligned_grids.path),
                ("Model Wrapper", enterprise.ag_grid.model_wrapper.path),
                ("Pivot Mode", enterprise.ag_grid.pivot_mode.path),
                ("Theme", enterprise.ag_grid.theme.path),
                ("Value Transformers", enterprise.ag_grid.value_transformers.path),
            ]
        },
        {
            "title": "AG Chart", 
            "description": "Interactive charts and data visualization",
            "link": enterprise.ag_chart.path,
            "components": [
                ("Overview", enterprise.ag_chart.path),
            ]
        },
        {
            "title": "Interactive Components",
            "description": "Drag-and-drop and mapping functionality", 
            "link": enterprise.drag_and_drop.path,
            "components": [
                ("Drag and Drop", enterprise.drag_and_drop.path),
                ("Mapping", enterprise.map.index.path),
            ]
        },
        {
            "title": "Mantine",
            "description": "Rich UI components from Mantine library",
            "link": enterprise.mantine.index.path,
            "components": [
                ("Overview", enterprise.mantine.index.path),
                ("Autocomplete", enterprise.mantine.autocomplete.path),
                ("Collapse", enterprise.mantine.collapse.path),
                ("Combobox", enterprise.mantine.combobox.path),
                ("JSON Input", enterprise.mantine.json_input.path),
                ("Loading Overlay", enterprise.mantine.loading_overlay.path),
                ("Multi Select", enterprise.mantine.multi_select.path),
                ("Number Formatter", enterprise.mantine.number_formatter.path),
                ("Pill", enterprise.mantine.pill.path),
                ("Ring Progress", enterprise.mantine.ring_progress.path),
                ("Semi Circle Progress", enterprise.mantine.semi_circle_progress.path),
                ("Spoiler", enterprise.mantine.spoiler.path),
                ("Tags Input", enterprise.mantine.tags_input.path),
                ("Timeline", enterprise.mantine.timeline.path),
                ("Tree", enterprise.mantine.tree.path),
            ]
        }
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
                    get_icon("new_tab", class_name="text-slate-11 [&>svg]:size-4"),
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
        class_name="grid grid-cols-1 lg:grid-cols-2 gap-6",
    )

component_grid = enterprise_component_grid()
```

```python eval
h1_comp(text="Enterprise Components")
```

```python eval
text_comp_2(text="Advanced UI components and features to enhance your Reflex applications. Available for free with the 'Built with Reflex' badge, or without the badge with an enterprise license.")
```

```python eval
component_grid
```