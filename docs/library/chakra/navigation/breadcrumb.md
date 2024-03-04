---
components:
    - rx.chakra.Breadcrumb
    - rx.chakra.BreadcrumbItem
    - rx.chakra.BreadcrumbLink
---

```python exec
import reflex as rx
```

# Breadcrumb

Breadcrumbs, or a breadcrumb navigation, can help enhance how users navigate to previous page levels of a website.

This is userful for websites with a lot of pages.

```python demo
rx.chakra.breadcrumb(
    rx.chakra.breadcrumb_item(rx.chakra.breadcrumb_link("Home", href="#")),
    rx.chakra.breadcrumb_item(rx.chakra.breadcrumb_link("Docs", href="#")),
    rx.chakra.breadcrumb_item(rx.chakra.breadcrumb_link("Breadcrumb", href="#")),
)
```

The separator prop can be used to change the default separator.

```python demo
rx.chakra.breadcrumb(
    rx.chakra.breadcrumb_item(rx.chakra.breadcrumb_link("Home", href="#")),
    rx.chakra.breadcrumb_item(rx.chakra.breadcrumb_link("Docs", href="#")),
    rx.chakra.breadcrumb_item(rx.chakra.breadcrumb_link("Breadcrumb", href="#")),
    separator=">",
    color="rgb(107,99,246)"
)
```
