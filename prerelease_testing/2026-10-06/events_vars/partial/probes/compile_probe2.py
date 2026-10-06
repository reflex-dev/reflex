"""Probe which conditional event-list shapes compile (alpha vs stable)."""
import sys
import reflex as rx
venv = sys.argv[1]
assert f"/scratchpad/envs/{venv}/" in rx.__file__, rx.__file__


class S(rx.State):
    flag: bool = True
    key: str = "b"

    @rx.event
    def ev(self, name: str):
        pass


A, B, C = S.ev("A"), S.ev("B"), S.ev("C")


def show(label, fn, trig="on_click"):
    try:
        c = fn()
        r = str(c)
        i = r.find("onClick") if trig == "on_click" else r.find("onKeyDown")
        print(f"[{label}] OK:", r[i:i+260].replace("\n", " "))
    except Exception as e:
        print(f"[{label}] ERROR: {type(e).__name__}: {str(e)[:160]}")


show("cond(list, noop)", lambda: rx.button("x", on_click=rx.cond(S.flag, [A, B], rx.noop())))
show("cond(list, ev)", lambda: rx.button("x", on_click=rx.cond(S.flag, [A, B], C)))
show("cond(ev, ev)", lambda: rx.button("x", on_click=rx.cond(S.flag, A, B)))
show("cond(list, list)", lambda: rx.button("x", on_click=rx.cond(S.flag, [A, B], [C])))
show("lambda cond(list,list)", lambda: rx.button("x", on_click=lambda: rx.cond(S.flag, [A, B], [C])))
show("lambda cond(list,noop)", lambda: rx.button("x", on_click=lambda: rx.cond(S.flag, [A, B], rx.noop())))
show("match(list, noop)", lambda: rx.button("x", on_click=rx.match(S.key, ("b", [A, B]), rx.noop())))
show("match(list, list)", lambda: rx.button("x", on_click=rx.match(S.key, ("b", [A, B]), [C])))
show("list[ev, cond(list,noop)]", lambda: rx.button("x", on_click=[A, rx.cond(S.flag, [B, C], rx.noop())]))
show("cond(list(nested), noop)", lambda: rx.button("x", on_click=rx.cond(S.flag, [A, [B, [C]]], rx.noop())))
show("issue7319 keydown", lambda: rx.window_event_listener(on_key_down=lambda key, modifiers: rx.cond(modifiers["ctrl_key"] | modifiers["meta_key"], rx.match(key, ("s", rx.noop()), ("b", [A.stop_propagation.prevent_default, B]), rx.noop()), rx.noop())), trig="key")
