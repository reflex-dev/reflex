```python exec
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN
```

# Assets

Static files such as images and stylesheets can be placed in `assets/` folder of the project. These files can be referenced within your app.

```md alert
# Assets are copied during the build process.

Any files placed within the `assets/` folder at runtime will not be available to the app
when running in production mode. The `assets/` folder should only be used for static files.
```

## Referencing Assets

There are two ways to reference assets in your Reflex app:

### 1. Direct Path Reference

To reference an image in the `assets/` folder, pass the relative path as a prop.

For example, you can store your logo in your assets folder:

```bash
assets
└── Reflex.svg
```

Then you can display it using a `rx.image` component:

```python demo
rx.image(src=f"{REFLEX_ASSETS_CDN}other/Reflex.svg", width="5em")
```

```md alert
# Always prefix the asset path with a forward slash `/` to reference the asset from the root of the project, or it may not display correctly on non-root pages.
```

### 2. Using rx.asset Function

The `rx.asset` function provides a more flexible way to reference assets in your app. It supports both local assets (in the app's `assets/` directory) and shared assets (placed next to your Python files).

#### Local Assets

Local assets are stored in the app's `assets/` directory and are referenced using `rx.asset`:

```python demo
rx.image(src=rx.asset("Reflex.svg"), width="5em")
```

#### Shared Assets

Shared assets are placed next to your Python file and are linked to the app's external assets directory. This is useful for creating reusable components with their own assets:

```python box
# my_component.py
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN

# my_script.js is located in the same directory as this Python file
def my_component():
    return rx.box(
        rx.script(src=rx.asset("my_script.js", shared=True)),
        "Component with custom script"
    )
```

You can also specify a subfolder for shared assets:

```python box
# my_component.py
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN

# image.png is located in a subfolder next to this Python file
def my_component_with_image():
    return rx.image(
        src=rx.asset("image.png", shared=True, subfolder="images")
    )
```

```md alert
# Shared assets are linked to your app via symlinks.

When using `shared=True`, the asset is symlinked from its original location to your app's external assets directory. This allows you to keep assets alongside their related code.
```

## Favicon

The favicon is the small icon that appears in the browser tab.

You can add a `favicon.ico` file to the `assets/` folder to change the favicon.
