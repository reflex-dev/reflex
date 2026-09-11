"""Independent verification of the claim:

  "AttributeError raised inside a cached var computation is masked as
   'Attribute <name> not found' with no __cause__."

Cases:
  A  claim as written: CachedVarOperation subclass, AttributeError in
     _cached_get_all_var_data  (internal API)
  B  same, but raised in _cached_var_name
  C  pure USER-SPACE path, no internal subclassing: a user @rx.serializer that
     raises AttributeError, reached lazily from LiteralArrayVar._cached_var_name
  D  control: same broken serializer reached EAGERLY (not via a cached property)
  E  control: AttributeError in a plain @rx.var computed var (not a cached prop)
  F  control: a non-AttributeError (ValueError) raised in a cached var computation
"""

import dataclasses
import traceback

import reflex

assert "site-packages" in reflex.__file__ and "/envs/" in reflex.__file__, (
    reflex.__file__
)
print(f"### reflex.__file__ = {reflex.__file__}")

import reflex as rx  # noqa: E402

print(f"### reflex version = {rx.constants.Reflex.VERSION}")
print()

REAL = "the_real_problem"


def report(tag: str, fn) -> None:
    print(f"===== {tag} =====")
    try:
        out = fn()
        print(f"{tag}: NO ERROR raised -> {out!r}")
    except BaseException as e:  # noqa: BLE001
        tb = traceback.format_exc()
        cause = e.__cause__
        ctx = e.__context__
        print(f"{tag}: {type(e).__module__}.{type(e).__name__}: {e}")
        print(f"{tag}: __cause__={type(cause).__name__ if cause else None} "
              f"__context__={type(ctx).__name__ if ctx else None}")
        print(f"{tag}: real_error_visible_in_traceback={REAL in tb}")
        if REAL not in tb:
            print(f"{tag}: ---- full traceback (real cause absent) ----")
            print(tb.rstrip())
    print()


# ---------------------------------------------------------------- A / B
from reflex_base.vars.base import (  # noqa: E402
    CachedVarOperation,
    VarData,
    cached_property_no_lock,
)
from reflex_base.vars.sequence import StringVar  # noqa: E402

print(f"### cached_property_no_lock = {cached_property_no_lock!r}")
print()


@dataclasses.dataclass(eq=False, frozen=True, slots=True)
class BoomVarData(CachedVarOperation, StringVar[str]):
    """VarData computation raises AttributeError."""

    _var_value: str = ""

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        return f'"{self._var_value}"'

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        raise AttributeError(f"module 'some.module' has no attribute '{REAL}'")


@dataclasses.dataclass(eq=False, frozen=True, slots=True)
class BoomVarName(CachedVarOperation, StringVar[str]):
    """var-name computation raises AttributeError."""

    _var_value: str = ""

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        raise AttributeError(f"module 'some.module' has no attribute '{REAL}'")

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        return self._var_data


@dataclasses.dataclass(eq=False, frozen=True, slots=True)
class BoomValueError(CachedVarOperation, StringVar[str]):
    """VarData computation raises ValueError (control)."""

    _var_value: str = ""

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        return f'"{self._var_value}"'

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        raise ValueError(f"module 'some.module' has no attribute '{REAL}'")


report(
    "A_cached_get_all_var_data",
    lambda: BoomVarData(_var_value="hi", _var_type=str, _js_expr="")._get_all_var_data(),
)
report(
    "B_cached_var_name",
    lambda: str(BoomVarName(_var_value="hi", _var_type=str, _js_expr="")),
)
report(
    "F_control_ValueError",
    lambda: BoomValueError(
        _var_value="hi", _var_type=str, _js_expr=""
    )._get_all_var_data(),
)


# ---------------------------------------------------------------- C / D
class Thing:
    """A plain user object with a (buggy) serializer."""

    def __init__(self, n: int) -> None:
        self.n = n


@rx.serializer
def serialize_thing(t: Thing) -> str:
    # typical real-world bug: refers to something that does not exist
    return rx.constants.Reflex.the_real_problem  # type: ignore[attr-defined]


# C: reached lazily from LiteralArrayVar._cached_var_name
report("C_userspace_serializer_in_array_literal", lambda: str(rx.Var.create([Thing(1)])))
# C2: same through a real component render path
report(
    "C2_userspace_serializer_component_render",
    lambda: rx.text("x", custom_attrs={"data-x": rx.Var.create([Thing(1)])}).render(),
)
# D: eager control (serializer called outside any cached property)
report("D_control_eager_serializer", lambda: str(rx.Var.create(Thing(1))))


# ---------------------------------------------------------------- E
class SomeState(rx.State):
    """State with a computed var that raises AttributeError."""

    n: int = 0

    @rx.var
    def bad(self) -> str:
        return rx.constants.Reflex.the_real_problem  # type: ignore[attr-defined]


report("E_control_computed_var", lambda: SomeState().bad)
