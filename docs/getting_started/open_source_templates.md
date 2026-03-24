# Open Source Templates

Check out what the community is building with Reflex. See 2000+ more public projects on [Github](https://github.com/reflex-dev/reflex/network/dependents). Want to get your app featured? Submit it [here](https://github.com/reflex-dev/templates). Copy the template command and use it during `reflex init`

```python exec

import reflex as rx

from pcweb.components.code_card import gallery_app_card
from pcweb.components.webpage.comps import h1_title
from pcweb.pages.gallery.sidebar import TemplatesState, pagination, sidebar
from pcweb.templates.webpage import webpage


@rx.memo
def skeleton_card() -> rx.Component:
    return rx.skeleton(
        class_name="box-border shadow-large border rounded-xl w-full h-[280px] overflow-hidden",
        loading=True,
    )


def component_grid() -> rx.Component:
    from pcweb.pages.gallery.apps import gallery_apps_data

    posts = []
    for path, document in list(gallery_apps_data.items()):
        posts.append(
            rx.cond(
                TemplatesState.filtered_templates.contains(document.metadata["title"]),
                gallery_app_card(app=document.metadata),
                None,
            )
        )
    return rx.box(
        *posts,
        rx.box(
            rx.el.h4(
                "No templates found",
                class_name="text-base font-semibold text-slate-12 text-nowrap",
            ),
            class_name="flex-col gap-2 flex absolute left-1 top-0 z-[-1] w-full",
        ),
        class_name="gap-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 w-full relative",
    )


def gallery() -> rx.Component:
    return rx.el.section(
        rx.box(
            sidebar(),
            rx.box(
                component_grid(),
                pagination(),
                class_name="flex flex-col",
            ),
            class_name="flex flex-col gap-6 lg:gap-10 w-full",
        ),
        id="gallery",
        class_name="mx-auto",
    )

```

```python eval
gallery()
```
