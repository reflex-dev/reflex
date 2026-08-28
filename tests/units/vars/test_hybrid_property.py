"""Unit tests for reflex_base.vars.hybrid_property."""

from collections.abc import Generator

import pytest
from reflex_base.registry import RegistrationContext
from reflex_base.utils.exceptions import HybridPropertyError
from typing_extensions import assert_type

import reflex as rx
from reflex.experimental import hybrid_property
from reflex.vars import Var


@pytest.fixture(autouse=True)
def _isolate_state_registrations() -> Generator[None, None, None]:
    """Discard the state classes each test declares instead of leaking them.

    Every state defined here would otherwise stay in the shared registry and be
    instantiated by every later test that builds the state tree.

    Yields:
        None.
    """
    token = RegistrationContext.set(RegistrationContext.ensure_context().fork())
    try:
        yield
    finally:
        RegistrationContext.reset(token)


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


def test_hybrid_property_var_fn_sees_state_dunders():
    """The backend-var guard forwards dunder names to the state class too."""
    seen: dict[str, str] = {}

    class DunderState(rx.State):
        name: str = "pub"
        _secret: str = "hidden"

        @hybrid_property
        def value(self) -> str:
            return self.name

        @value.var
        @classmethod
        def _value_var(cls) -> Var[str]:
            seen["name"] = cls.__name__
            seen["module"] = cls.__module__
            return cls.name  # pyright: ignore[reportReturnType]

    _ = DunderState.value
    assert seen == {"name": "DunderState", "module": DunderState.__module__}


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


def test_hybrid_property_setter_on_state():
    """setter/deleter also work on a state, whose __setattr__ guards unknown names."""

    class NameState(rx.State):
        first: str = "Jane"
        last: str = "Doe"

        @hybrid_property
        def full(self) -> str:
            return f"{self.first} {self.last}"

        @full.setter
        def _full_setter(self, value: str) -> None:
            self.first, self.last = value.split(" ", 1)

        @_full_setter.deleter
        def _full_deleter(self) -> None:
            self.first = self.last = ""

    state = NameState(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    state.full = "Ada Lovelace"  # pyright: ignore[reportAttributeAccessIssue]
    assert (state.first, state.last) == ("Ada", "Lovelace")
    assert state.full == "Ada Lovelace"
    # the assignment marks the vars the setter touched, not the property
    assert {"first", "last"} <= state.dirty_vars
    del state.full  # pyright: ignore[reportAttributeAccessIssue]
    assert (state.first, state.last) == ("", "")
    # the frontend value still comes from the getter
    assert str(Var.create(NameState.full)) == str(
        Var.create(f"{NameState.first} {NameState.last}")
    )


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


def test_hybrid_property_functional_construction():
    """A functionally constructed property binds under the assigned name."""

    def _get_val(self) -> str:
        return self._v

    def _set_val(self, new: str) -> None:
        self._v = new

    class Holder:
        def __init__(self) -> None:
            self._v = "a"

        value = hybrid_property(_get_val).setter(_set_val)

    assert "value" in Holder.__dict__
    assert "_get_val" not in Holder.__dict__
    holder = Holder()
    assert holder.value == "a"
    holder.value = "b"
    assert holder.value == "b"


def test_hybrid_property_functional_copy_keeps_original():
    """Assigning a derived copy to a new name must not touch the original."""

    def _set_val(self, new: str) -> None:
        self._v = new

    class Holder:
        def __init__(self) -> None:
            self._v = "a"

        @hybrid_property
        def a(self) -> str:
            return self._v

        b = a.setter(_set_val)

    assert "a" in Holder.__dict__
    assert "b" in Holder.__dict__
    holder = Holder()
    holder.b = "c"
    assert holder.a == "c"
    with pytest.raises(AttributeError, match="no setter"):
        holder.a = "x"  # pyright: ignore[reportAttributeAccessIssue]


def test_hybrid_property_functional_construction_then_alias_setter():
    """An alias decorator on a functionally constructed property binds under its name."""

    def _get_value(self) -> str:
        return self._v

    class Holder:
        def __init__(self) -> None:
            self._v = "a"

        value = hybrid_property(_get_value)

        @value.setter
        def _set_value(self, new: str) -> None:
            self._v = new

    assert "_get_value" not in Holder.__dict__
    assert "_set_value" not in Holder.__dict__
    holder = Holder()
    holder.value = "b"
    assert holder.value == "b"


def test_hybrid_property_functional_construction_then_redeclared_setter():
    """Redeclaring the property's name for the setter keeps that name."""

    def _get_value(self) -> str:
        return self._v

    class Holder:
        def __init__(self) -> None:
            self._v = "a"

        value = hybrid_property(_get_value)  # pyright: ignore[reportRedeclaration]

        @value.setter  # pyright: ignore[reportGeneralTypeIssues]
        def value(self, new: str) -> None:
            self._v = new

    assert "_get_value" not in Holder.__dict__
    assert "value" in Holder.__dict__
    holder = Holder()
    holder.value = "b"
    assert holder.value == "b"


def test_hybrid_property_getterless_alias_getter_decorator():
    """A getter added under an alias name binds to the getter-less property."""

    class Holder:
        value = hybrid_property()

        @value.getter
        def _get_value(self) -> str:
            return "got"

    assert "_get_value" not in Holder.__dict__
    assert Holder().value == "got"


def test_hybrid_property_getterless_getter_decorator():
    """A getter-less property accepts its getter via the decorator form."""

    class Holder:
        value = hybrid_property()

        @value.getter  # pyright: ignore[reportGeneralTypeIssues]
        def value(self) -> str:
            return "got"

    # the added getter also types the property's value
    _ = assert_type(Holder().value, str)
    assert Holder().value == "got"


def test_hybrid_property_getterless_var_only():
    """A getter-less property with only a var function works on a state."""

    class VarOnlyState(rx.State):
        count: int = 0

        maybe = hybrid_property().var(lambda owner: owner.count + 1)

    assert str(Var.create(VarOnlyState.maybe)) == str(
        Var.create(VarOnlyState.count + 1)
    )


def test_hybrid_property_unchained_setter_and_deleter():
    """setter/deleter derived from the same property (not chained) both survive."""
    seen: list[str] = []

    class Holder:
        def __init__(self) -> None:
            self._v = "a"

        @hybrid_property
        def value(self) -> str:
            return self._v

        @value.setter
        def _value_setter(self, new: str) -> None:
            self._v = new

        @value.deleter
        def _value_deleter(self) -> None:
            seen.append("deleted")

    holder = Holder()
    assert holder.value == "a"
    holder.value = "b"
    assert holder.value == "b"
    del holder.value
    assert seen == ["deleted"]


def test_hybrid_property_alias_accessors_survive_redeclared_var():
    """Aliased accessors survive a later var decorator that redeclares the name."""
    seen: list[str] = []

    class Holder:
        def __init__(self) -> None:
            self._v = "a"

        @hybrid_property
        def value(self) -> str:  # pyright: ignore[reportRedeclaration]
            return self._v

        @value.setter
        def _value_setter(self, new: str) -> None:
            self._v = new

        @value.deleter
        def _value_deleter(self) -> None:
            seen.append("deleted")

        @value.var
        @classmethod
        def value(cls) -> Var[str]:
            return Var.create("frontend")

    assert "_value_setter" not in Holder.__dict__
    assert "_value_deleter" not in Holder.__dict__
    assert Holder.__dict__["value"]._var is not None
    holder = Holder()
    assert holder.value == "a"
    holder.value = "b"
    assert holder.value == "b"
    del holder.value
    assert seen == ["deleted"]


def test_hybrid_property_alias_setter_chained_redeclared_var_removes_alias():
    """A var decorator chained off an aliased setter still removes the alias."""

    class Holder:
        def __init__(self) -> None:
            self._v = "a"

        @hybrid_property
        def value(self) -> str:  # pyright: ignore[reportRedeclaration]
            return self._v

        @value.setter
        def _value_setter(self, new: str) -> None:
            self._v = new

        @_value_setter.var
        @classmethod
        def value(cls) -> Var[str]:
            return Var.create("frontend")

    assert "_value_setter" not in Holder.__dict__
    assert Holder.__dict__["value"]._var is not None
    holder = Holder()
    holder.value = "b"
    assert holder.value == "b"


def test_hybrid_property_forked_copy_redeclared_var_keeps_its_name():
    """A copy forked under a new name keeps that name when its var redeclares it."""

    def _set_b(self, new: str) -> None:
        self._v = new

    class Holder:
        def __init__(self) -> None:
            self._v = "a"

        @hybrid_property
        def a(self) -> str:
            return self._v

        b = a.setter(_set_b)  # pyright: ignore[reportAssignmentType]

        @b.var  # pyright: ignore[reportGeneralTypeIssues]
        @classmethod
        def b(cls) -> Var[str]:
            return Var.create("frontend")

    assert "b" in Holder.__dict__
    assert Holder.__dict__["b"]._var is not None
    # The fork must not leak its accessors back onto the original.
    assert Holder.__dict__["a"]._var is None
    assert Holder.__dict__["a"].fset is None
    holder = Holder()
    holder.b = "c"
    assert holder.a == "c"
    with pytest.raises(AttributeError, match="no setter"):
        holder.a = "x"  # pyright: ignore[reportAttributeAccessIssue]


def test_hybrid_property_in_pydantic_model():
    """A hybrid property may be declared directly in a pydantic model body."""
    pytest.importorskip("pydantic")
    from pydantic import BaseModel

    class Person(BaseModel):
        first_name: str
        last_name: str

        @hybrid_property
        def full_name(self) -> str:
            return f"{self.first_name} {self.last_name}"

    assert Person(first_name="Jane", last_name="Doe").full_name == "Jane Doe"


def test_hybrid_property_backend_var_not_resolved_during_class_creation():
    """An inherited hybrid property backend var must not run during class creation."""
    calls: list[str] = []

    class HybridBase:
        @hybrid_property
        def _foo(self) -> int:
            calls.append("getter ran")
            return 1

    class GuardState(HybridBase, rx.State):
        _foo: int  # pyright: ignore[reportIncompatibleVariableOverride]

    assert calls == []
    # The annotation must not shadow the inherited descriptor with storage.
    assert "_foo" not in GuardState.backend_vars
    assert GuardState(_reflex_internal_init=True)._foo == 1  # pyright: ignore[reportCallIssue]
    assert calls == ["getter ran"]


def test_hybrid_property_inherited_annotated_name_keeps_descriptor():
    """An annotation on a name a base provides as a hybrid property stays a descriptor."""

    class HybridBase:
        @hybrid_property
        def doubled(self) -> int:
            return self.count * 2  # pyright: ignore[reportAttributeAccessIssue]

    class InheritedState(HybridBase, rx.State):
        count: int = 3
        doubled: int  # pyright: ignore[reportIncompatibleVariableOverride]

    assert "doubled" not in InheritedState.get_fields()
    assert InheritedState(_reflex_internal_init=True).doubled == 6  # pyright: ignore[reportCallIssue]
    assert str(Var.create(InheritedState.doubled)) == str(
        Var.create(InheritedState.count * 2)
    )


def test_hybrid_property_shadowed_by_closer_base_stays_a_field():
    """A base that C3 resolves ahead of the property's owner keeps its field."""

    class Shared:
        @hybrid_property
        def value(self) -> int:
            return 1

    class Plain(Shared):
        pass

    class Overriding(Shared, rx.State):
        # overrides the shared base's property with a real var
        value: int = 5  # pyright: ignore[reportIncompatibleVariableOverride, reportAssignmentType]

    # C3 order is Child, Plain, Overriding, Shared -- the field wins, not the
    # property Plain reaches through Shared.
    class Child(Plain, Overriding):
        value: int  # pyright: ignore[reportGeneralTypeIssues, reportIncompatibleVariableOverride]

    # compare identities: reflex renames state classes that collide by name
    assert Child.__mro__[:4] == (Child, Plain, Overriding, Shared)
    assert "value" in Child.get_fields()
    assert isinstance(Child.value, Var)


def test_hybrid_property_annotated_name_keeps_descriptor():
    """An annotation on the property's name must not turn it into a field."""

    class AnnotatedState(rx.State):
        count: int = 3
        doubled: int  # pyright: ignore[reportRedeclaration]

        @hybrid_property
        def doubled(self) -> int:
            return self.count * 2

    assert isinstance(AnnotatedState.__dict__["doubled"], hybrid_property)
    assert AnnotatedState(_reflex_internal_init=True).doubled == 6  # pyright: ignore[reportCallIssue]
    assert str(Var.create(AnnotatedState.doubled)) == str(
        Var.create(AnnotatedState.count * 2)
    )


def test_hybrid_property_subclass_identity_preserved():
    """Deriving via setter/deleter/var keeps the descriptor's subclass."""
    from reflex_base.vars.hybrid_property import HybridProperty

    class MyHybridProperty(HybridProperty):
        pass

    class Holder:
        def __init__(self) -> None:
            self._v = "a"

        @MyHybridProperty
        def value(self) -> str:
            return self._v

        @value.setter
        def _value_setter(self, new: str) -> None:
            self._v = new

    assert type(Holder.__dict__["value"]) is MyHybridProperty


def test_hybrid_property_abstractmethod():
    """A hybrid property over an abstractmethod keeps the class abstract."""
    import abc

    class AbstractBase(abc.ABC):
        @hybrid_property
        @abc.abstractmethod
        def name(self) -> str: ...

    class Incomplete(AbstractBase):  # pyright: ignore[reportImplicitAbstractClass]
        pass

    with pytest.raises(TypeError):
        Incomplete()  # pyright: ignore[reportAbstractUsage]

    class Complete(AbstractBase):
        @hybrid_property
        def name(self) -> str:  # pyright: ignore[reportIncompatibleVariableOverride]
            return "x"

    assert Complete().name == "x"


def test_hybrid_property_non_state_class_access_returns_descriptor():
    """Class-level access on a non-state class returns the descriptor itself."""
    from dataclasses import dataclass

    @dataclass
    class Info:
        first: str

        @hybrid_property
        def combined(self) -> str:
            return self.first

    assert Info.combined is Info.__dict__["combined"]
    assert Info(first="a").combined == "a"


def test_hybrid_property_var_fn_as_staticmethod():
    """A var function may be a staticmethod receiving the owner."""

    class StaticVarState(rx.State):
        count: int = 0

        @hybrid_property
        def maybe(self) -> int:  # pyright: ignore[reportRedeclaration]
            return self.count

        maybe = maybe.var(staticmethod(lambda owner: owner.count * 5))

    assert str(Var.create(StaticVarState.maybe)) == str(
        Var.create(StaticVarState.count * 5)
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
