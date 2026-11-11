"""Upgrade guide (docs/changelog/upgrading/upgrading-to-0-10.md @ 555b667c1) statement + sample checks, Python level.

Usage (from a neutral dir, never the checkout):
  REFLEX_ENV_MODE=dev <venv>/bin/python guide_probe.py <expected-venv-name>
Prints one line per check: `<id> | <what> -> <observed>`.
"""

import os
import sys
import threading
from typing import Any, ClassVar, Optional

import reflex as rx

assert f"/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

V = version("reflex")
print(f"reflex {V} reflex-base {version('reflex-base')} REFLEX_ENV_MODE={os.environ.get('REFLEX_ENV_MODE', '<unset>')}")


def t(label, fn):
    try:
        r = fn()
        s = r if isinstance(r, str) else repr(r)
        print(f"{label:78} -> {s}"[:420])
        return r
    except Exception as e:  # noqa: BLE001
        print(f"{label:78} -> EXC {type(e).__module__}.{type(e).__name__}: {str(e)[:300]}"[:520])
        return e


def fresh(cls):
    return rx.State(_reflex_internal_init=True).get_substate(cls.get_full_name().split(".")[1:])


def render(c):
    return str(c).replace("\n", " ")


print("=== S1 Reading a backend var on a state class")


class State(rx.State):
    _items: list[str] = ["a", "b"]
    _endpoint: ClassVar[str] = "https://example.com/api"
    _label: str = "lbl"
    _color: str = "red"
    _flag: bool = True
    _size: int = 16


t("S1.1 type(State._items)", lambda: type(State._items).__module__ + "." + type(State._items).__name__)
t("S1.2 rx.text(State._items)  [guide: ChildrenTypeError]", lambda: render(rx.text(State._items))[:120])
t("S1.3 rx.box(State._label)   [child]", lambda: render(rx.box(State._label))[:120])
t("S1.4 rx.text('x', color=State._color) [guide: TypeError Unsupported type ... for LiteralVar]", lambda: render(rx.text("x", color=State._color))[:120])
t("S1.5 rx.box(id=State._label)  [prop]", lambda: render(rx.box(id=State._label))[:120])
t("S1.6 rx.input(value=State._label)  [prop]", lambda: render(rx.input(value=State._label))[:120])
t("S1.7 rx.image(src=State._label)  [prop]", lambda: render(rx.image(src=State._label))[:120])
t("S1.8 rx.link('x', href=State._label)  [prop]", lambda: render(rx.link("x", href=State._label))[:120])
t("S1.9 rx.box(style={'color': State._color})  [style]", lambda: render(rx.box(style={"color": State._color}))[:120])
t("S1.10 rx.foreach(State._items, rx.text)  [the 0.9 pattern in the sample comment]", lambda: render(rx.foreach(State._items, rx.text))[:120])
t("S1.11 rx.cond(State._flag, rx.text('y'), rx.text('n'))", lambda: render(rx.cond(State._flag, rx.text("y"), rx.text("n")))[:120])
t("S1.12 f'{State._label}'  [guide: BackendVarFormatError]", lambda: f"{State._label}")
t("S1.13 '{}'.format(State._label)  [guide: BackendVarFormatError]", lambda: "{}".format(State._label))
t("S1.14 f'{State._label!r}'  [guide: embeds the Field text]", lambda: f"{State._label!r}")
t("S1.15 f'{State._label!s}'  [guide: embeds the Field text]", lambda: f"{State._label!s}")
t("S1.16 str(State._label)  [guide: embeds the Field text]", lambda: str(State._label))
t("S1.17 '%s' % State._label  [not in guide]", lambda: "%s" % State._label)
t("S1.18 f'{State._size}px'", lambda: f"{State._size}px")
t("S1.19 instance read fresh(State)._items  [guide: unchanged]", lambda: fresh(State)._items)
t("S1.20 sample: State._items.default_value()", lambda: State._items.default_value())
t("S1.21 sample: rx.foreach(State._items.default_value(), rx.text) renders a,b", lambda: render(rx.foreach(State._items.default_value(), rx.text))[:160])
t("S1.22 sample: type(State._endpoint), rx.text(State._endpoint)", lambda: (type(State._endpoint).__name__, render(rx.text(State._endpoint))[:100]))
t("S1.23 sample page: rx.vstack(foreach(default_value), text(ClassVar))", lambda: render(rx.vstack(rx.foreach(State._items.default_value(), rx.text), rx.text(State._endpoint)))[:200])
t("S1.24 portable: State.get_fields()['_items'].default_value()", lambda: State.get_fields()["_items"].default_value())
t("S1.26 BackendVarFormatError message names default_value()/ClassVar", lambda: (lambda e: ("default_value()" in str(e), "ClassVar" in str(e), str(e)[:260]))(t("   (raise)", lambda: f"{State._label}")))

print("=== S2 Assigning a default through a state class")


class Cnt(rx.State):
    count: int = 0


i_before_stored = fresh(Cnt)
i_before_stored.count = 5
i_before_untouched = fresh(Cnt)
Cnt.count = 10
t("S2.1 after Cnt.count = 10: type(Cnt.count)  [0.9: replaced; 0.10: stays a var]", lambda: type(Cnt.count).__name__)
t("S2.2 new instance count  [0.9: declared default 0; 0.10: 10]", lambda: fresh(Cnt).count)
t("S2.3 instance with a stored value (5) keeps it", lambda: i_before_stored.count)
t("S2.4 instance created BEFORE the assignment, count never touched", lambda: i_before_untouched.count)
t("S2.5 reset() of the stored instance -> new default", lambda: (i_before_stored.reset(), i_before_stored.count)[1])
t("S2.6 rx.text(Cnt.count) still renders a reactive var", lambda: render(rx.text(Cnt.count))[:120])
t("S2.7 Cnt.count = 'x'  [guide: TypeError: Invalid default for field]", lambda: setattr(Cnt, "count", "x"))
t("   default after the rejected assignment", lambda: fresh(Cnt).count)


class Client:
    def __init__(self):
        self.lock = threading.Lock()


class Slots(rx.State):
    _client = None
    _client2: Optional[Client] = None
    _any: Any = None
    count2: int = 0
    count3: int = 0
    items: list[str] = []


t("S2.8 unannotated _client = None; Slots._client = Client()  [guide: TypeError]", lambda: setattr(Slots, "_client", Client()))
t("S2.9 unannotated _client = None; Slots._client = None", lambda: setattr(Slots, "_client", None))
CALLS = {"n": 0}


def factory():
    CALLS["n"] += 1
    return 42


t("S2.10 Slots.count2 = factory (zero-arg fn returning int)", lambda: setattr(Slots, "count2", factory))
t("   calls during the assignment  [guide: called once]", lambda: CALLS["n"])
t("   two new instances read count2", lambda: (fresh(Slots).count2, fresh(Slots).count2))
t("   calls after two instances  [factory per instance]", lambda: CALLS["n"])
t("S2.11 Slots.count3 = int (a class, annotation int does not accept the class)", lambda: setattr(Slots, "count3", int))
t("   fresh(Slots).count3", lambda: fresh(Slots).count3)
SIDE = []


def bad_factory():
    SIDE.append("ran")
    return "not-an-int"


t("S2.12 Slots.count3 = bad_factory (returns str)  [side effect runs, then TypeError]", lambda: setattr(Slots, "count3", bad_factory))
t("   side effects executed", lambda: SIDE)
t("   default after the rejected factory (previous one stays)", lambda: fresh(Slots).count3)


def raising_factory():
    raise RuntimeError("boom")


t("S2.13 Slots.count3 = raising_factory  [base_vars: previous default remains]", lambda: setattr(Slots, "count3", raising_factory))
t("   default after the failing factory", lambda: fresh(Slots).count3)
Slots.items = ["x"]
t("S2.14 mutable default copied per instance", lambda: (lambda a, b: (a.items, b.items, a.items is b.items))(fresh(Slots), fresh(Slots)))
t("S2.15 Slots._client2 = Client() (Optional[Client]) accepted", lambda: setattr(Slots, "_client2", Client()))
t("   new instance reads _client2  [guide: TypeError: cannot pickle '_thread.lock' object]", lambda: fresh(Slots)._client2)
t("S2.16 Slots._any = threading.Lock() (Any) accepted", lambda: setattr(Slots, "_any", threading.Lock()))
t("   new instance reads _any  [guide: TypeError: cannot pickle '_thread.lock' object]", lambda: fresh(Slots)._any)


class Shared(rx.State):
    _pool: ClassVar[Client] = Client()


t("S2.17 ClassVar object shared, never copied (identity on two instances)", lambda: fresh(Shared)._pool is fresh(Shared)._pool is Shared._pool)


class Mix(rx.State, mixin=True):
    mval: int = 1


class UsesMixBefore(Mix, rx.State):
    pass


Mix.mval = 5


class UsesMixAfter(Mix, rx.State):
    pass


t("S2.18 mixin: Mix.mval = 5 -> (state defined before, state defined after)  [guide: only after]", lambda: (fresh(UsesMixBefore).mval, fresh(UsesMixAfter).mval))


class Par(rx.State):
    pcount: int = 1


class Chi(Par):
    pass


Chi.pcount = 9
t("S2.19 Chi.pcount = 9 on a subclass -> (Par new instance, Chi new instance)  [base_vars: declaring state changes]", lambda: (fresh(Par).pcount, fresh(Chi).pcount))


class Undo(rx.State):
    u: int = 1


orig = Undo.u
Undo.u = 2
t("S2.20 Undo.u = 2; Undo.u = <Var read before>  [base_vars: undo]", lambda: (setattr(Undo, "u", orig), fresh(Undo).u)[1])
Undo.u = 3
t("S2.21 Undo.u = 3; del Undo.u  [base_vars: undo]", lambda: (delattr(Undo, "u"), fresh(Undo).u)[1])

print("=== S4 Other changes")


class Bg(rx.State):
    async def h(self):
        pass

    @rx.event(background=True)
    async def hb(self):
        pass


t("S4.1 rx.event.BACKGROUND_TASK_MARKER / SUPERSEDES_MARKER", lambda: (getattr(rx.event, "BACKGROUND_TASK_MARKER", "<missing>"), getattr(rx.event, "SUPERSEDES_MARKER", "<missing>")))
t("S4.2 Bg.hb.is_background", lambda: Bg.hb.is_background)
t("S4.3 Bg.h.is_background before marking", lambda: Bg.h.is_background)
t("S4.4 mark Bg.h.fn after first use -> is_background  [guide: ignored, no warning]", lambda: (setattr(Bg.h.fn, getattr(rx.event, "BACKGROUND_TASK_MARKER", "_reflex_background_task"), True), Bg.h.is_background)[1])
t("S4.5 @rx.event(supersedes=True) accepted", lambda: type(rx.event(supersedes=True)).__name__)


class Und(rx.State):
    x: int = 0


u = fresh(Und)
t("S4.6 self.typo = 1 on an instance  [guide: dev raises SetUndefinedStateVarError; prod plain attr]", lambda: (setattr(u, "typo", 1), u.typo)[1])
t("   typo is not a var (not in dict/dirty)", lambda: ("typo" in str(u.dict()), sorted(u.dirty_vars)))
t("S4.7 self._typo__name = 1 (only looks mangled)", lambda: (setattr(u, "_typo__name", 1), u._typo__name)[1])
