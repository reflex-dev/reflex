---
components:
  - rx.theme
  - rx.theme_panel
---

# Theme

The `Theme` component is used to change the theme of the application. Configure
the app-level theme in `rxconfig.py` with `RadixThemesPlugin`.

```python
import reflex as rx

config = rx.Config(
    app_name="my_app",
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(
                appearance="light",
                has_background=True,
                radius="large",
                accent_color="teal",
            )
        ),
    ],
)
```

# Theme Panel

The `ThemePanel` component is a container for the `Theme` component. It provides a way to change the theme of the application.

```python
rx.theme_panel()
```

The theme panel is closed by default. You can set it open `default_open=True`.

```python
rx.theme_panel(default_open=True)
```
