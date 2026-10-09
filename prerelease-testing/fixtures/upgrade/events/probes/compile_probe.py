"""Probe how nested/conditional event lists compile (run with alpha or stable venv)."""
import sys
import reflex as rx
venv = sys.argv[1]
assert f"/envs/{venv}/" in rx.__file__, rx.__file__
print("reflex", rx.__version__ if hasattr(rx, "__version__") else "?")


class S(rx.State):
    flag: bool = True
    order: list[str] = []

    @rx.event
    def ev(self, name: str):
        self.order.append(name)


def show(label, fn):
    try:
        c = fn()
        r = str(c)
        i = r.find("onClick")
        print(f"[{label}] OK:", r[i:i+400].replace("\n", " ") if i >= 0 else r[:400])
    except Exception as e:
        print(f"[{label}] ERROR: {type(e).__name__}: {e}")


show("nested_list", lambda: rx.button("x", on_click=[S.ev("E"), [S.ev("F")]]))
show("deep3", lambda: rx.button("x", on_click=[S.ev("A"), [S.ev("B"), [S.ev("C")]], S.ev("D")]))
show("cond_lists", lambda: rx.button("x", on_click=rx.cond(S.flag, [S.ev("G1"), S.ev("G2")], [S.ev("H")])))
show("match_lists", lambda: rx.button("x", on_click=rx.match(S.flag, (True, [S.ev("M1"), S.ev("M2")]), [S.ev("M3")])))
show("cond_nested_in_list", lambda: rx.button("x", on_click=[S.ev("Q0"), rx.cond(S.flag, [S.ev("Q1"), S.ev("Q2")], S.ev("Q3")), S.ev("Q4")]))
def deep(n):
    x = [S.ev("Z")]
    for _ in range(n):
        x = [x]
    return x
show("depth50", lambda: rx.button("x", on_click=deep(50)))
show("call_script_cb", lambda: rx.button("x", on_click=rx.call_script("1+1", callback=S.ev)))
show("run_script", lambda: rx.button("x", on_click=[S.ev("R0"), rx.run_script("console.log('rs')"), S.ev("R1")]))
