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
        def _value_var(cls) -> Var[str]:
            return cls._secret  # pyright: ignore[reportReturnType]

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

        @original.var
        def _full_var(cls) -> Var:
            return cls.first  # pyright: ignore[reportReturnType]

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


def test_hybrid_property_not_evaluated_during_class_creation():
    """A hybrid property must not be evaluated while its state class is built.

    State creation introspects the class; if that resolved hybrid properties, the
    var function would run against a half-built class, and any side effect it has
    (e.g. reading user configuration) would happen far too early.
    """
    calls: list[str] = []

    class LazyState(rx.State):
        count: int = 0
        _secret: str = "hidden"

        @hybrid_property
        def doubled(self) -> int:
            return self.count * 2

        @doubled.var
        def _doubled_var(cls) -> Var[int]:
            calls.append("var")
            return cls.count * 2  # pyright: ignore[reportReturnType]

    assert calls == []
    _ = LazyState.doubled
    assert calls == ["var"]


def test_hybrid_property_var_fn_under_own_name():
    """A var function defined under its own name binds to the property's name."""

    class AliasState(rx.State):
        count: int = 0

        @hybrid_property
        def doubled(self) -> int:
            return self.count * 2

        @doubled.var
        def _doubled_var(cls) -> Var[int]:
            return cls.count * 3  # pyright: ignore[reportReturnType]

    # the alias does not linger on the class
    assert "_doubled_var" not in AliasState.__dict__
    assert AliasState(_reflex_internal_init=True).doubled == 0  # pyright: ignore[reportCallIssue]
    assert str(Var.create(AliasState.doubled)) == str(Var.create(AliasState.count * 3))


def test_hybrid_property_var_fn_may_return_none():
    """A var function returning None means the property has no frontend value."""

    class NoFrontendState(rx.State):
        count: int = 0

        @hybrid_property
        def maybe(self) -> int:
            return self.count

        @maybe.var
        def _maybe_var(cls) -> Var[int] | None:
            return None

    assert NoFrontendState.maybe is None
    assert NoFrontendState(_reflex_internal_init=True).maybe == 0  # pyright: ignore[reportCallIssue]


def test_hybrid_property_none_on_object_var_raises():
    """A hybrid property without a frontend value cannot be accessed on an object var."""
    from dataclasses import dataclass

    from reflex_base.utils.exceptions import VarAttributeError

    @dataclass
    class Info:
        a: str

        @hybrid_property
        def combined(self) -> str:
            return self.a

        @combined.var
        def _combined_var(cls) -> Var[str] | None:
            return None

    class NoneObjVarState(rx.State):
        info: Info = Info(a="a")

    with pytest.raises(VarAttributeError, match="combined"):
        _ = NoneObjVarState.info.combined


def test_hybrid_property_setter_and_deleter():
    """setter/deleter keep working like on a plain property."""
    seen: list[str] = []

    class Holder:
        def __init__(self) -> None:
            self._value = "a"

        @hybrid_property
        def value(self) -> str:
            return self._value

        @value.setter
        def _value_setter(self, new: str) -> None:
            self._value = new

        @_value_setter.deleter
        def _value_deleter(self) -> None:
            seen.append("deleted")

    holder = Holder()
    assert holder.value == "a"
    holder.value = "b"
    assert holder.value == "b"
    del holder.value
    assert seen == ["deleted"]


def test_hybrid_property_var_fn_as_classmethod():
    """A var function may be declared a classmethod, which types its first parameter."""

    class ClassmethodVarState(rx.State):
        count: int = 0

        @hybrid_property
        def doubled(self) -> int:  # pyright: ignore[reportRedeclaration]
            return self.count * 2

        @doubled.var
        @classmethod
        def doubled(cls) -> Var[int]:
            return cls.count * 4  # pyright: ignore[reportReturnType]

    assert ClassmethodVarState(_reflex_internal_init=True).doubled == 0  # pyright: ignore[reportCallIssue]
    assert str(Var.create(ClassmethodVarState.doubled)) == str(
        Var.create(ClassmethodVarState.count * 4)
    )


def test_hybrid_property_class_access_var_type_follows_getter():
    """Class-level access resolves to the var equivalent of the getter's return type."""

    class LadderState(rx.State):
        count: int = 0
        names: list[str] = []

        @hybrid_property
        def positive(self) -> bool:
            return self.count > 0

        @hybrid_property
        def doubled(self) -> int:
            return self.count * 2

        @hybrid_property
        def upper_names(self) -> list[str]:
            return [name.upper() for name in self.names]

        @upper_names.var
        @classmethod
        def _upper_names_var(cls) -> Var[list[str]]:
            return cls.names  # pyright: ignore[reportReturnType]

    # the operations these var types carry must be available on class access
    assert isinstance(LadderState.positive & True, Var)
    assert isinstance(LadderState.doubled + 1, Var)
    assert isinstance(LadderState.upper_names.length(), Var)
    # ... while the getter still serves the instance
    state = LadderState(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    state.count = 2
    state.names = ["a"]
    assert state.positive is True
    assert state.doubled == 4
    assert state.upper_names == ["A"]
