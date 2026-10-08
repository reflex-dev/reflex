"""Issue 2 verifier: state_auto_setters=True + parent var `set_<x>` + child var `<x>`.

Run with cwd = autoset_on/ (rxconfig state_auto_setters=True) or autoset_off/ (default):
  cd $W/autoset_on && EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I ../probe_autoset2.py
"""
import os
import sys
import traceback

sys.path.insert(0, os.getcwd())
import reflex as rx  # noqa: E402

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

from reflex.compiler.utils import compile_state  # noqa: E402

print(f"reflex {version('reflex')} auto_setters={rx.config.get_config().state_auto_setters}", flush=True)


def row(name, fn):
    try:
        r = fn()
    except Exception as e:  # noqa: BLE001
        tb = traceback.extract_tb(e.__traceback__)
        r = f"EXC {type(e).__name__}: {str(e)[:200]} @ {[f'{os.path.basename(t.filename)}:{t.lineno}' for t in tb[-3:]]}"
    print(f"ROW {name} | {r}", flush=True)


def kind(v):
    return f"{type(v).__name__}({getattr(v, '_js_expr', '')})" if hasattr(v, "_js_expr") else type(v).__name__


def inherited_collision():
    class PColl(rx.State):
        set_color: str = "p"

    class CColl(PColl):
        color: str = "c"

    globals().update(PColl=PColl, CColl=CColl)
    p = PColl(_reflex_internal_init=True)
    c = p.substates[CColl.get_name()]
    out = [f"created; CColl.set_color={kind(CColl.__dict__.get('set_color', CColl.set_color))} PColl.set_color={kind(PColl.set_color)}"]
    out.append(f"'set_color' in CColl.event_handlers={'set_color' in CColl.event_handlers} in CColl.__fields__={'set_color' in getattr(CColl, '__fields__', {})}")
    if "set_color" in CColl.event_handlers:
        CColl.event_handlers["set_color"].fn(c, "blue")
        out.append(f"child setter -> c.color={c.color!r}")
    else:
        out.append("no auto setter (auto setters off)")
    try:
        out.append(f"c.set_color (instance read)={kind(c.set_color)}")
    except Exception as e:  # noqa: BLE001
        out.append(f"c.set_color read: {type(e).__name__}")
    p.set_color = "pp"
    out.append(f"parent var still works: p.set_color={p.set_color!r}")
    st = compile_state(PColl)
    out.append(f"compiled P keys={sorted(st[PColl.get_full_name()])} C keys={sorted(st[CColl.get_full_name()])}")
    try:
        out.append(f"rx.text(CColl.set_color) -> {type(rx.text(CColl.set_color)).__name__}")
    except Exception as e:  # noqa: BLE001
        out.append(f"rx.text(CColl.set_color) -> {type(e).__name__}: {str(e)[:80]}")
    return "; ".join(out)


row("1 parent var set_color + child var color", inherited_collision)


def same_class():
    class SSame(rx.State):
        set_color: str = "p"
        color: str = "c"

    globals()["SSame"] = SSame
    s = SSame(_reflex_internal_init=True)
    return (f"created; SSame.set_color={kind(SSame.set_color)} 'set_color' in event_handlers={'set_color' in SSame.event_handlers}; "
            f"s.set_color={s.set_color!r}")


row("2 same class: set_color var + color var", same_class)


def explicit_handler_override():
    class PExp(rx.State):
        set_color: str = "p"

    class CExp(PExp):
        color: str = "c"

        @rx.event
        def set_color(self, v: str):
            self.color = v

    globals().update(PExp=PExp, CExp=CExp)
    return f"created; CExp.set_color={kind(CExp.set_color)}"


row("3 child declares an explicit handler named like an inherited var (set_color)", explicit_handler_override)


def grand():
    class GA(rx.State):
        set_size: int = 0

    class GB(GA):
        pass

    class GC(GB):
        size: int = 1

    globals().update(GA=GA, GB=GB, GC=GC)
    return "created"


row("4 grandparent var set_size + grandchild var size", grand)
