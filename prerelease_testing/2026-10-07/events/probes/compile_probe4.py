import sys
import reflex as rx
venv = sys.argv[1]
assert f"/scratchpad/envs/{venv}/" in rx.__file__, rx.__file__


class S(rx.State):
    @rx.event
    def ev(self, name: str):
        pass


def show(label, fn):
    try:
        c = fn()
        r = str(c)
        i = r.find("onKeyDown")
        print(f"[{label}] OK:", r[i:i+120].replace("\n", " "))
    except BaseException as e:
        print(f"[{label}] ERROR: {type(e).__name__}: {str(e)[-200:]}")


show("lambda->match(list,noop)", lambda: rx.input(on_key_down=lambda key: rx.match(key, ("x", [S.ev("A").prevent_default, S.ev("B")]), rx.noop())))
show("lambda->cond(bool, match, noop)", lambda: rx.input(on_key_down=lambda key: rx.cond(key == "x", rx.match(key, ("x", [S.ev("A").prevent_default, S.ev("B")]), rx.noop()), rx.noop())))
show("lambda->cond(bool, list, noop)", lambda: rx.input(on_key_down=lambda key: rx.cond(key == "x", [S.ev("A").prevent_default, S.ev("B")], rx.noop())))
show("lambda->match(ev, noop)", lambda: rx.input(on_key_down=lambda key: rx.match(key, ("x", S.ev("A")), rx.noop())))
show("on_click=match(list,noop) (no lambda)", lambda: rx.button(on_click=rx.match(S.ev("A").__class__ and "x", ("x", [S.ev("A"), S.ev("B")]), rx.noop())))
