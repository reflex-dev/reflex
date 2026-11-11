"""N-024: does the 'Upgrading to Reflex 0.10' guide ("Calling inherited handlers from background tasks") match behaviour?

Guide (a3 source, docs/changelog/upgrading/upgrading-to-0-10.md) claims:
  C1 0.9: `self.inherited_handler()` from a background task ran on the parent state without the lock (wrote outside
     `async with self`); 0.10: goes through the proxy.
  C2 outside `async with self`, a call that MODIFIES state raises ImmutableStateError;
  C3 ... a READ-ONLY handler still runs;
  C4 inside the lock, `type(self)` in the called handler is `StateProxy`;
  C5 `self.__class__` gives "the state class"; C6 `isinstance(self, Parent)` still works;
  C7 a handler declared on the SAME state was already called through the proxy (0.9 too);
  C8 sample 1 (verbatim): `self.bump()` outside the lock raises ImmutableStateError on 0.10;
  C9 sample 2 (verbatim): `async with self: self.bump()` works on both versions.
Each button records its outcome in Child.results (rendered as #res-<key>); the backend exception handler prints
N024_BACKEND_EXC lines to the server log and counts them in #exc.
"""

import importlib.metadata
import json
import time

import reflex as rx
from reflex.event import EventSpec

# venv guard (a3_events_tp): bin/start.sh exports EV_EXPECT_VENV=<venv name>
_EXPECT_VENV = __import__("os").environ.get("EV_EXPECT_VENV", "")
assert _EXPECT_VENV and f"/envs/{_EXPECT_VENV}/" in rx.__file__, (rx.__file__, _EXPECT_VENV)
print(f"VENV_GUARD ok venv={_EXPECT_VENV} reflex={rx.__file__}", flush=True)

VERSION = importlib.metadata.version("reflex")
EXC = []


def mark(msg: str) -> None:
    print(f"N024 {time.time():.3f} {msg}", flush=True)


def on_backend_exc(exception: Exception) -> EventSpec | None:
    EXC.append(f"{type(exception).__name__}: {str(exception)[:120]}")
    mark(f"N024_BACKEND_EXC {type(exception).__name__}: {exception}")
    return None


def describe(obj, parent_cls) -> str:
    return (f"type={type(obj).__name__},cls={obj.__class__.__name__},"
            f"isinst_parent={isinstance(obj, parent_cls)},kind={obj._kind()}")


# --- the guide's sample, verbatim names (Parent/Child/count/bump/work) plus probes
class Parent(rx.State):
    count: int = 0
    seen: list[str] = []

    @rx.event
    def bump(self):
        self.seen.append("bump:" + describe(self, Parent))
        self.count += 1

    @rx.event
    def peek(self):
        # read-only handler: reads state, never writes
        mark(f"peek count={self.count} {describe(self, Parent)}")

    def _kind(self) -> str:
        return "parent"

    @rx.event(background=True)
    async def own_bg_outside(self):
        # C7: handler declared on the SAME state, called from that state's own background task outside the lock
        try:
            self.bump()
            res = "no-error"
        except Exception as e:
            res = type(e).__name__
        async with self:
            self.seen.append(f"own_bg_outside={res}")


class Child(Parent):
    results: dict[str, str] = {}
    exc_count: int = 0
    own: int = 0
    own_items: list[str] = []

    def _kind(self) -> str:
        return "child"

    def _rec(self, key: str, val: str) -> None:
        self.results = {**self.results, key: val}

    @rx.event
    def own_write(self):
        self.count += 0

    # C7 variants: handlers declared on Child itself
    @rx.event
    def write_own(self):
        self.own += 1

    @rx.event
    def append_own(self):
        self.own_items.append("x")

    @rx.event
    def write_inherited(self):
        self.count += 1

    @rx.event
    def read_own(self):
        mark(f"read_own own={self.own}")

    # direct writes (no handler call) from the background task outside the lock, for comparison
    @rx.event(background=True)
    async def direct_write(self, which: str):
        try:
            if which == "inherited":
                self.count += 1
            elif which == "inherited_list":
                self.seen.append("direct-inherited-append")
            else:
                self.own += 1
            res = "no-error"
        except Exception as e:
            res = type(e).__name__
        async with self:
            self._rec(f"direct_write:{which}", f"{res} own={self.own} count={self.count}")

    @rx.event(background=True)
    async def outside_call(self, name: str):
        try:
            getattr(self, name)()
            res = "no-error"
        except Exception as e:
            res = type(e).__name__
        async with self:
            self._rec(f"outside_call:{name}", f"{res} own={self.own} items={len(self.own_items)} count={self.count}")

    # C8 sample 1 verbatim
    @rx.event(background=True)
    async def work(self):
        self.bump()  # Raises ImmutableStateError on 0.10.

    # C9 sample 2 verbatim (renamed: two handlers cannot share a name)
    @rx.event(background=True)
    async def work_locked(self):
        async with self:
            self.bump()

    # C2: modifying inherited handler outside the lock, outcome recorded
    @rx.event(background=True)
    async def outside_modify(self):
        try:
            self.bump()
            res = "no-error"
        except Exception as e:
            res = type(e).__name__
        async with self:
            self._rec("outside_modify", res)

    # C3: read-only inherited handler outside the lock
    @rx.event(background=True)
    async def outside_readonly(self):
        try:
            self.peek()
            res = "ran"
        except Exception as e:
            res = type(e).__name__
        async with self:
            self._rec("outside_readonly", res)

    # C7 from the child: handler declared on Child itself, outside the lock
    @rx.event(background=True)
    async def outside_own_handler(self):
        try:
            self.own_write()
            res = "no-error"
        except Exception as e:
            res = type(e).__name__
        async with self:
            self._rec("outside_own_handler", res)

    # C4/C5/C6 inside the lock vs a foreground call from the same child
    @rx.event(background=True)
    async def inside_describe(self):
        async with self:
            self.bump()
            self._rec("inside_lock", self.seen[-1])

    @rx.event
    def fg_describe(self):
        self.bump()
        self._rec("foreground", self.seen[-1])

    @rx.var
    def results_json(self) -> str:
        return json.dumps(self.results, sort_keys=True)

    @rx.event
    def refresh(self):
        self.exc_count = len(EXC)

    @rx.event
    def reset_all(self):
        self.results = {}
        self.seen = []
        self.count = 0
        EXC.clear()
        self.exc_count = 0


BUTTONS = ["work", "work_locked", "outside_modify", "outside_readonly", "outside_own_handler", "inside_describe",
           "fg_describe", "refresh", "reset_all"]
KEYS = ["outside_modify", "outside_readonly", "outside_own_handler", "inside_lock", "foreground"]


def index() -> rx.Component:
    return rx.vstack(
        rx.heading(f"N-024 docs claims (reflex {VERSION})"),
        rx.text(rx.State.router.session.client_token, id="token"),
        rx.hstack(*[rx.button(b, id=f"btn-{b}", on_click=getattr(Child, b)) for b in BUTTONS], wrap="wrap"),
        rx.button("parent own_bg_outside", id="btn-own_bg_outside", on_click=Parent.own_bg_outside),
        rx.hstack(*[rx.button(f"outside_call {n}", id=f"btn-oc-{n}", on_click=Child.outside_call(n))
                    for n in ["write_own", "append_own", "write_inherited", "own_write", "read_own", "bump", "peek"]]),
        rx.hstack(*[rx.button(f"direct_write {n}", id=f"btn-dw-{n}", on_click=Child.direct_write(n))
                    for n in ["own", "inherited", "inherited_list"]]),
        rx.text("count=", Parent.count, id="count"),
        rx.text("exc=", Child.exc_count, id="exc"),
        rx.text(Parent.seen.join(" | "), id="seen"),
        rx.text(Child.results_json, id="results"),
    )


app = rx.App(backend_exception_handler=on_backend_exc)
app.add_page(index, route="/")
