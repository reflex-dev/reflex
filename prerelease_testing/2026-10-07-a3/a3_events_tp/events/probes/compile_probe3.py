import sys
import reflex as rx
venv = sys.argv[1]
assert f"/scratchpad/envs/{venv}/" in rx.__file__, rx.__file__


class S(rx.State):
    key: str = "b"

    @rx.event
    def ev(self, name: str):
        pass


def show(label, fn):
    try:
        c = fn()
        r = str(c)
        i = r.find("onClick")
        print(f"[{label}] OK len={len(r)}:", r[i:i+300].replace("\n", " "))
    except BaseException as e:
        print(f"[{label}] ERROR: {type(e).__name__}: {str(e)[:200]}")


def deep_match(n):
    inner = rx.match(S.key, ("b", [S.ev("Z0")]), rx.noop())
    for i in range(1, n):
        inner = rx.match(S.key, ("b", [S.ev(f"Z{i}"), inner]), rx.noop())
    return inner


show("match nested 2", lambda: rx.button("x", on_click=deep_match(2)))
show("match nested 50", lambda: rx.button("x", on_click=deep_match(50)))
show("malformed 5", lambda: rx.button("x", on_click=rx.match(S.key, ("b", [S.ev("W1"), rx.Var.create(5), S.ev("W2")]), rx.noop())))
show("malformed raw obj", lambda: rx.button("x", on_click=rx.match(S.key, ("b", [S.ev("W1"), rx.Var("({})"), S.ev("W2")]), rx.noop())))
show("boom in match", lambda: rx.button("x", on_click=rx.match(S.key, ("b", [S.ev("Q1"), S.ev("boom"), S.ev("Q2")]), rx.noop())))
show("call_script cb list", lambda: rx.button("x", on_click=rx.call_script("1", callback=[S.ev("CB1"), S.ev("CB2")])))
show("call_script cb lambda list", lambda: rx.button("x", on_click=rx.call_script("1", callback=lambda r: [S.ev(r), S.ev("CB3")])))
show("call_script in match", lambda: rx.button("x", on_click=rx.match(S.key, ("b", [S.ev("C1"), rx.call_script("throw new Error('cs-boom')"), S.ev("C2")]), rx.noop())))
show("run_script in match", lambda: rx.button("x", on_click=rx.match(S.key, ("b", [S.ev("C1"), rx.run_script("window.__rs=1"), S.ev("C2")]), rx.noop())))
