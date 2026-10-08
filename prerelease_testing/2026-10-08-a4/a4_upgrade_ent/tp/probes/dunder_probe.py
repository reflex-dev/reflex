"""F-001 enterprise half at the Python level: the AG Grid model wrapper stores a class on the state and reads it back at class level
(`state_cls.__data_source_params_class__.from_request(...)`, reflex-enterprise wrapper.py:153).

Usage: <venv>/bin/python dunder_probe.py <expected-venv-name>
"""
import sys

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__


class Params:
    @classmethod
    def from_request(cls, req):
        return ("params-from", req)


from typing import Type


class GridMixin(rx.State, mixin=True):
    """Shaped like reflex-enterprise's ModelWrapper: an ANNOTATED dunder default on a mixin, overridden per subclass."""

    __data_source_params_class__: Type[Params] = Params


class SubParams(Params):
    @classmethod
    def from_request(cls, req):
        return ("sub-params-from", req)


class GridState(GridMixin, rx.State):
    __data_source_params_class__ = SubParams  # per-model override (unannotated), as in the demo's model_wrapper_ssrm.py
    _plain_private = Params  # single-underscore control


class AnnState(rx.State):
    __data_source_params_class__: Type[Params] = Params  # annotated dunder declared directly on a state


def show(label, fn):
    try:
        v = fn()
        print(f"{label}: {type(v).__name__} {v!r}"[:200])
    except BaseException as e:  # noqa: BLE001
        print(f"{label}: EXC {type(e).__name__}: {str(e)[:160]}")


show("body-declared __data_source_params_class__ (class read)", lambda: GridState.__data_source_params_class__)
show("  .from_request(1)", lambda: GridState.__data_source_params_class__.from_request(1))
show("annotated dunder directly on a state (class read)", lambda: AnnState.__data_source_params_class__)
show("  .from_request(1)", lambda: AnnState.__data_source_params_class__.from_request(1))
show("annotated dunder inherited from the mixin by a plain subclass", lambda: type("Sub", (GridMixin, rx.State), {"__module__": __name__}).__data_source_params_class__)
GridState.__data_source_params_class__ = Params  # assigned after class creation (what a wrapper does per model)
show("setattr-after-creation __data_source_params_class__ (class read)", lambda: GridState.__data_source_params_class__)
setattr(GridState, "__other_dunder__", Params)
show("setattr(cls, '__other_dunder__', Params) (class read)", lambda: getattr(GridState, "__other_dunder__"))
show("single-underscore control _plain_private (class read)", lambda: GridState._plain_private)
show("'__data_source_params_class__' in get_fields()", lambda: "__data_source_params_class__" in GridState.get_fields())
root = rx.State(_reflex_internal_init=True)
inst = root.get_substate(GridState.get_full_name().split(".")[1:])
show("instance read __data_source_params_class__", lambda: inst.__data_source_params_class__)
