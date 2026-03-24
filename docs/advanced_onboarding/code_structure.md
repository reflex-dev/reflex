```python exec
from pcweb.pages.docs import custom_components
```

# Project Structure (Advanced)

## App Module

Reflex imports the main app module based on the `app_name` from the config, which **must define a module-level global named `app` as an instance of `rx.App`**.

The main app module is responsible for importing all other modules that make up the app and defining `app = rx.App()`.

**All other modules containing pages, state, and models MUST be imported by the main app module or package** for Reflex to include them in the compiled output.

# Breaking the App into Smaller Pieces

As applications scale, effective organization is crucial. This is achieved by breaking the application down into smaller, manageable modules and organizing them into logical packages that avoid circular dependencies.

In the following documentation there will be an app with an `app_name` of `example_big_app`. The main module would be `example_big_app/example_big_app.py`.

In the [Putting it all together](#putting-it-all-together) section there is a visual of the project folder structure to help follow along with the examples below.

### Pages Package: `example_big_app/pages`

All complex apps will have multiple pages, so it is recommended to create `example_big_app/pages` as a package.

1. This package should contain one module per page in the app.
2. If a particular page depends on the state, the substate should be defined in the same module as the page.
3. The page-returning function should be decorated with `rx.page()` to have it added as a route in the app.

```python
import reflex as rx

from ..state import AuthState


class LoginState(AuthState):
    @rx.event
    def handle_submit(self, form_data):
        self.logged_in = authenticate(form_data["username"], form_data["password"])


def login_field(name: str, **input_props):
    return rx.hstack(
        rx.text(name.capitalize()),
        rx.input(name=name, **input_props),
        width="100%",
        justify="between",
    )


@rx.page(route="/login")
def login():
    return rx.card(
        rx.form(
            rx.vstack(
                login_field("username"),
                login_field("password", type="password"),
                rx.button("Login"),
                width="100%",
                justify="center",
            ),
            on_submit=LoginState.handle_submit,
        ),
    )
```

### Templating: `example_big_app/template.py`

Most applications maintain a consistent layout and structure across pages. Defining this common structure in a separate module facilitates easy sharing and reuse when constructing individual pages.

**Best Practices**

1. Factor out common frontend UI elements into a function that returns a component.
2. If a function accepts a function that returns a component, it can be used as a decorator as seen below.

```python
from typing import Callable

import reflex as rx

from .components.menu import menu
from .components.navbar import navbar


def template(page: Callable[[], rx.Component]) -> rx.Component:
    return rx.vstack(
        navbar(),
        rx.hstack(
            menu(),
            rx.container(page()),
        ),
        width="100%",
    )
```

The `@template` decorator should appear below the `@rx.page` decorator and above the page-returning function. See the [Posts Page](#a-post-page-example_big_apppagespostspy) code for an example.

## State Management

Most pages will use State in some capacity. You should avoid adding vars to a
shared state that will only be used in a single page. Instead, define a new
subclass of `rx.State` and keep it in the same module as the page.

### Accessing other States

As of Reflex 0.4.3, any event handler can get access to an instance of any other
substate via the `get_state` API. From a practical perspective, this means that
state can be split up into smaller pieces without requiring a complex
inheritance hierarchy to share access to other states.

In previous releases, if an app wanted to store settings in `SettingsState` with
a page or component for modifying them, any other state with an event handler
that needed to access those settings would have to inherit from `SettingsState`,
even if the other state was mostly orthogonal. The other state would also now
always have to load the settings, even for event handlers that didn't need to
access them.

A better strategy is to load the desired state on demand from only the event
handler which needs access to the substate.

### A Settings Component: `example_big_app/components/settings.py`

```python
import reflex as rx


class SettingsState(rx.State):
    refresh_interval: int = 15
    auto_update: bool = True
    prefer_plain_text: bool = True
    posts_per_page: int = 20


def settings_dialog():
    return rx.dialog(...)
```

### A Post Page: `example_big_app/pages/posts.py`

This page loads the `SettingsState` to determine how many posts to display per page
and how often to refresh.

```python
import reflex as rx

from ..models import Post
from ..template import template
from ..components.settings import SettingsState


class PostsState(rx.State):
    refresh_tick: int
    page: int
    posts: list[Post]

    @rx.event
    async def on_load(self):
        settings = await self.get_state(SettingsState)
        if settings.auto_update:
            self.refresh_tick = settings.refresh_interval * 1000
        else:
            self.refresh_tick = 0

    @rx.event
    async def tick(self, _):
        settings = await self.get_state(SettingsState)
        with rx.session() as session:
            q = Post.select().offset(self.page * settings.posts_per_page).limit(settings.posts_per_page)
            self.posts = q.all()

    @rx.event
    def go_to_previous(self):
        if self.page > 0:
            self.page = self.page - 1

    @rx.event
    def go_to_next(self):
        if self.posts:
            self.page = self.page + 1


@rx.page(route="/posts", on_load=PostsState.on_load)
@template
def posts():
    return rx.vstack(
        rx.foreach(PostsState.posts, post_view),
        rx.hstack(
            rx.button("< Prev", on_click=PostsState.go_to_previous),
            rx.button("Next >", on_click=PostsState.go_to_next),
            justify="between",
        ),
        rx.moment(interval=PostsState.refresh_tick, on_change=PostsState.tick, display="none"),
        width="100%",
    )
```

### Common State: `example_big_app/state.py`

_Common_ states and substates that are shared by multiple pages or components
should be implemented in a separate module to avoid circular imports. This
module should not import other modules in the app.

## Component Reusability

The primary mechanism for reusing components in Reflex is to define a function that returns
the component, then simply call it where that functionality is needed.

Component functions typically should not take any State classes as arguments, but prefer
to import the needed state and access the vars on the class directly.

### Memoize Functions for Improved Performance

In a large app, if a component has many subcomponents or is used in a large number of places, it can improve compile and runtime performance to memoize the function with the `@lru_cache` decorator.

To memoize the `foo` component to avoid re-creating it many times simply add `@lru_cache` to the function definition, and the component will only be created once per unique set of arguments.

```python
from functools import lru_cache

import reflex as rx

class State(rx.State):
    v: str = "foo"


@lru_cache
def foo():
    return rx.text(State.v)


def index():
    return rx.flex(
        rx.button("Change", on_click=State.set_v(rx.cond(State.v != "bar", "bar", "foo"))),
        *[
            foo()
            for _ in range(100)
        ],
        direction="row",
        wrap="wrap",
    )
```

### example_big_app/components

This package contains reusable parts of the app, for example headers, footers,
and menus. If a particular component requires state, the substate may be defined
in the same module for locality. Any substate defined in a component module
should only contain fields and event handlers pertaining to that individual
component.

### External Components

Reflex 0.4.3 introduced support for the [`reflex component` CLI commands]({custom_components.overview.path}), which makes it easy
to bundle up common functionality to publish on PyPI as a standalone Python package
that can be installed and used in any Reflex app.

When wrapping npm components or other self-contained bits of functionality, it can be helpful
to move this complexity outside the app itself for easier maintenance and reuse in other apps.

## Database Models: `example_big_app/models.py`

It is recommended to implement all database models in a single file to make it easier to define relationships and understand the entire schema.

However, if the schema is very large, it might make sense to have a `models` package with individual models defined in their own modules.

At any rate, defining the models separately allows any page or component to import and use them without circular imports.

## Top-level Package: `example_big_app/__init__.py`

This is a great place to import all state, models, and pages that should be part of the app.
Typically, components and helpers do not need to imported, because they will be imported by
pages that use them (or they would be unused).

```python
from . import state, models
from .pages import index, login, post, product, profile, schedule

__all__ = [
    "state",
    "models",
    "index",
    "login",
    "post",
    "product",
    "profile",
    "schedule",
]
```

If any pages are not imported here, they will not be compiled as part of the app.

## example_big_app/example_big_app.py

This is the main app module. Since everything else is defined in other modules, this file becomes very simple.

```python
import reflex as rx

app = rx.App()
```

## File Management

There are two categories of non-code assets (media, fonts, stylesheets,
documents) typically used in a Reflex app.

### assets

The `assets` directory is used for **static** files that should be accessible
relative to the root of the frontend (default port 3000). When an app is deployed in
production mode, changes to the assets directory will NOT be available at runtime!

When referencing an asset, always use a leading forward slash, so the
asset can be resolved regardless of the page route where it may appear.

### uploaded_files

If an app needs to make files available dynamically at runtime, it is
recommended to set the target directory via `REFLEX_UPLOADED_FILES_DIR`
environment variable (default `./uploaded_files`), write files relative to the
path returned by `rx.get_upload_dir()`, and create working links via
`rx.get_upload_url(relative_path)`.

Uploaded files are served from the backend (default port 8000) via
`/_upload/<relative_path>`

## Putting it all together

Based on the previous discussion, the recommended project layout look like this.

```text
example-big-app/
├─ assets/
├─ example_big_app/
│  ├─ components/
│  │  ├─ __init__.py
│  │  ├─ auth.py
│  │  ├─ footer.py
│  │  ├─ menu.py
│  │  ├─ navbar.py
│  ├─ pages/
│  │  ├─ __init__.py
│  │  ├─ index.py
│  │  ├─ login.py
│  │  ├─ posts.py
│  │  ├─ product.py
│  │  ├─ profile.py
│  │  ├─ schedule.py
│  ├─ __init__.py
│  ├─ example_big_app.py
│  ├─ models.py
│  ├─ state.py
│  ├─ template.py
├─ uploaded_files/
├─ requirements.txt
├─ rxconfig.py
```

## Key Takeaways

- Like any other Python project, **split up the app into modules and packages** to keep the codebase organized and manageable.
- Using smaller modules and packages makes it easier to **reuse components and state** across the app
  without introducing circular dependencies.
- Create **individual functions** to encapsulate units of functionality and **reuse them** where needed.
