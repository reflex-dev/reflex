"""Unit tests for reflex_base.vars.hybrid_property."""

import pytest
from reflex_base.utils.exceptions import HybridPropertyError

import reflex as rx
from reflex.experimental import hybrid_property
from reflex.vars import Var


def test_hybrid_property_getter_backend_var_access_raises():
    """A hybrid property getter that reads a backend var raises when its frontend var is built."""

    class GetterBackendState(rx.State):
        name: str = "pub"
        _secret: str = "hidden"

        @hybrid_property
        def leaky(self) -> str:
            return f"{self.name}-{self._secret}"

    with pytest.raises(HybridPropertyError, match="_secret"):
        _ = GetterBackendState.leaky


def test_hybrid_property_var_fn_backend_var_access_raises():
    """A hybrid property whose custom .var function reads a backend var raises."""

    class VarFnBackendState(rx.State):
        name: str = "pub"
        _secret: str = "hidden"

        @hybrid_property
        def value(self) -> str:
            return self.name

        @value.var
        def value(cls) -> Var[str]:
            return cls._secret  # ty:ignore[invalid-return-type]

    with pytest.raises(HybridPropertyError, match="_secret"):
        _ = VarFnBackendState.value


def test_hybrid_property_frontend_var_access_ok():
    """A hybrid property reading only frontend vars builds the expected frontend var."""

    class FrontendOnlyState(rx.State):
        first: str = "a"
        last: str = "b"

        @hybrid_property
        def full(self) -> str:
            return f"{self.first} {self.last}"

    assert str(Var.create(FrontendOnlyState.full)) == str(
        Var.create(f"{FrontendOnlyState.first} {FrontendOnlyState.last}")
    )


def test_hybrid_property_var_returns_new_descriptor():
    """var() must return a new descriptor, not mutate self, so mixin inheritance is safe."""

    class Mixin:
        @hybrid_property
        def full(self) -> str:
            return ""

    original = Mixin.__dict__["full"]

    class StateA(Mixin, rx.State):
        first: str = "a"
        last: str = "b"

        @Mixin.full.var
        def full(cls) -> Var:
            return cls.first  # ty:ignore[invalid-return-type]

    class StateB(Mixin, rx.State):
        first: str = "x"
        last: str = "y"

    # var() must have produced a new object
    assert StateA.__dict__["full"] is not original
    # The mixin's descriptor must be unmodified
    assert original._var is None
    # StateB inherits the unmodified descriptor — no _var leak
    assert StateB.__dict__.get("full") is None or StateB.__dict__["full"]._var is None


def test_hybrid_property_on_object_var_not_guarded():
    """The guard is State-only; underscore fields on an object var are not affected.

    Underscore-field serialization on dataclasses/models is a separate concern, so a
    hybrid property accessed through an object var must not raise here.
    """
    from dataclasses import dataclass

    @dataclass
    class Info:
        a: str
        _internal: str = "x"

        @hybrid_property
        def combined(self) -> str:
            return f"{self.a}-{self._internal}"

    class ObjVarState(rx.State):
        info: Info = Info(a="a")

    assert isinstance(Var.create(ObjVarState.info.combined), Var)
