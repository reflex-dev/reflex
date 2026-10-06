"""Minimal repro: annotated (non-ClassVar) dunder / underscore class attributes on a State.

reflex-enterprise's AbstractWrapper declares
    __data_source_params_class__: Type[DATASOURCE_PARAMS] = DatasourceParams
and later reads it at class level (wrapper.py:153). This checks what a class-level
read returns on the running reflex version.
Run: <venv>/bin/python -I repro_dunder_annotated_classattr.py <venv-name>
"""
import sys
from typing import ClassVar, Type

import reflex as rx

venv = sys.argv[1]
assert f"/scratchpad/envs/{venv}/" in rx.__file__, rx.__file__


class Params:
    @classmethod
    def from_request(cls, data):
        return f"{cls.__name__}.from_request ok"


class ChildParams(Params):
    pass


class S(rx.State):
    __dunder_annotated__: Type[Params] = Params
    __dunder_classvar__: ClassVar[Type[Params]] = Params
    _under_annotated: Type[Params] = Params
    __dunder_plain__ = Params


class Sub(S):
    __dunder_annotated__ = ChildParams  # plain override in subclass (as FriendModelWrapperSSRM does)


import importlib.metadata as m

print("reflex", m.version("reflex"))
for name in ("__dunder_annotated__", "__dunder_classvar__", "_under_annotated", "__dunder_plain__"):
    v = getattr(S, name)
    try:
        r = v.from_request({})
    except Exception as e:  # noqa: BLE001
        r = f"{type(e).__name__}: {e}"
    print(f"S.{name}: type={type(v).__name__} -> {r}")
v = Sub.__dunder_annotated__
print(f"Sub.__dunder_annotated__ (plain override): type={type(v).__name__} -> {getattr(v, 'from_request', lambda d: 'n/a')({})}")
print("backend_vars keys:", sorted(k for k in getattr(S, "backend_vars", {}) if "dunder" in k or "under" in k))
print("vars keys:", sorted(k for k in S.vars if "dunder" in k or "under" in k))
