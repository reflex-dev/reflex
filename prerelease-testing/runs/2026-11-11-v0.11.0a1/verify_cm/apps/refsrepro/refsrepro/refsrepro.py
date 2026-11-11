"""Minimal repro: page code that reaches `refs` (the registry of component id refs) from $/utils/state."""

import reflex as rx


class S(rx.State):
    log: str = ""

    @rx.event
    def set_log(self, v: str):
        self.log = str(v)


class RefHook(rx.Fragment):
    """A custom component (wrapping-React style) whose hook reads a registered id ref."""

    def add_imports(self):
        return {"react": ["useEffect"]}

    def add_hooks(self):
        return ["useEffect(() => { refs['ref_target'].current.value = 'set by hook'; }, [])"]


def index():
    return rx.vstack(
        rx.heading("refs repro", id="h"),
        rx.input(id="target"),
        # 1. raw JS function Var as an event handler
        rx.button(
            "raw var handler",
            id="raw",
            on_click=rx.Var("() => { refs['ref_target'].current.value = 'set by raw var'; }").to(rx.vars.FunctionVar),
        ),
        # 2. rx.call_function with a JS function Var
        rx.button(
            "call_function",
            id="callfn",
            on_click=rx.call_function(rx.Var("() => refs['ref_target'].current.value"), callback=S.set_log),
        ),
        rx.text("log: ", S.log, id="log"),
    )


def hook():
    return rx.vstack(rx.heading("hook page", id="h2"), rx.input(id="target"), RefHook.create())


app = rx.App()
app.add_page(index)
app.add_page(hook, route="/hook")
