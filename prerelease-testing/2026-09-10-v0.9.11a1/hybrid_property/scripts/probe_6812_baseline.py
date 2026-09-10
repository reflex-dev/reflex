"""#6812 fixes exercised directly on state instances -- run with each venv to compare.

Checks: (a) assigning to a hybrid_property / plain property from a state runs the setter,
(b) a state annotating a name a base provides as a hybrid property instantiates,
(c) a backend var annotated on the state takes the base's field() default,
(d) a raising default_factory surfaces (and when), (e) var fn not run during class creation.
"""
import sys, traceback
import reflex
print("python", sys.version.split()[0], "reflex", reflex.__file__)
import reflex as rx
from reflex.experimental import hybrid_property


def run(name, fn):
    try:
        print(f"{name}: OK ->", fn())
    except Exception as e:  # noqa: BLE001
        print(f"{name}: {type(e).__name__}: {str(e)[:200]}")


def a_hybrid_setter():
    class NameState(rx.State):
        first: str = "Jane"
        last: str = "Doe"

        @hybrid_property
        def full(self) -> str:
            return f"{self.first} {self.last}"

        @full.setter
        def _set_full(self, value: str) -> None:
            self.first, self.last = value.split(" ", 1)

    s = NameState(_reflex_internal_init=True)
    s.full = "Ada Lovelace"
    return (s.first, s.last, sorted(s.dirty_vars))


def a_plain_setter():
    class PlainState(rx.State):
        first: str = "Jane"
        last: str = "Doe"

        @property
        def full(self) -> str:
            return f"{self.first} {self.last}"

        @full.setter
        def full(self, value: str) -> None:
            self.first, self.last = value.split(" ", 1)

    s = PlainState(_reflex_internal_init=True)
    s.full = "Ada Lovelace"
    return (s.first, s.last)


def b_inherited_annotated():
    class HybridBase:
        @hybrid_property
        def doubled(self) -> int:
            return self.count * 2

    class InheritedState(HybridBase, rx.State):
        count: int = 3
        doubled: int

    s = InheritedState(_reflex_internal_init=True)
    return (s.doubled, "doubled" in InheritedState.get_fields(), str(InheritedState.doubled))


def c_backend_default():
    class WithDefault:
        _n = rx.field(default=3)
        _cache = rx.field(default_factory=lambda: {"hits": 0})

    class InheritsDefault(WithDefault, rx.State):
        _n: int
        _cache: dict

    s = InheritsDefault(_reflex_internal_init=True)
    return (InheritsDefault.backend_vars["_n"], InheritsDefault.backend_vars["_cache"], s._n, s._cache)


def d_factory_raises():
    def _boom():
        raise ValueError("factory blew up")

    class WithFailingFactory:
        _n = rx.field(default_factory=_boom)

    class FactoryState(WithFailingFactory, rx.State):
        _n: int

    return ("class created without error; backend_vars=", FactoryState.backend_vars.get("_n", "<missing>"))


def e_lazy_var_fn():
    calls = []

    class LazyState(rx.State):
        count: int = 0

        @hybrid_property
        def doubled(self) -> int:
            return self.count * 2

        @doubled.var
        def _doubled_var(cls):
            calls.append("var")
            return cls.count * 2

    after_class = list(calls)
    _ = LazyState.doubled
    return (after_class, calls)


for name, fn in [("a_hybrid_setter", a_hybrid_setter), ("a_plain_setter", a_plain_setter),
                 ("b_inherited_annotated", b_inherited_annotated), ("c_backend_default", c_backend_default),
                 ("d_factory_raises", d_factory_raises), ("e_lazy_var_fn", e_lazy_var_fn)]:
    run(name, fn)


def f_underscore_inherited_hybrid():
    calls = []

    class HybridBase:
        @hybrid_property
        def _foo(self) -> int:
            calls.append("getter ran")
            return 1

    class GuardState(HybridBase, rx.State):
        _foo: int

    after_class = list(calls)
    s = GuardState(_reflex_internal_init=True)
    return ("calls after class creation", after_class, "_foo in backend_vars", "_foo" in GuardState.backend_vars, "instance._foo", s._foo)


run("f_underscore_inherited_hybrid", f_underscore_inherited_hybrid)
