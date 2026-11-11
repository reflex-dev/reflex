"""Probe #7807/#7810 merge semantics and FINDING-016 (staticmethod/classmethod above @rx.event).

usage (neutral cwd): EXPECT_VENV=<venv> <venv>/bin/python -I deco_semantics.py
"""
import contextlib
import io
import os
import warnings

import reflex as rx

assert os.environ["EXPECT_VENV"] in rx.__file__, rx.__file__
from importlib.metadata import version

print("reflex", version("reflex"))


def run(label, fn):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf), warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            res = fn()
        except Exception as ex:
            res = f"RAISES {type(ex).__name__}: {str(ex)[:160]}"
    msgs = " ".join(buf.getvalue().split()) + " ".join(str(x.message)[:120] for x in w)
    print(f"- {label:52s} {res}")
    if msgs.strip():
        print(f"    out/warn: {msgs[:260]}")


def outer_false_bg():
    class A(rx.State):
        @rx.event(background=False)
        @rx.event(background=True)
        async def h(self):
            pass
    return f"bg={A.event_handlers['h'].is_background}"


def outer_true_bg_over_false():
    class B(rx.State):
        @rx.event(background=True)
        @rx.event(background=False)
        async def h(self):
            pass
    return f"bg={B.event_handlers['h'].is_background}"


def throttle_zero_override():
    class C(rx.State):
        @rx.event(throttle=0)
        @rx.event(throttle=300)
        def h(self):
            pass
    return f"actions={C.event_handlers['h'].event_actions}"


def merge_actions():
    class C2(rx.State):
        @rx.event(debounce=50)
        @rx.event(throttle=300)
        def h(self):
            pass
    return f"actions={C2.event_handlers['h'].event_actions}"


def supersedes_false():
    class C3(rx.State):
        @rx.event(supersedes=False)
        @rx.event(supersedes=True)
        def h(self):
            pass
    eh = C3.event_handlers["h"]
    return f"supersedes attrs={ {k: v for k, v in vars(eh.fn).items() if 'super' in k.lower() or 'rx' in k.lower()} }"


class Other(rx.State):
    v: int = 0

    @rx.event
    def handle(self):
        self.v += 1


def other_state_plain():
    class D(rx.State):
        h = rx.event(Other.handle)
    return f"created; registered={'h' in D.event_handlers} Other.handle.bg={Other.handle.is_background}"


def other_state_bg():
    class E(rx.State):
        h = rx.event(background=True)(Other.handle)
    return f"created; Other.handle.bg={Other.handle.is_background}"


def other_state_outside_class():
    return repr(rx.event(Other.handle))[:100]


def static_over():
    class F(rx.State):
        @staticmethod
        @rx.event
        def static_over(x: int):
            return x * 2

        @classmethod
        @rx.event
        def cls_over(cls, x: int):
            return (cls.__name__, x * 3)
    return f"F.static_over(3)={F.static_over(3)!r} F().static_over(3)? cls_over={F.cls_over(3)!r} registered={sorted(k for k in F.event_handlers if 'over' in k)}"


def static_over_instance():
    class G(rx.State):
        @staticmethod
        @rx.event
        def s(x: int):
            return x * 2
    return f"G.s(3)={G.s(3)!r}"


class Mix(rx.State, mixin=True):
    @staticmethod
    @rx.event
    def ms(x: int):
        return x + 100


def static_via_mixin():
    class H(Mix, rx.State):
        pass
    return f"H.ms(1)={H.ms(1)!r}"


class Helper:
    @staticmethod
    @rx.event
    def static_over_event(x: int):
        return x * 2


def static_non_state():
    return f"Helper.static_over_event(3)={Helper.static_over_event(3)!r}"[:150]


@rx.event
@rx.event
def dec_twice(state: Other, x: int):
    state.v += x


def decentralized_twice():
    names = [k for k in Other.event_handlers if "dec_twice" in k]
    return f"Other handlers matching dec_twice={names} type={type(dec_twice).__name__}"


for label, fn in list(globals().items()):
    pass
for label, fn in [
    ("outer background=False over background=True", outer_false_bg),
    ("outer background=True over background=False", outer_true_bg_over_false),
    ("outer throttle=0 over throttle=300", throttle_zero_override),
    ("debounce=50 over throttle=300 (merge)", merge_actions),
    ("supersedes=False over supersedes=True", supersedes_false),
    ("rx.event(Other.handle) in another state", other_state_plain),
    ("rx.event(background=True)(Other.handle)", other_state_bg),
    ("rx.event(Other.handle) at module level", other_state_outside_class),
    ("staticmethod/classmethod above event [016]", static_over),
    ("staticmethod above event, class call", static_over_instance),
    ("staticmethod above event via mixin", static_via_mixin),
    ("staticmethod above event, non-state class", static_non_state),
    ("decentralized @rx.event twice", decentralized_twice),
]:
    run(label, fn)
