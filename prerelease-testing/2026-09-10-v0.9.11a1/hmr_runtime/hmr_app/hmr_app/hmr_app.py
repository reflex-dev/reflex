"""HMR runtime stability test app for reflex 0.9.11a1 (cluster hmr_runtime).

Editable markers (the Playwright driver rewrites these lines while the server runs):
  EDIT_DEFAULT  -> State.label default
  EDIT_TEXT     -> rendered heading text
  EDIT_NEWVAR   -> a new state var is inserted below this line
  EDIT_HANDLER  -> a new event handler is inserted below this line
  EDIT_PROPS    -> component props changed
"""

import asyncio

import reflex as rx

LONG_PARAGRAPH = (
    "Paragraph {i}: café naïve résumé über straße "
    "日本語テスト 中文测试 한국어 "
    "\U0001F389\U0001F680\U0001F60E\U0001F1EF\U0001F1F5 "
    "The quick brown fox jumps over the lazy dog. "
)


class State(rx.State):
    """Main app state."""

    count: int = 0
    label: str = "Counter"  # EDIT_DEFAULT
    todos: list[str] = ["first todo"]
    new_todo: str = ""
    bg_ticks: int = 0
    bg_running: bool = False
    # EDIT_NEWVAR

    @rx.event
    def increment(self):
        self.count += 1

    @rx.event
    def decrement(self):
        self.count -= 1

    @rx.event
    def set_new_todo(self, value: str):
        self.new_todo = value

    @rx.event
    def add_todo(self):
        if self.new_todo:
            self.todos.append(self.new_todo)
            self.new_todo = ""
        return rx.set_focus("todo_input")

    @rx.event
    def remove_todo(self, item: str):
        self.todos = [t for t in self.todos if t != item]

    @rx.event
    def focus_input(self):
        return rx.set_focus("todo_input")

    # EDIT_HANDLER

    @rx.event(background=True)
    async def start_bg(self):
        async with self:
            if self.bg_running:
                return
            self.bg_running = True
            self.bg_ticks = 0
        for _ in range(60):
            await asyncio.sleep(0.25)
            async with self:
                if not self.bg_running:
                    break
                self.bg_ticks += 1
        async with self:
            self.bg_running = False

    @rx.event
    def stop_bg(self):
        self.bg_running = False


class Toggle(rx.ComponentState):
    """A ComponentState toggle."""

    on: bool = False

    @rx.event
    def flip(self):
        self.on = not self.on

    @classmethod
    def get_component(cls, **props) -> rx.Component:
        return rx.button(
            rx.cond(cls.on, "Toggle: ON", "Toggle: OFF"),
            on_click=cls.flip,
            id="toggle-btn",
            **props,
        )


toggle = Toggle.create()

client_val = rx._x.client_state(var_name="cs_val", default="cs-initial")


@rx.memo
def counter_display(count: rx.Var[int], label: rx.Var[str]) -> rx.Component:
    return rx.text(label, ": ", count, id="memo-count", size="6")  # EDIT_PROPS


def nav() -> rx.Component:
    return rx.hstack(
        rx.link("Home", href="/", id="nav-home"),
        rx.link("About", href="/about", id="nav-about"),
        rx.link("Long", href="/long", id="nav-long"),
        rx.link("Page2", href="/page2", id="nav-page2"),
        rx.link("Page3", href="/page3", id="nav-page3"),
        spacing="4",
    )


def index() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.el.input(id="scratch", placeholder="uncontrolled scratch (remount detector)"),
        rx.heading("HMR Runtime App", id="heading"),  # EDIT_TEXT
        counter_display(count=State.count, label=State.label),
        rx.hstack(
            rx.button("-", on_click=State.decrement, id="dec-btn"),
            rx.button("+", on_click=State.increment, id="inc-btn"),
        ),
        rx.cond(
            State.count > 5,
            rx.text("count is big", id="cond-big"),
            rx.text("count is small", id="cond-small"),
        ),
        toggle,
        client_val,
        rx.text("client: ", client_val.value, id="cs-text"),
        rx.button("set client", on_click=client_val.set_value("cs-changed"), id="cs-btn"),
        rx.hstack(
            rx.input(
                id="todo_input",
                placeholder="new todo",
                value=State.new_todo,
                on_change=State.set_new_todo,
            ),
            rx.button("add", on_click=State.add_todo, id="add-btn"),
            rx.button("focus", on_click=State.focus_input, id="focus-btn"),
        ),
        rx.vstack(
            rx.foreach(
                State.todos,
                lambda t: rx.hstack(
                    rx.text(t, class_name="todo-item"),
                    rx.button("x", on_click=State.remove_todo(t), size="1"),
                ),
            ),
            id="todo-list",
        ),
        rx.hstack(
            rx.button("start bg", on_click=State.start_bg, id="bg-start"),
            rx.button("stop bg", on_click=State.stop_bg, id="bg-stop"),
            rx.text("ticks: ", State.bg_ticks, id="bg-ticks"),
            rx.text(rx.cond(State.bg_running, "running", "idle"), id="bg-status"),
        ),
        spacing="3",
        padding="2em",
    )


def about() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("About — café über naïve", id="about-heading"),
        rx.text("Emoji: \U0001F389 \U0001F680 \U0001F60E \U0001F1EF\U0001F1F5 \U0001F468‍\U0001F469‍\U0001F467", id="emoji-text"),
        rx.text("CJK: 日本語のテスト 中文测试文本 한국어 테스트", id="cjk-text"),
        rx.text("Accents: éèêë àâ ñ ø å ß ıİ șț", id="accent-text"),
        rx.text("Count from state: ", State.count, id="about-count"),
        padding="2em",
    )


def long_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("Long page", id="long-heading"),
        *[rx.text(LONG_PARAGRAPH.format(i=i), class_name="long-para") for i in range(700)],
        rx.text("END OF LONG PAGE \U0001F3C1", id="long-end"),
        padding="2em",
    )


def page2() -> rx.Component:
    return rx.vstack(nav(), rx.heading("Page 2", id="page2-heading"), rx.text("count: ", State.count, id="page2-count"), padding="2em")


def page3() -> rx.Component:
    return rx.vstack(nav(), rx.heading("Page 3", id="page3-heading"), rx.text("count: ", State.count, id="page3-count"), padding="2em")


LONG_META = "".join(LONG_PARAGRAPH.format(i=i) for i in range(560))  # ~70KB, forces several response chunks
# rx.App head_components land in the root layout <head>, which IS server-rendered in dev (routes are not).
app = rx.App(
    head_components=[
        rx.el.title("HMR — café 日本語 \U0001F389"),
        rx.el.meta(name="description", content=LONG_META),
    ]
)
app.add_page(index, route="/")
# Server-rendered head content with multibyte text: the dev server renders page bodies client-side
# (HydrateFallback), so this is what actually flows through the Safari cache-bust rewriter.
app.add_page(about, route="/about", title="About — café 日本語 \U0001F389", description="Ünïcödé 中文 \U0001F680 description")
app.add_page(long_page, route="/long", title="Long — naïve 한국어 \U0001F3C1", meta=[{"name": "description", "content": LONG_META}])
app.add_page(page2, route="/page2")
app.add_page(page3, route="/page3")
