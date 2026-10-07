"""Verifier probe for a3_class_state-7: which rejection paths skip the undo entry.

For each var kind: configure a class default (C.v = good1), then run
`mock.patch.object(C, "v", <value>)` around nothing and report the default
afterwards. A correct round trip leaves good1 in place whether the patch was
accepted or rejected.

Run: EXPECT_VENV=<venv-dir-name> <venv>/bin/python -I probe_v7_paths.py
"""

import dataclasses
import os
from typing import Any, Literal, Optional
from unittest import mock

import reflex

assert f"/envs/{os.environ['EXPECT_VENV']}/" in reflex.__file__, reflex.__file__

import reflex as rx  # noqa: E402

VERSION = reflex.__file__.split("/envs/")[1].split("/")[0]


@dataclasses.dataclass
class Pt:
    x: int = 0


class Other(rx.State):
    y: int = 3


calls = []


def raising_factory():
    calls.append("raising_factory")
    raise RuntimeError("factory boom")


CASES = [
    # name, annotation, declared default (or rx.field(...)), configured value, patch value
    ("int_var_value", int, 0, 10, Other.y),
    ("int_field_value", int, 0, 10, rx.field(5)),
    ("int_wrong_type", int, 0, 10, "x"),
    ("int_raising_callable", int, 0, 10, raising_factory),
    ("literal_bad", Literal["a", "b", "c"], "a", "b", "zzz"),
    ("dict_bad", dict[str, int], {}, {"k": 1}, ["not", "a", "dict"]),
    ("dataclass_bad", Pt, Pt(), Pt(5), 7),
    ("optional_ok", Optional[int], None, 4, None),
    ("tuple_bad", tuple[int, ...], (), (1, 2), "nope"),
    ("any_magicmock", Any, None, 1, mock.MagicMock()),
    ("str_storage_decl_factory_raising", str, rx.field(default_factory=raising_factory), "cfg", "patched"),
]


def default_of(cls, name):
    try:
        s = cls(_reflex_internal_init=True)
        return getattr(s, name)
    except Exception as err:  # noqa: BLE001
        return f"<{type(err).__name__}: {err}>"


for i, (name, ann, declared, configured, patch_value) in enumerate(CASES):
    ns = {"__module__": __name__, "__annotations__": {"v": ann}, "v": declared}
    try:
        C = type(f"P{i}_{name}", (rx.State,), ns)
    except Exception as err:  # noqa: BLE001
        print(f"[{VERSION}] {name}: class creation failed {type(err).__name__}: {err}")
        continue
    try:
        C.v = configured
        cfg_err = None
    except Exception as err:  # noqa: BLE001
        cfg_err = f"{type(err).__name__}: {err}"
    before = default_of(C, "v")
    patch_err = None
    try:
        with mock.patch.object(C, "v", patch_value):
            inside = default_of(C, "v")
    except Exception as err:  # noqa: BLE001
        patch_err = f"{type(err).__name__}: {str(err)[:70]}"
        inside = "-"
    after = default_of(C, "v")
    ok = repr(after) == repr(before)
    print(
        f"[{VERSION}] {name:34s} configure_err={cfg_err!s:10.10s} before={before!r} inside={inside!r} "
        f"patch_err={patch_err} after={after!r} -> {'OK' if ok else 'LOST/LEAKED'}"
    )
