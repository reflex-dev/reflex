# Python Package Index

```python exec
import reflex as rx

image_style = {
    "width": "400px",
    "border_radius": "12px",
    "border": "1px solid var(--c-slate-5)",
}
```

In order to publish a Python package, you need to use a publishing utility. Any would work, but we recommend either [Twine](https://twine.readthedocs.io/en/stable/) or [uv](https://docs.astral.sh/uv/guides/package/#publishing-your-package).

## PyPI

It is straightforward to create accounts and API tokens with PyPI. There is official help on the [PyPI website](https://pypi.org/help/). For a quick reference here, go to the top right corner of the PyPI website and look for the button to register and fill out personal information.

```python eval
rx.center(
    rx.image(
        src="https://web.reflex-assets.dev/custom_components/pypi_register.webp",
        style=image_style,
        margin_bottom="16px",
        loading="lazy",
    ),
)
```

A user can use username and password to authenticate with PyPI when publishing.

```python eval
rx.center(
    rx.image(
        src="https://web.reflex-assets.dev/custom_components/pypi_account_settings.webp",
        style=image_style,
        margin_bottom="16px",
        loading="lazy",
    ),
)
```

Scroll down to the API tokens section and click on the "Add API token" button. Fill out the form and click "Generate API token".

```python eval
rx.center(
    rx.image(
        src="https://web.reflex-assets.dev/custom_components/pypi_api_tokens.webp",
        style=image_style,
        width="700px",
        loading="lazy",
    ),
)
```
