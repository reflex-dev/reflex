"""T-2 matrix: class-level assignment to State backend-var placeholders, with side-effect counters.

Independent verifier probe (authored without reading the explorer's probes).

For every (declaration, assigned value) pair a FRESH State class is built, the assignment is attempted,
and we record: the exception (if any), how many times user code ran during the assignment (counters),
what a fresh instance reads afterwards, and what the class attribute reads as.

Run: REFLEX_TELEMETRY_ENABLED=false EXPECT_VENV=<venv> <venv>/bin/python -I t2_matrix.py [out.json]
"""

import json
import os
import sys
from typing import Any, Callable, Optional
from unittest import mock

import httpx
import reflex as rx

EXPECT = os.environ["EXPECT_VENV"]
assert f"/envs/{EXPECT}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

REFLEX_VERSION = version("reflex")


class Client:
    """A zero-arg-constructible 'client' whose construction is a visible side effect."""

    made = 0

    def __init__(self):
        Client.made += 1


class CallableThing:
    """A callable instance (like sessionmaker / functools.partial / a factory object)."""

    calls = 0

    def __call__(self):
        CallableThing.calls += 1
        return "from-callable"


class NotCallable:
    pass


def counters():
    return {"Client.made": Client.made, "CallableThing.calls": CallableThing.calls, "fn.calls": FN_CALLS[0]}


FN_CALLS = [0]


def counting_fn():
    FN_CALLS[0] += 1
    return "from-fn"


def counting_fn_returns_none():
    FN_CALLS[0] += 1
    return None


def inst(cls):
    try:
        return cls(_reflex_internal_init=True)
    except TypeError:
        return cls()


def plain(v):
    v = getattr(v, "__wrapped__", v)
    if isinstance(v, (int, float, str, bool, type(None), list, tuple, dict)):
        return v
    return f"<{type(v).__name__}>"


# ------------------------------------------------------------ declarations
def decl_none():
    class Cfg(rx.State):
        _slot = None

    return Cfg


def decl_zero():
    class Cfg(rx.State):
        _slot = 0

    return Cfg


def decl_empty_str():
    class Cfg(rx.State):
        _slot = ""

    return Cfg


def decl_false():
    class Cfg(rx.State):
        _slot = False

    return Cfg


def decl_empty_list():
    class Cfg(rx.State):
        _slot = []

    return Cfg


def decl_empty_dict():
    class Cfg(rx.State):
        _slot = {}

    return Cfg


def decl_pub_none():
    class Cfg(rx.State):
        slot = None

    return Cfg


def decl_ann_str():
    class Cfg(rx.State):
        _slot: str = ""

    return Cfg


def decl_ann_int():
    class Cfg(rx.State):
        _slot: int = 0

    return Cfg


def decl_ann_optional_client():
    class Cfg(rx.State):
        _slot: Optional[Client] = None

    return Cfg


def decl_ann_pep604_client():
    class Cfg(rx.State):
        _slot: Client | None = None

    return Cfg


def decl_ann_any():
    class Cfg(rx.State):
        _slot: Any = None

    return Cfg


def decl_ann_callable_or_none():
    class Cfg(rx.State):
        _slot: Callable[..., Any] | None = None

    return Cfg


def decl_ann_object():
    class Cfg(rx.State):
        _slot: object = None

    return Cfg


def decl_ann_client_default_none():
    class Cfg(rx.State):
        _slot: Client = None  # type: ignore[assignment]

    return Cfg


def decl_ann_httpx_optional():
    class Cfg(rx.State):
        _slot: httpx.Client | None = None

    return Cfg


def decl_ann_str_forward():
    class Cfg(rx.State):
        _slot: "Client | None" = None

    return Cfg


DECLS = {
    "_slot = None            (unannotated)": decl_none,
    "_slot = 0               (unannotated)": decl_zero,
    "_slot = ''              (unannotated)": decl_empty_str,
    "_slot = False           (unannotated)": decl_false,
    "_slot = []              (unannotated)": decl_empty_list,
    "_slot = {}              (unannotated)": decl_empty_dict,
    "slot = None             (unannotated, PUBLIC)": decl_pub_none,
    "_slot: str = ''": decl_ann_str,
    "_slot: int = 0": decl_ann_int,
    "_slot: Optional[Client] = None": decl_ann_optional_client,
    "_slot: Client | None = None": decl_ann_pep604_client,
    "_slot: 'Client | None' = None   (string annotation)": decl_ann_str_forward,
    "_slot: Any = None": decl_ann_any,
    "_slot: Callable[..., Any] | None = None": decl_ann_callable_or_none,
    "_slot: object = None": decl_ann_object,
    "_slot: Client = None    (annotation excludes None)": decl_ann_client_default_none,
    "_slot: httpx.Client | None = None": decl_ann_httpx_optional,
}

# ------------------------------------------------------------ assigned values
VALUES = {
    "Client() instance (not callable)": lambda: Client(),
    "Client class (callable, 0-arg ctor)": lambda: Client,
    "'a-string'": lambda: "a-string",
    "42": lambda: 42,
    "'five' (for int-ish slots)": lambda: "five",
    "None": lambda: None,
    "1 (int for bool/str slot)": lambda: 1,
    "[1] (list)": lambda: [1],
    "CallableThing() (callable instance)": lambda: CallableThing(),
    "counting_fn (0-arg function -> 'from-fn')": lambda: counting_fn,
    "lambda: 1 (0-arg function -> int)": lambda: (lambda: 1),
    "lambda x: x (needs an argument)": lambda: (lambda x: x),
    "MagicMock()": lambda: mock.MagicMock(),
    "MagicMock(spec=Client)": lambda: mock.MagicMock(spec=Client),
    "httpx.Client() (not callable)": lambda: httpx.Client(),
}


def run_one(decl_label, decl_fn, val_label, val_fn):
    row = {"decl": decl_label, "value": val_label}
    try:
        cls = decl_fn()
    except Exception as e:  # noqa: BLE001
        row["decl_error"] = f"{type(e).__name__}: {str(e)[:150]}"
        return row
    try:
        value = val_fn()
    except Exception as e:  # noqa: BLE001
        row["value_error"] = f"{type(e).__name__}: {str(e)[:100]}"
        return row
    name = "slot" if "slot" in cls.get_fields() and "_slot" not in cls.get_fields() else "_slot"
    row["before_inst"] = plain(getattr(inst(cls), name))
    c0 = counters()
    try:
        setattr(cls, name, value)
        row["error"] = None
    except Exception as e:  # noqa: BLE001
        row["error"] = f"{type(e).__name__}: {str(e)[:170]}"
    c1 = counters()
    row["side_effects"] = {k: c1[k] - c0[k] for k in c0 if c1[k] != c0[k]}
    try:
        row["after_inst"] = plain(getattr(inst(cls), name))
    except Exception as e:  # noqa: BLE001
        row["after_inst"] = f"<{type(e).__name__}: {str(e)[:60]}>"
    row["class_read"] = type(getattr(cls, name)).__name__
    return row


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else None
    rows = []
    for dl, df in DECLS.items():
        for vl, vf in VALUES.items():
            rows.append(run_one(dl, df, vl, vf))
    if out:
        with open(out, "w") as fh:
            json.dump({"reflex": REFLEX_VERSION, "venv": EXPECT, "rows": rows}, fh, indent=1, default=repr)
    print(f"reflex {REFLEX_VERSION}  (venv {EXPECT})")
    cur = None
    for r in rows:
        if r["decl"] != cur:
            cur = r["decl"]
            print(f"\n== {cur}")
        if "decl_error" in r:
            print(f"   DECL ERROR {r['decl_error']}")
            continue
        if "value_error" in r:
            print(f"   {r['value']:<44} VALUE ERROR {r['value_error']}")
            continue
        se = f" SIDE-EFFECTS={r['side_effects']}" if r["side_effects"] else ""
        if r["error"]:
            print(f"   {r['value']:<44} RAISES {r['error'][:110]}{se}")
        else:
            print(f"   {r['value']:<44} ok     inst reads {r['after_inst']!r:<22} class reads {r['class_read']}{se}")


if __name__ == "__main__":
    main()
