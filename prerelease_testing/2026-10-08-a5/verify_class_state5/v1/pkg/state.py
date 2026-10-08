"""Real class statements (not type()) using module-level containers as defaults."""
import dataclasses
import time

import reflex as rx

from pkg.registry import PLUGINS

OPTIONS: list[str] = []          # filled AFTER the class statement (p1)
EARLY: list[str] = []
EARLY.extend(["e1", "e2"])       # filled BEFORE the class statement (p2 control)
REBOUND: list[str] = []          # name rebound after class (p3 control)
LATE_BACKEND_FIELD: list[str] = []
LATE_FRONT_FIELD: list[str] = []
GUESTBOOK: list[str] = []        # naive "global shared" list, appended by handlers (p8)


@dataclasses.dataclass
class Cfg:
    api: str = ""
    retries: int = 0


CFG = Cfg()                      # mutated attribute-wise later (p13)


class VState(rx.State):
    options: list[str] = OPTIONS                                  # p1
    early: list[str] = EARLY                                      # p2
    rebound: list[str] = REBOUND                                  # p3
    _bf: list[str] = rx.field(LATE_BACKEND_FIELD)                 # p4 backend rx.field(value)
    _stamp: float = rx.field(default_factory=time.time)           # p5 backend rx.field(factory)
    ff: list[str] = rx.field(LATE_FRONT_FIELD)                    # p6 frontend rx.field(value)
    _plugins: dict[str, str] = PLUGINS                            # p7 cross-module registry
    entries: list[str] = GUESTBOOK                                # p8 naive shared list
    _cfg: Cfg = CFG                                               # p13 backend dataclass config
    stamp_front: float = rx.field(default_factory=time.time)      # p5b frontend factory

    @rx.event
    def sign(self, name: str):
        GUESTBOOK.append(name)
        self.entries.append(name)


class VChild(VState):
    c: int = 0


OPTIONS.extend(["red", "green"])
REBOUND = ["rebound"]  # noqa: F811  (rebinding the name never reaches the class)
LATE_BACKEND_FIELD.append("late")
LATE_FRONT_FIELD.append("late")
CFG.api, CFG.retries = "https://x", 3
