"""Schema hash (`_to_schema()`) of several state shapes, to compare a3 / a4 / 0.9.12.
Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I schema_hashes.py"""
import hashlib
import os
from typing import ClassVar, Optional

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402


class HBase(rx.State):
    count: int = 0
    items: list[str] = []
    opt: Optional[int] = None
    _secret: str = "s"
    CFG: ClassVar[int] = 3
    theme: str = rx.LocalStorage("light", name="h_theme")
    ck: str = rx.Cookie("c", max_age=60)


class HMix(rx.State, mixin=True):
    m: int = 1


class HChild(HMix, HBase):
    note: str = "n"
    _b: dict = {}


class HCfg(rx.State):
    limit: int = 0


HCfg.__fields__["limit"].default = 10  # field-configured default must not change the schema


def h(cls):
    s = repr(cls._to_schema()) if hasattr(cls, "_to_schema") else "n/a"
    return hashlib.sha256(s.encode()).hexdigest()[:16]


print(f"reflex {version('reflex')}: " + " ".join(f"{c.__name__}={h(c)}" for c in (HBase, HChild, HCfg)))
