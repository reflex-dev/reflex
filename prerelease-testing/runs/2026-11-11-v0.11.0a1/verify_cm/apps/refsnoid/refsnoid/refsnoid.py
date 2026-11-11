"""Variant of refsrepro: the probe buttons carry NO id, and the /hook page's only id'd
component sits inside a stateful rx.cond (so it is memoized into its own module).
Shows whether 0.10.1's `refs` import was guaranteed or coincidental."""

import reflex as rx


class S(rx.State):
    log: str = ""
    show: bool = True

    @rx.event
    def set_log(self, v: str):
        self.log = str(v)


class RefHook(rx.Fragment):
    def add_imports(self):
        return {"react": ["useEffect"]}

    def add_hooks(self):
        return ["useEffect(() => { setTimeout(() => { refs['ref_target'].current.value = 'set by hook'; }, 300) }, [])"]


def index():
    return rx.vstack(
        rx.heading("refs noid"),
        rx.input(id="target"),
        rx.button(
            "raw var handler",
            on_click=rx.Var("() => { refs['ref_target'].current.value = 'set by raw var'; }").to(rx.vars.FunctionVar),
        ),
        rx.button(
            "call_function",
            on_click=rx.call_function(rx.Var("() => refs['ref_target'].current.value"), callback=S.set_log),
        ),
        rx.text("log: ", S.log, class_name="log"),
    )


def hook():
    return rx.vstack(rx.heading("hook page"), rx.cond(S.show, rx.input(id="target")), RefHook.create())


app = rx.App()
app.add_page(index)
app.add_page(hook, route="/hook")
