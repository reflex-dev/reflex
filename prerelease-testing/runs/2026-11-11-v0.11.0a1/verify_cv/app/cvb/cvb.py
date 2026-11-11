"""Verifier app for client_vars item B (identifier collisions) and C (None set ops)."""
import os

import reflex as rx

_venv = os.environ["EXPECT_VENV"]
assert f"/envs/{_venv}/" in rx.__file__, rx.__file__
NEW = hasattr(rx, "client_state")
CASE = os.environ.get("CV_CASE", "casing")


def cs(default, name):
    """Create a named (global) client state var on either version.

    Args:
        default: default value
        name: the var name

    Returns:
        the var
    """
    if NEW:
        return rx.client_state(default, name=name)
    return rx._x.client_state(name, default)


def setter(v, value):
    return v.set(value) if NEW else v.set_value(value)


class S(rx.State):
    maybe_set: set[str] | None = None
    maybe_list: list[str] | None = None
    n: int = 0

    @rx.event
    def inc(self):
        self.n += 1

    @rx.event
    def fill(self):
        self.maybe_set = {"m"}
        self.maybe_list = ["m"]


def index():
    return rx.vstack(rx.text("HOME-OK", id="home"), rx.link("casing", href="/casing"), rx.button("inc", on_click=S.inc, id="inc"), rx.text(S.n))


app = rx.App()
app.add_page(index, route="/")
app.add_page(lambda: rx.text("STATIC-OK"), route="/static")

if CASE == "casing":
    lower = cs("lower", "item")
    upper = cs("upper", "Item")

    def casing():
        return rx.vstack(
            rx.text(lower.value, id="lower"),
            rx.text(upper.value, id="upper"),
            rx.button("both", on_click=[setter(lower, "L"), setter(upper, "U")], id="both"),
        )

    app.add_page(casing, route="/casing")
elif CASE == "camel":
    # realistic: camelCase vs snake/lower names that 0.10.1 capitalize() folded together
    a = cs("a", "searchQuery")
    b = cs("b", "searchquery")

    def camel():
        return rx.vstack(rx.text(a.value, id="a"), rx.text(b.value, id="b"),
                         rx.button("both", on_click=[setter(a, "A"), setter(b, "B")], id="both"))

    app.add_page(camel, route="/casing")
elif CASE == "dup":
    open1 = cs(False, "open")
    open2 = cs(True, "open")

    def dup1():
        return rx.vstack(rx.text(open1.value.to_string(), id="d1"), rx.button("t", on_click=setter(open1, True)))

    def dup2():
        return rx.vstack(rx.text(open2.value.to_string(), id="d2"), rx.button("t", on_click=setter(open2, False)))

    app.add_page(dup1, route="/dup1")
    app.add_page(dup2, route="/dup2")
elif CASE == "dupone":
    # both declarations used on ONE page
    open1 = cs(False, "open")
    open2 = cs(True, "open")

    def dupone():
        return rx.vstack(rx.text(open1.value.to_string(), id="d1"), rx.text(open2.value.to_string(), id="d2"))

    app.add_page(dupone, route="/dup1")
elif CASE == "setnone":
    def setnone():
        if NEW:
            ops = [S.maybe_set.contains("m").to_string(), S.maybe_set.union({"z"}).length().to_string()]
        else:
            ops = [S.maybe_set.contains("m").to_string(), S.maybe_list.contains("m").to_string()]
        return rx.vstack(rx.text("SETNONE", id="hdr"), *[rx.text(o) for o in ops], rx.button("fill", on_click=S.fill))

    app.add_page(setnone, route="/setnone")
elif CASE == "listnone":
    def listnone():
        return rx.vstack(rx.text("LISTNONE", id="hdr"), rx.text(S.maybe_list.contains("m").to_string()), rx.text(S.maybe_list.length().to_string()), rx.button("fill", on_click=S.fill))

    app.add_page(listnone, route="/setnone")

if CASE == "factory":
    import sys as _sys, time as _time, traceback as _tb

    def _tok() -> str:
        """Record each call of the factory.

        Returns:
            a token
        """
        stack = [f"{f.name}" for f in _tb.extract_stack()[-8:-1]]
        with open(os.environ["CV_FACTORY_LOG"], "a") as fh:
            fh.write(f"{os.getpid()} {_time.time():.1f} {_sys.argv[0].rsplit('/',1)[-1]} {'>'.join(stack)}\n")
        return "tok"

    class F(rx.State):
        token: str = rx.field(default_factory=_tok)
        maybe_tok: str | None = rx.field(default_factory=_tok)

    app.add_page(lambda: rx.text(F.token, id="tok"), route="/factory")
