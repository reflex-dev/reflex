```python exec
import reflex as rx
```

# Plugins

Reflex supports a plugin system that allows you to extend the framework's functionality during the compilation process. Plugins can add frontend dependencies, modify build configurations, generate static assets, and perform custom tasks before compilation.

## Configuring Plugins

Plugins are configured in your `rxconfig.py` file using the `plugins` parameter:

```python
import reflex as rx

config = rx.Config(
    app_name="my_app",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)
```

## Built-in Plugins

Reflex comes with several built-in plugins that provide common functionality.

### SitemapPlugin

The `SitemapPlugin` automatically generates a sitemap.xml file for your application, which helps search engines discover and index your pages.

```python
import reflex as rx

config = rx.Config(
    app_name="my_app",
    plugins=[
        rx.plugins.SitemapPlugin(),
    ],
)
```

The sitemap plugin automatically includes all your app's routes. For dynamic routes or custom configuration, you can add sitemap metadata to individual pages:

```python
@rx.page(
    route="/blog/[slug]", context={"sitemap": {"changefreq": "weekly", "priority": 0.8}}
)
def blog_post():
    return rx.text("Blog post content")


@rx.page(
    route="/about", context={"sitemap": {"changefreq": "monthly", "priority": 0.5}}
)
def about():
    return rx.text("About page")
```

The sitemap configuration supports the following options:

- `loc`: Custom URL for the page (required for dynamic routes)
- `lastmod`: Last modification date (datetime object)
- `changefreq`: How frequently the page changes (`"always"`, `"hourly"`, `"daily"`, `"weekly"`, `"monthly"`, `"yearly"`, `"never"`)
- `priority`: Priority of this URL relative to other URLs (0.0 to 1.0)

### TailwindV4Plugin

The `TailwindV4Plugin` provides support for Tailwind CSS v4, which is the recommended version for new projects and includes performance improvements and new features.

```python
import reflex as rx

# Basic configuration
config = rx.Config(
    app_name="my_app",
    plugins=[
        rx.plugins.TailwindV4Plugin(),
    ],
)
```

You can customize the Tailwind configuration by passing a config dictionary:

```python
import reflex as rx

tailwind_config = {
    "theme": {
        "extend": {
            "colors": {
                "brand": {
                    "50": "#eff6ff",
                    "500": "#3b82f6",
                    "900": "#1e3a8a",
                }
            }
        }
    },
    "plugins": ["@tailwindcss/typography"],
}

config = rx.Config(
    app_name="my_app",
    plugins=[
        rx.plugins.TailwindV4Plugin(tailwind_config),
    ],
)
```

### TailwindV3Plugin

The `TailwindV3Plugin` integrates Tailwind CSS v3 into your Reflex application. While still supported, TailwindV4Plugin is recommended for new projects.

```python
import reflex as rx

# Basic configuration
config = rx.Config(
    app_name="my_app",
    plugins=[
        rx.plugins.TailwindV3Plugin(),
    ],
)
```

You can customize the Tailwind configuration by passing a config dictionary:

```python
import reflex as rx

tailwind_config = {
    "theme": {
        "extend": {
            "colors": {
                "primary": "#3b82f6",
                "secondary": "#64748b",
            }
        }
    },
    "plugins": ["@tailwindcss/typography", "@tailwindcss/forms"],
}

config = rx.Config(
    app_name="my_app",
    plugins=[
        rx.plugins.TailwindV3Plugin(tailwind_config),
    ],
)
```

## Plugin Management

### Default Plugins

Some plugins are enabled by default. Currently, the `SitemapPlugin` is enabled automatically. If you want to disable a default plugin, use the `disable_plugins` parameter:

```python
import reflex as rx

config = rx.Config(
    app_name="my_app",
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
)
```

### Plugin Order

Plugins are executed in the order they appear in the `plugins` list. This can be important if plugins have dependencies on each other or modify the same files.

```python
import reflex as rx

config = rx.Config(
    app_name="my_app",
    plugins=[
        rx.plugins.TailwindV4Plugin(),  # Runs first
        rx.plugins.SitemapPlugin(),  # Runs second
    ],
)
```

## Plugin Architecture

All plugins inherit from the base `Plugin` class and can implement several lifecycle methods:

```python
class Plugin:
    def get_frontend_development_dependencies(self, **context) -> list[str]:
        """Get NPM packages required by the plugin for development."""
        return []

    def get_frontend_dependencies(self, **context) -> list[str]:
        """Get NPM packages required by the plugin."""
        return []

    def get_static_assets(self, **context) -> Sequence[tuple[Path, str | bytes]]:
        """Get static assets required by the plugin."""
        return []

    def get_stylesheet_paths(self, **context) -> Sequence[str]:
        """Get paths to stylesheets required by the plugin."""
        return []

    def register_route(self, **context) -> None:
        """Contribute pages before the app's first compilation."""
        pass

    def pre_compile(self, **context) -> None:
        """Called before compilation to perform custom tasks."""
        pass
```

### Creating Custom Plugins

You can create custom plugins by inheriting from the base `Plugin` class:

```python
from reflex.plugins.base import Plugin
from pathlib import Path


class CustomPlugin(Plugin):
    def get_frontend_dependencies(self, **context):
        return ["my-custom-package@1.0.0"]

    def pre_compile(self, **context):
        # Custom logic before compilation
        print("Running custom plugin logic...")

        # Add a custom task
        context["add_save_task"](self.create_custom_file)

    def create_custom_file(self):
        return "public/custom.txt", "Custom content"
```

Then use it in your configuration:

```python
import reflex as rx
from my_plugins import CustomPlugin

config = rx.Config(
    app_name="my_app",
    plugins=[
        CustomPlugin(),
    ],
)
```

### Contributing Pages

A plugin can contribute pages by overriding `register_route`. The hook runs
once for each `App`, after app-defined pages have been collected and before any
page is evaluated. A fresh app created by development reload or a new process
runs the hooks again.

Use the provided `add_page` capability rather than calling `app.add_page`
directly. The framework collects every plugin's calls first and commits them
only after all route hooks succeed, so a failing hook cannot leave partial pages
or dynamic route arguments on the app:

```python
class DashboardPlugin(Plugin):
    def __init__(self, route="/dashboard"):
        self.route = route

    def register_route(self, *, add_page, has_app_page, **context):
        # Let an app-defined page override this optional default.
        if not has_app_page(self.route):
            add_page(dashboard_page, route=self.route, title="Dashboard")
```

`add_page` accepts the same page options as `App.add_page` (`title`,
`on_load`, `meta`, ...) but takes them as keyword arguments only; its signature
is described by the `AddPageProtocol` in the hook context. It uses the app's
normal page-preparation path while collecting the descriptor, then the
framework commits the prepared descriptors together.
Adding a route already defined by the app or by another plugin raises a
`RouteValueError` identifying the owner.
`has_app_page(route)` checks only app-defined pages; it intentionally ignores
pages staged by earlier plugins so plugin conflicts do not silently depend on
configuration order.

The hook also receives `app_type`, which supports concrete-app compatibility
checks without exposing the mutable `App` instance.

An `App` subclass that adds page-registration keyword arguments must normalize
them in its protected `_prepare_page` override and return the base prepared-page
descriptor. That method must not mutate app route state: plugin hooks call it
during collection, while the framework owns the final batch commit. The public
`add_page` and protected `_commit_page` overrides remain the direct-registration
API but are intentionally not dispatched during a staged plugin batch, so an
override cannot make the batch commit partially.

### Looking Up Configured Plugins

Use `rx.plugins.get_plugin(PluginType)` when runtime behavior needs the plugin
instance declared in `rxconfig.py`. It returns the single configured instance
matching that type (including subclasses), returns `None` when none matches,
and raises `ConfigError` when the lookup is ambiguous. Runtime-readable values
should be derived from the plugin's constructor arguments so every process can
recreate the same behavior from `rxconfig.plugins` without a separate binding
step.
