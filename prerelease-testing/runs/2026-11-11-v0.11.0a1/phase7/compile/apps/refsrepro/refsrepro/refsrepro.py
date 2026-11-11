"""Minimal repro: page code that reaches `refs` (the registry of component id refs) from $/utils/state.

Phase 7 extension: /memo (component @rx.memo with add_hooks, plus a standalone Var-returning
function @rx.memo reading refs[...]) and /decl (custom code declaring its own `refs`).
"""

import os

import reflex as rx

_EXPECT = os.environ.get("EXPECT_VENV")
assert _EXPECT is None or _EXPECT in rx.__file__, rx.__file__
print("RXFILE", rx.__file__)

NEW = hasattr(rx, "client_state")


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


class RefsDecl(rx.Fragment):
    """Custom code that binds its own module-level `refs` (must not collide)."""

    def add_custom_code(self):
        return ["const refs = {mine: true};"]

    def add_hooks(self):
        return ["const __mine = refs.mine;"]


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


@rx.memo
def hook_memo(label: rx.Var[str]) -> rx.Component:
    return rx.fragment(rx.text(label, id="memolabel"), RefHook.create())


if NEW:

    @rx.memo
    def ref_kind() -> rx.Var[str]:
        return rx.Var("String(typeof refs['ref_target'])").to(str)


def memo_page():
    return rx.vstack(
        rx.heading("memo page", id="h3"),
        rx.input(id="target"),
        hook_memo(label="memo"),
        rx.text("fnmemo: ", ref_kind() if NEW else "n/a", id="fnmemo"),
    )


def decl():
    return rx.vstack(rx.heading("decl page", id="h4"), rx.input(id="target"), RefsDecl.create(), rx.text("decl ok", id="declok"))


app = rx.App()
app.add_page(index)
app.add_page(hook, route="/hook")
if os.environ.get("REFS_MEMO", "1") == "1":
    app.add_page(memo_page, route="/memo")
if os.environ.get("REFS_DECL", "1") == "1":
    app.add_page(decl, route="/decl")
