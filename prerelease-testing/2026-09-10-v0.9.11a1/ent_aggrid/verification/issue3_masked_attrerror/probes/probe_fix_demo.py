"""Does the claimant's suggested direction actually recover the real error?

Monkeypatch reflex_base.vars.base.cached_property.__get__ so an AttributeError
escaping the cached computation is re-raised as a non-AttributeError with the
original chained as __cause__ (so Python's attribute protocol does not fall back
to Var.__getattr__), then repeat the failing cases.
"""

import importlib.metadata as md
import traceback

import reflex as rx

assert "/envs/" in rx.__file__, rx.__file__
print("reflex:", md.version("reflex"), "| reflex-base:", md.version("reflex-base"))

from reflex_base.vars import base as vb  # noqa: E402


class CachedComputationError(RuntimeError):
    """Raised when a cached var computation fails with AttributeError."""


_orig_get = vb.cached_property.__get__


def patched_get(self, instance, owner=None):
    """Re-raise AttributeError from the cached computation as a non-AttributeError."""
    try:
        return _orig_get(self, instance, owner)
    except AttributeError as exc:
        msg = (
            f"Computing cached property {type(instance).__name__}."
            f"{self._attrname} raised AttributeError: {exc}"
        )
        raise CachedComputationError(msg) from exc


vb.cached_property.__get__ = patched_get


class Point:
    """A user domain object."""

    def __init__(self, x: int):
        self.x = x


@rx.serializer
def serialize_point(p: Point) -> str:
    """Buggy serializer."""
    return p.label  # noqa


for tag, fn in [
    ("foreach_render", lambda: rx.foreach([Point(1)], lambda p: rx.text(p.to_string())).render()),
    ("var_create_list_str", lambda: str(rx.Var.create([Point(1)]))),
    ("custom_attrs_list", lambda: rx.box(custom_attrs={"data-p": [Point(1)]}).render()),
]:
    print(f"=== {tag} ===")
    try:
        fn()
        print("  no exception")
    except BaseException as e:  # noqa: BLE001
        tb = traceback.format_exc()
        print(f"  {type(e).__name__}: {str(e)[:180]}")
        print(f"  __cause__: {e.__cause__!r}")
        print(f"  real error 'has no attribute \\'label\\'' visible: {'has no attribute' in tb and 'label' in tb}")
        print(f"  user file serialize_point in traceback: {'serialize_point' in tb}")
    print()
