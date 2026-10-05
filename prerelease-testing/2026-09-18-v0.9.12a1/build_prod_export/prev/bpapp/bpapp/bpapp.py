"""build_prod_export cluster test app (reflex 0.9.12a1 pre-release QA).

Exercises: frontend_path route matching (#7153), prerender/asset collisions +
compression + preload + sitemap (#7078), frontend_lazy_bundled_libraries (#7078),
json5 removal / non-finite float upload parsing (#7165), stateful-page markers
(#7142), module-import probe (#7112).
"""

import sys
from pathlib import Path

import reflex as rx

assert "/envs/prev/" in rx.__file__, rx.__file__

PROBE_MODULES = ("httpx", "json5", "sqlalchemy", "pandas", "h11", "granian")

ICONS = ["rocket", "circle-check", "triangle-alert", "bug", "sparkles"]

MD = """
## Markdown heading

Some *markdown* with a [link](/app/about) and inline `code`.

```python
def in_markdown():
    return "code block inside markdown"
```
"""

CODE = '''def shiki_highlighted(x: int) -> str:
    """Docstring so shiki has something to color."""
    return f"value={x}"
'''


class S(rx.State):
    """Main app state."""

    counter: int = 0
    icon_index: int = 0
    upload_inf: float = 0.0
    upload_ninf: float = 0.0
    upload_nan: float = 0.0
    upload_normal: float = 0.0
    upload_done: bool = False
    modules: list[str] = []
    bg_ticks: int = 0

    @rx.var
    def icon_name(self) -> str:
        """Current dynamic icon tag.

        Returns:
            The icon tag name.
        """
        return ICONS[self.icon_index % len(ICONS)]

    @rx.var
    def upload_summary(self) -> str:
        """Human readable summary of the uploaded float values.

        Returns:
            Summary string.
        """
        if not self.upload_done:
            return "no upload yet"
        return (
            f"inf={self.upload_inf} ninf={self.upload_ninf} "
            f"nan={self.upload_nan} normal={self.upload_normal}"
        )

    @rx.event
    def inc(self):
        """Increment the counter."""
        self.counter += 1

    @rx.event
    def next_icon(self):
        """Advance the dynamic icon."""
        self.icon_index += 1

    @rx.event
    def probe_modules(self):
        """Record which heavyweight modules are loaded in this worker."""
        self.modules = sorted(m for m in PROBE_MODULES if m in sys.modules)

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        """Set non-finite floats from an upload (json5 removal check, #7165).

        Args:
            files: uploaded files.
        """
        for f in files:
            data = await f.read()
            self.upload_normal = float(len(data))
        self.upload_inf = float("inf")
        self.upload_ninf = float("-inf")
        self.upload_nan = float("nan")
        self.upload_done = True

    @rx.event(background=True)
    async def bg_tick(self):
        """Background task that bumps a counter three times."""
        for _ in range(3):
            async with self:
                self.bg_ticks += 1


CS = rx._x.client_state("cs_value", default="cs-initial")


class CompState(rx.ComponentState):
    """ComponentState wrapping a dynamic icon + code block."""

    idx: int = 0

    @rx.event
    def bump(self):
        """Advance the component-local icon index."""
        self.idx += 1

    @classmethod
    def get_component(cls, **props):
        """Build the component.

        Args:
            props: extra props.

        Returns:
            The component.
        """
        return rx.vstack(
            rx.text("ComponentState idx: ", rx.text.strong(cls.idx), id="cs-idx"),
            rx.icon(tag=rx.Var.create(ICONS)[cls.idx % len(ICONS)], size=28),
            rx.button("bump cs", on_click=cls.bump, id="cs-bump"),
            **props,
        )


@rx.memo
def memo_card(label: str, icon_tag: str) -> rx.Component:
    """Memoized card containing a dynamic icon.

    Args:
        label: card label.
        icon_tag: icon tag.

    Returns:
        The card component.
    """
    return rx.hstack(
        rx.icon(tag=icon_tag, size=20),
        rx.text(label),
        rx.code_block("memo = True", language="python"),
        border="1px solid gray",
        padding="4px",
    )


def nav() -> rx.Component:
    """Navigation links for every route.

    Returns:
        A hstack of links.
    """
    return rx.hstack(
        *[
            rx.link(name, href=href, id=f"nav-{name}")
            for name, href in [
                ("index", "/"),
                ("apple", "/apple"),
                ("app", "/app"),
                ("about", "/about"),
                ("components", "/components"),
                ("assets", "/assets"),
                ("item7", "/items/7"),
            ]
        ],
        wrap="wrap",
    )


def shell(title: str, *children) -> rx.Component:
    """Common page shell.

    Args:
        title: page heading.
        children: page body.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading(title, id="page-title"),
        rx.text(f"PAGEMARK:{title}", id="pagemark"),
        nav(),
        *children,
        padding="1em",
    )


@rx.page(route="/", title="Index Page")
def index() -> rx.Component:
    """Index page.

    Returns:
        The page.
    """
    return shell(
        "index",
        rx.text("counter: ", rx.text.strong(S.counter), id="counter"),
        rx.button("inc", on_click=S.inc, id="inc"),
        rx.button("bg", on_click=S.bg_tick, id="bg"),
        rx.text("bg_ticks: ", S.bg_ticks, id="bgticks"),
        rx.input(
            id="cs-input",
            value=CS.value,
            on_change=CS.set,
        ),
        rx.text(CS.value, id="cs-out"),
        rx.button("probe", on_click=S.probe_modules, id="probe"),
        rx.text("modules: ", rx.foreach(S.modules, lambda m: rx.badge(m)), id="modules"),
        rx.text("modules_len: ", S.modules.length(), id="modules-len"),
    )


@rx.page(route="/apple", title="Apple Page")
def apple() -> rx.Component:
    """Route whose name is a prefix-collision with frontend_path /app (#7153).

    Returns:
        The page.
    """
    return shell(
        "apple",
        rx.text("This route starts with the frontend_path text.", id="apple-note"),
        rx.text("counter: ", S.counter, id="counter"),
        rx.button("inc", on_click=S.inc, id="inc"),
    )


@rx.page(route="/app", title="App Page")
def app_page() -> rx.Component:
    """Route literally named `app`, i.e. /app/app under frontend_path.

    Returns:
        The page.
    """
    return shell("app", rx.text("route named app", id="app-note"))


@rx.page(route="/about", title="About Page")
def about() -> rx.Component:
    """Static about page.

    Returns:
        The page.
    """
    return shell(
        "about",
        rx.markdown(MD),
        rx.code_block(CODE, language="python", show_line_numbers=True),
    )


@rx.page(route="/components", title="Components Page")
def components_page() -> rx.Component:
    """Route colliding with the assets/components/ directory (#7078).

    Returns:
        The page.
    """
    return shell(
        "components",
        rx.image(src="/components/logo.svg", id="logo", width="40px"),
        memo_card(label="memo-a", icon_tag="rocket"),
        memo_card(label="memo-b", icon_tag=S.icon_name),
        CompState.create(id="compstate"),
        rx.hstack(
            rx.icon(tag=S.icon_name, size=32, id="dyn-icon"),
            rx.button("next icon", on_click=S.next_icon, id="next-icon"),
            rx.text(S.icon_name, id="icon-name"),
        ),
        rx.cond(
            S.counter > 0,
            rx.icon(tag="check", size=20),
            rx.icon(tag="x", size=20),
        ),
    )


@rx.page(route="/assets", title="Assets Page")
def assets_page() -> rx.Component:
    """Route named `assets` plus the upload / non-finite float probe (#7165).

    Returns:
        The page.
    """
    return shell(
        "assets",
        rx.upload(
            rx.text("drop or select"),
            id="up",
            border="1px dashed gray",
            padding="1em",
        ),
        rx.button(
            "do upload",
            on_click=S.handle_upload(rx.upload_files(upload_id="up")),
            id="do-upload",
        ),
        rx.text(S.upload_summary, id="upload-summary"),
        rx.text("inf=", S.upload_inf, id="v-inf"),
        rx.text("ninf=", S.upload_ninf, id="v-ninf"),
        rx.text("nan=", S.upload_nan, id="v-nan"),
        rx.text("normal=", S.upload_normal, id="v-normal"),
        rx.link("note.txt", href="/apple/note.txt", id="note-link"),
    )


@rx.page(route="/items/[id]", title="Item Page")
def item_page() -> rx.Component:
    """Dynamic route page.

    Returns:
        The page.
    """
    return shell(
        "item",
        rx.text("item id: ", rx.State.id, id="item-id"),
        rx.text("path: ", rx.State.router.url.path, id="router-path"),
        rx.text("url: ", rx.State.router.url.to_string(), id="router-url"),
    )


class DynState(rx.State):
    """State whose var value is a Component referencing a bundled library (#7096)."""

    tag: str = "rocket"
    plain: str = "hello"

    @rx.event
    def flip(self):
        """Toggle the icon tag."""
        self.tag = "bug" if self.tag == "rocket" else "rocket"


@rx.dynamic
def widget(state: DynState) -> rx.Component:
    """Component-valued var serialized into the hydrate delta (#7096).

    Args:
        state: the dyn state.

    Returns:
        The rendered widget.
    """
    return rx.hstack(
        rx.icon(tag=state.tag, size=24),
        rx.text("dyn:" + state.tag),
    )


@rx.page(route="/dyn", title="Dyn Page")
def dyn_page() -> rx.Component:
    """Page rendering a component-valued state var (#7096 backend-only shape).

    Returns:
        The page.
    """
    return shell(
        "dyn",
        rx.box(widget(), id="dyn-widget"),
        rx.text("tag: ", DynState.tag, id="dyn-tag"),
        rx.text("plain: ", DynState.plain, id="dyn-plain"),
        rx.button("flip", on_click=DynState.flip, id="dyn-flip"),
    )


app = rx.App()

