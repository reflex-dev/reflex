"""#7456 re-verification: what happens when a backend var read on the class is used in the UI.

Usage: <venv>/bin/python derive_e_format.py <expected-venv-name>
Run from a neutral directory. One line per probe: the result or the exception (type + full message).
"""

import os
import sys

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

from reflex_base.utils import exceptions as rxe  # noqa: E402

print(f"reflex {version('reflex')}  REFLEX_ENV_MODE={os.environ.get('REFLEX_ENV_MODE', '<unset>')}")
print("BackendVarFormatError exists:", hasattr(rxe, "BackendVarFormatError"),
      "| subclass of VarTypeError:", hasattr(rxe, "BackendVarFormatError") and issubclass(rxe.BackendVarFormatError, rxe.VarTypeError))


class Mix(rx.State, mixin=True):
    m_pub: str = "mixin-frontend"
    _m_be: str = "mixin-backend"


class S(Mix, rx.State):
    _size: int = 16
    _label = "label"
    _items: list[str] = ["a", "b"]
    _flag: bool = True
    _cfg: dict[str, str] = {"color": "red"}
    _nonvar: str = rx.field("nv", is_var=False)
    count: int = 0

    @rx.event
    def takes(self, v: str):
        pass


def show(name, fn):
    try:
        r = fn()
        if isinstance(r, rx.Component):
            r = str(r)
        r = repr(r)
        print(f"{name:52} -> OK {r[:150]}")
    except Exception as e:  # noqa: BLE001
        print(f"{name:52} -> {type(e).__name__}: {str(e)[:400]}")


print("--- formatting into a string")
show('f"{S._size}px"', lambda: f"{S._size}px")
show('"{}px".format(S._size)', lambda: "{}px".format(S._size))
show('format(S._size)', lambda: format(S._size))
show('f"{S._size!s}px"  (explicit str conversion)', lambda: f"{S._size!s}px")
show('str(S._size) + "px"', lambda: str(S._size) + "px")
show('"%s px" % S._size', lambda: "%s px" % S._size)
show('"x" + S._label', lambda: "x" + S._label)
show('f"{S._nonvar}" (is_var=False field)', lambda: f"{S._nonvar}")
show('f"{Mix._m_be}" (mixin backend)', lambda: f"{Mix._m_be}")
show('f"{Mix.m_pub}" (mixin frontend)', lambda: f"{Mix.m_pub}")
show('f"{S.m_pub}" (mixin frontend via user state)', lambda: f"{S.m_pub}")
show('f"{rx.field(3)}" (unbound field)', lambda: f"{rx.field(3)}")
show('print(S._size) (uses str)', lambda: print("   printed:", S._size))
print("--- as a child / prop / style / control flow")
show("rx.text(S._label)  [child]", lambda: rx.text(S._label))
show('rx.text(f"w={S._size}")  [f-string child]', lambda: rx.text(f"w={S._size}"))
show("rx.box(width=S._size)  [prop]", lambda: rx.box(width=S._size))
show("rx.icon('x', size=S._size)  [typed prop]", lambda: rx.icon("x", size=S._size))
show("rx.box(id=S._label)  [id prop]", lambda: rx.box(id=S._label))
show('rx.box(style={"width": S._size})', lambda: rx.box(style={"width": S._size}))
show('rx.box(class_name=[S._label])', lambda: rx.box(class_name=[S._label]))
show("rx.foreach(S._items, rx.text)", lambda: rx.foreach(S._items, rx.text))
show("rx.cond(S._flag, 'y', 'n')", lambda: rx.cond(S._flag, rx.text("y"), rx.text("n")))
show("rx.match(S._label, ('label', rx.text('m')), rx.text('d'))", lambda: rx.match(S._label, ("label", rx.text("m")), rx.text("d")))
show("rx.Var.create(S._size)", lambda: rx.Var.create(S._size))
show("rx.button(on_click=S.takes(S._label))  [event arg]", lambda: rx.button("b", on_click=S.takes(S._label)))
show("rx.button(on_click=rx.console_log(S._label))", lambda: rx.button("b", on_click=rx.console_log(S._label)))
show("rx.link('l', href=S._label)", lambda: rx.link("l", href=S._label))
show("rx.button(S._label)  [button child]", lambda: rx.button(S._label))
print("--- documented fix: default_value()")
show("S._items.default_value()", lambda: S._items.default_value())
show("rx.foreach(S._items.default_value(), rx.text)", lambda: rx.foreach(S._items.default_value(), rx.text))
show('rx.text(f"{S._size.default_value()}px")', lambda: rx.text(f"{S._size.default_value()}px"))
show("rx.box(width=f'{S._size.default_value()}px')", lambda: rx.box(width=f"{S._size.default_value()}px"))
show("S._cfg.default_value() is fresh copy", lambda: S._cfg.default_value() is not S._cfg.default_value())
print("--- instance-level (must be unaffected)")
root = rx.State(_reflex_internal_init=True)
inst = root.get_substate(S.get_full_name().split(".")[1:])
show('f"{inst._size}px"', lambda: f"{inst._size}px")
show("inst.count = S._size  (mistyped assignment of a Field)", lambda: setattr(inst, "count", S._size) or inst.count)
