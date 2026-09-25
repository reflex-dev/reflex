"""Tests for reflex_base.vars.base state metaclass field handling."""

import dataclasses
import gc
import pickle
import threading
import traceback
import typing
import weakref
from typing import Any, ClassVar, Literal, TypeVar

import pytest
from reflex_base.constants import RouteArgType
from reflex_base.utils import serializers
from reflex_base.utils.exceptions import ReflexRuntimeError, StateValueError
from reflex_base.utils.imports import ImportVar
from reflex_base.utils.types import get_field_type
from reflex_base.vars.base import (
    FIELD_TYPE,
    GLOBAL_CACHE,
    BaseStateMeta,
    CachedVarOperation,
    EvenMoreBasicBaseState,
    Field,
    LiteralVar,
    Var,
    VarData,
    _global_vars,
    _linearize_bases,
    cached_property,
    cached_property_no_lock,
    computed_var,
    field,
    var_operation,
    var_operation_return,
)
from reflex_base.vars.number import NumberVar
from reflex_base.vars.object import ObjectVar
from reflex_base.vars.sequence import ArrayVar, StringVar
from typing_extensions import Self, TypeAliasType, TypeVarTuple, Unpack

from reflex.state import BaseState, State, _override_base_method

_MARKER_ATTR = "_marker"


def test_custom_field_attr_survives_annotated_rebuild():
    """A custom attribute on an annotated Field survives a rebuild."""
    f = field("x")
    setattr(f, _MARKER_ATTR, "tag")

    class MyState(EvenMoreBasicBaseState):
        name: str = f  # pyright: ignore[reportAssignmentType]

    rebuilt = MyState.get_fields()["name"]
    assert getattr(rebuilt, _MARKER_ATTR, None) == "tag"
    assert rebuilt.annotated_type is str


def test_custom_field_attr_survives_unannotated_rebuild():
    """A custom attribute survives an inferred-type Field rebuild."""
    f = field(0)
    setattr(f, _MARKER_ATTR, "tag")

    class MyState(EvenMoreBasicBaseState):
        count = f

    rebuilt = MyState.get_fields()["count"]
    assert getattr(rebuilt, _MARKER_ATTR, None) == "tag"
    assert rebuilt.annotated_type is int


def test_custom_field_attr_survives_unannotated_factory_rebuild():
    """A custom attribute survives a default-factory Field rebuild."""
    f = field(default_factory=list)
    setattr(f, _MARKER_ATTR, "tag")

    class MyState(EvenMoreBasicBaseState):
        items = f

    rebuilt = MyState.get_fields()["items"]
    assert getattr(rebuilt, _MARKER_ATTR, None) == "tag"
    assert rebuilt.annotated_type is Any


def test_reserved_annotation_attr_not_copied():
    """A custom `annotation` attr must not make the rebuilt Field look pydantic.

    get_field_type duck-types __fields__ entries on `.annotation`, so copying
    it would shadow the real class annotation.
    """
    f = field("x")
    f.annotation = int  # pyright: ignore[reportAttributeAccessIssue]

    class MyState(EvenMoreBasicBaseState):
        name: str = f  # pyright: ignore[reportAssignmentType]

    rebuilt = MyState.get_fields()["name"]
    assert "annotation" not in rebuilt.__dict__
    assert get_field_type(MyState, "name") is str


def test_custom_attr_is_carried_by_reference():
    """Custom attrs land on the rebuilt Field as the same objects.

    Identity is what tag consumers rely on (e.g. stateful callable markers
    must not run as clones), and any copy scheme would break it. The lock
    also guards the old failure mode directly: deep-copying carried attrs
    raised ``TypeError: cannot pickle '_thread.lock' object``.
    """

    class Check:
        def __init__(self) -> None:
            self.lock = threading.Lock()

    check = Check()
    f = field("x")
    f._check = check  # pyright: ignore[reportAttributeAccessIssue]

    class MyState(EvenMoreBasicBaseState):
        name: str = f  # pyright: ignore[reportAssignmentType]

    rebuilt = MyState.get_fields()["name"]
    assert rebuilt._check is check  # pyright: ignore[reportAttributeAccessIssue]


def _type_alias_types() -> list[type]:
    native = getattr(typing, "TypeAliasType", None)
    return (
        [TypeAliasType] if native in (None, TypeAliasType) else [TypeAliasType, native]
    )


@pytest.mark.parametrize("alias_cls", _type_alias_types())
def test_guess_type_resolves_type_alias(alias_cls: type) -> None:
    """A TypeAliasType (PEP 695 ``type`` statement) resolves to its value.

    State var annotations like ``type Key = Literal[...]`` reach guess_type as
    a TypeAliasType, which must be unwrapped instead of raising TypeError.
    """
    alias = alias_cls("ChartKey", Literal["day", "week"])

    var = Var(_js_expr="key", _var_type=alias).guess_type()
    assert isinstance(var, StringVar)
    assert var._var_type == Literal["day", "week"]

    optional_var = Var(_js_expr="key", _var_type=alias | None).guess_type()
    assert isinstance(optional_var, StringVar)


@pytest.mark.parametrize("alias_cls", _type_alias_types())
def test_guess_type_resolves_parameterized_type_alias(alias_cls: type) -> None:
    """A subscripted generic alias (``type Keys[T] = list[T]``) resolves.

    The subscription keeps the TypeAliasType as the origin, so resolution has
    to substitute the alias's type parameters into its value.
    """
    t = TypeVar("t")
    keys = alias_cls("Keys", list[t], type_params=(t,))  # pyright: ignore[reportGeneralTypeIssues]

    var = Var(_js_expr="keys", _var_type=keys[str]).guess_type()
    assert isinstance(var, ArrayVar)
    assert var._var_type == list[str]

    optional_var = Var(_js_expr="keys", _var_type=keys[str] | None).guess_type()
    assert isinstance(optional_var, ArrayVar)

    k = TypeVar("k")
    v = TypeVar("v")
    # value's __parameters__ order (v, k) differs from type_params (k, v)
    pair = alias_cls("Pair", dict[v, k], type_params=(k, v))  # pyright: ignore[reportGeneralTypeIssues]
    pair_var = Var(_js_expr="pair", _var_type=pair[str, int]).guess_type()
    assert isinstance(pair_var, ObjectVar)
    assert pair_var._var_type == dict[int, str]


@pytest.mark.parametrize("alias_cls", _type_alias_types())
def test_guess_type_resolves_variadic_type_alias(alias_cls: type) -> None:
    """A variadic alias (``type Tup[*Ts] = tuple[*Ts]``) keeps all arguments.

    The TypeVarTuple must absorb every remaining subscription argument, not
    just the one a plain positional zip would pair it with.
    """
    ts = TypeVarTuple("ts")
    tup = alias_cls("Tup", tuple[Unpack[ts]], type_params=(ts,))  # pyright: ignore[reportGeneralTypeIssues]
    var = Var(_js_expr="t", _var_type=tup[str, int]).guess_type()
    assert isinstance(var, ArrayVar)
    assert var._var_type == tuple[str, int]

    t = TypeVar("t")
    prefixed = alias_cls("Prefixed", dict[t, tuple[Unpack[ts]]], type_params=(t, ts))  # pyright: ignore[reportGeneralTypeIssues]
    prefixed_var = Var(_js_expr="p", _var_type=prefixed[str, int, float]).guess_type()
    assert isinstance(prefixed_var, ObjectVar)
    assert prefixed_var._var_type == dict[str, tuple[int, float]]

    suffixed = alias_cls("Suffixed", dict[t, tuple[Unpack[ts]]], type_params=(ts, t))  # pyright: ignore[reportGeneralTypeIssues]
    suffixed_var = Var(_js_expr="s", _var_type=suffixed[int, float, str]).guess_type()
    assert isinstance(suffixed_var, ObjectVar)
    assert suffixed_var._var_type == dict[str, tuple[int, float]]


@pytest.mark.parametrize("alias_cls", _type_alias_types())
def test_state_var_type_alias(alias_cls: type) -> None:
    """A state var annotated with a TypeAliasType compiles."""
    chart_key = alias_cls("ChartKey", Literal["day", "week"])

    class TypeAliasState(State):
        key: chart_key = "day"  # pyright: ignore[reportInvalidTypeForm]

    assert isinstance(TypeAliasState.key, StringVar)
    assert TypeAliasState.key._var_type == Literal["day", "week"]


@pytest.mark.parametrize(
    "shape",
    [
        "single",
        "diamond",
        "shared_via_two_bases",
        "base_of_a_base",
        "three_bases",
        "ancestor_listed_after_descendant",
    ],
)
def test_linearize_bases_matches_real_mro(shape: str) -> None:
    """The pre-creation linearization equals the MRO `type` builds.

    Args:
        shape: The inheritance shape to build.
    """
    a = type("A", (), {})
    b = type("B", (a,), {})
    c = type("C", (a,), {})
    d = type("D", (), {})
    bases: tuple[type, ...] = {
        "single": (b,),
        "diamond": (b, c),
        "shared_via_two_bases": (type("E", (b,), {}), type("F", (c,), {})),
        "base_of_a_base": (b, a),
        "three_bases": (b, c, d),
        # C3 keeps `a` ahead of `d` here, though `d` sits earlier in the first
        # base's own MRO
        "ancestor_listed_after_descendant": (type("G", (a, d), {}), a),
    }[shape]

    created = type("Created", bases, {})
    assert _linearize_bases(bases) == list(created.__mro__[1:])


def test_linearize_bases_without_bases() -> None:
    """A class with no bases has nothing to inherit from."""
    assert _linearize_bases(()) == []


def test_linearize_bases_compares_by_identity() -> None:
    """A metaclass defining __eq__ must not confuse the linearization."""

    class EqMeta(type):
        def __eq__(cls, other: object) -> bool:
            return True

        def __hash__(cls) -> int:
            return 1

    a = EqMeta("A", (), {})
    b = EqMeta("B", (a,), {})
    c = EqMeta("C", (a,), {})
    created = EqMeta("Created", (b, c), {})

    # `==` between these classes is always True, so compare element identities
    assert all(
        left is right
        for left, right in zip(
            _linearize_bases((b, c)), created.__mro__[1:], strict=True
        )
    )


def test_var_data_merge_collects_field_names():
    """Merging vars of one state keeps every field name, deduped and in order."""
    merged = VarData.merge(
        VarData(state="s", field_name="a"),
        VarData(state="s", field_name="b"),
        VarData(state="s", field_name="a"),
    )

    assert merged is not None
    assert dict(merged.field_dependencies) == {"s": ("a", "b")}
    # `field_name` stays the first, so existing single-field readers are intact.
    assert merged.field_name == "a"


def test_var_data_merge_keeps_field_names_of_every_state():
    """A var spanning several states keeps each state's own fields.

    Fields stay grouped by the state that owns them, so a dependency on a
    composite var tracks every field it reads rather than only those of
    whichever state happened to merge first.
    """
    merged = VarData.merge(
        VarData(state="s", field_name="a"),
        VarData(state="other", field_name="b"),
        VarData(state="s", field_name="c"),
    )

    assert merged is not None
    assert dict(merged.field_dependencies) == {"s": ("a", "c"), "other": ("b",)}
    # The fallback accessors report the first state and its first field only.
    assert merged.state == "s"
    assert merged.field_name == "a"


def test_var_data_field_dependencies_round_trip():
    """`state`/`field_name` are the shorthand for a single-field mapping."""
    assert dict(VarData(state="s", field_name="a").field_dependencies) == {"s": ("a",)}
    # A state with no named field is still recorded: many vars carry only the
    # state, for its imports and hooks, and read no field.
    assert dict(VarData(state="s").field_dependencies) == {"s": ()}
    assert dict(VarData().field_dependencies) == {}
    # The canonical form wins over the shorthand.
    assert dict(
        VarData(
            state="ignored",
            field_name="ignored",
            field_dependencies={"s": ("a",), "other": ("b",)},
        ).field_dependencies
    ) == {"s": ("a",), "other": ("b",)}


def test_var_data_field_name_reports_the_first_field():
    """`field_name` reports the first field of the first state."""
    assert VarData(field_name="a").field_name == "a"
    assert VarData(field_dependencies={"s": ("a", "b")}).field_name == "a"
    assert VarData().field_name == ""


def test_serializer_attribute_error_is_not_masked() -> None:
    """An AttributeError raised inside a serializer surfaces chained, with its own frame."""

    class Point:
        pass

    def serialize_point(value: Point) -> str:
        return value.label  # pyright: ignore[reportAttributeAccessIssue]

    serializers.serializer(serialize_point)
    try:
        with pytest.raises(ReflexRuntimeError, match=r"_cached_var_name") as exc_info:
            str(LiteralVar.create([Point()]))
    finally:
        serializers.SERIALIZERS.pop(Point)
        serializers.SERIALIZER_TYPES.pop(Point)
        serializers.get_serializer.cache_clear()
        serializers.get_serializer_type.cache_clear()
    cause = exc_info.value.__cause__
    assert isinstance(cause, AttributeError)
    assert "'label'" in str(cause)
    assert traceback.extract_tb(cause.__traceback__)[-1].name == "serialize_point"


def test_cached_var_attribute_error_is_chained() -> None:
    """An AttributeError raised in a cached var computation surfaces as the cause."""

    @dataclasses.dataclass(eq=False, frozen=True, slots=True)
    class BrokenVar(CachedVarOperation, Var):
        @cached_property_no_lock
        def _cached_var_name(self) -> str:
            return "broken"

        @cached_property_no_lock
        def _cached_get_all_var_data(self):
            msg = "the real error message"
            raise AttributeError(msg)

    with pytest.raises(ReflexRuntimeError, match="the real error message") as exc_info:
        BrokenVar(_js_expr="")._get_all_var_data()
    assert isinstance(exc_info.value.__cause__, AttributeError)
    assert str(exc_info.value.__cause__) == "the real error message"


class _CachedValue:
    """A mutable input with an explicitly resettable derived value."""

    _reflex_cache_result: object

    def __init__(self, value: str):
        """Store the input.

        Args:
            value: The value to cache.
        """
        self.value = value

    @cached_property
    def result(self) -> list[str]:
        """Return the derived value.

        Returns:
            A fresh list containing the input.
        """
        return [self.value]


def test_cached_property_identity_and_reset():
    """Local keys isolate instances and survive explicit cache resets."""
    first = _CachedValue("first")
    second = _CachedValue("second")
    result = first.result
    assert first.result is result
    assert second.result == ["second"]
    first.value = "changed"
    assert first.result is result
    GLOBAL_CACHE.clear()
    assert first.result == ["changed"]
    assert first.result is not result


def test_cached_property_pickle_does_not_reuse_another_instances_key():
    """Deserialized keys must not collide with live cache entries."""
    original = _CachedValue("original")
    assert original.result == ["original"]
    restored = pickle.loads(pickle.dumps(original))
    restored.value = "restored"
    assert restored.result == ["restored"]
    assert original.result == ["original"]


def test_cached_property_releases_entry_with_instance():
    """Destroying an instance removes its cached value."""
    value = _CachedValue("temporary")
    assert value.result == ["temporary"]
    key = value._reflex_cache_result
    reference = weakref.ref(value)
    del value
    gc.collect()
    assert reference() is None
    assert key not in GLOBAL_CACHE


def test_literal_var_dispatch_follows_later_registrations():
    """A literal class registered after a lookup wins the next lookup for its type."""

    class Coordinate:
        """A value no literal Var claims yet."""

        def __init__(self, x: int):
            """Store the coordinate.

            Args:
                x: The coordinate value.
            """
            self.x = x

    from reflex_base.utils import serializers
    from reflex_base.vars import base

    var_subclasses = len(base._var_subclasses)
    literal_subclasses = len(base._var_literal_subclasses)
    try:

        @serializers.serializer
        def serialize_coordinate(value: Coordinate) -> str:
            """Serialize a coordinate.

            Args:
                value: The coordinate.

            Returns:
                Its string form.
            """
            return f"coordinate-{value.x}"

        assert str(LiteralVar.create(Coordinate(1))) == '"coordinate-1"'

        class CoordinateVar(Var[Coordinate], python_types=Coordinate):
            """A Var holding a coordinate."""

        class LiteralCoordinateVar(LiteralVar, CoordinateVar):
            """A literal coordinate Var."""

            @classmethod
            def create(cls, value: Coordinate, _var_data=None):
                """Create the literal.

                Args:
                    value: The coordinate.
                    _var_data: Unused metadata.

                Returns:
                    A Var with the coordinate's expression.
                """
                return Var(_js_expr=f"[{value.x}]", _var_type=Coordinate)

        assert str(LiteralVar.create(Coordinate(2))) == "[2]"
    finally:
        serializers.SERIALIZERS.pop(Coordinate)
        serializers.SERIALIZER_TYPES.pop(Coordinate)
        serializers.get_serializer.cache_clear()
        serializers.get_serializer_type.cache_clear()
        del base._var_subclasses[var_subclasses:]
        del base._var_literal_subclasses[literal_subclasses:]
        base._clear_var_subclass_lookup_caches()
        base._literal_var_by_type.clear()


def _operand_with_var_data() -> NumberVar[int]:
    """Build an operand carrying imports and hooks worth losing.

    Returns:
        A number Var whose VarData has to survive into any operation built from it.
    """
    return Var(
        _js_expr="operandValue",
        _var_data=VarData(
            imports={"operand-lib": [ImportVar(tag="operandThing")]},
            hooks={"const operand = useOperand()": None},
        ),
    ).to(int)


@pytest.mark.parametrize(
    ("build", "expected_js"),
    [
        pytest.param(lambda v: v + 1, "(operandValue + 1)", id="add"),
        pytest.param(lambda v: v - 1, "(operandValue - 1)", id="subtract"),
        pytest.param(lambda v: v > 1, "(operandValue > 1)", id="greater_than"),
        pytest.param(
            lambda v: v.bool() & v.bool(),
            "pyAnd(isTrue(operandValue), () => (isTrue(operandValue)))",
            id="logical_and",
        ),
        pytest.param(lambda v: v.to_string().lower(), None, id="string_lower"),
        pytest.param(lambda v: v.to(ArrayVar).length(), None, id="array_length"),
        pytest.param(lambda v: v.to(ObjectVar).keys(), None, id="object_keys"),
        pytest.param(lambda v: (v + 1) * 2 > 3, None, id="chained"),
    ],
)
def test_var_operation_operands_do_not_register_global_vars(
    build: typing.Callable[[NumberVar[int]], Var], expected_js: str | None
) -> None:
    """Building an operation leaves the module-global var registry alone.

    Operation bodies interpolate their operands with ``!s``, which renders the
    expression directly. Interpolating them with ``{}`` instead would hash each
    operand, register it in ``_global_vars`` forever — a leak that grows with
    every operation an app builds — and emit a tag the result then has to
    regex-decode back out, all to recover VarData that ``_args`` already
    carries.

    Args:
        build: Builds the operation from an operand.
        expected_js: The expected JavaScript, when it is short enough to pin.
    """
    operand = _operand_with_var_data()

    before = len(_global_vars)
    result = build(operand)
    assert len(_global_vars) == before

    if expected_js is not None:
        assert str(result) == expected_js


def test_var_operation_rolls_up_operand_var_data() -> None:
    """An operand's imports and hooks still reach the operation it is used in.

    They arrive through ``CustomVarOperation._args`` rather than through a tag
    decoded out of the returned expression, which is what makes ``!s`` safe.
    """
    operand = _operand_with_var_data()

    var_data = (operand + 1)._get_all_var_data()

    assert var_data is not None
    assert dict(var_data.imports)["operand-lib"] == (ImportVar(tag="operandThing"),)
    assert "const operand = useOperand()" in var_data.hooks


def test_var_operation_body_created_var_still_tags() -> None:
    """A var built inside a body is not an operand and must keep its tag.

    ``_args`` only carries what was passed in, so a var the body creates itself
    reaches the operation solely through the returned expression. It therefore
    interpolates with ``{}``, and ``!s`` would silently drop its imports.
    """

    @var_operation
    def op_with_derived(value: Var):
        derived = Var(
            _js_expr="derivedHelper",
            _var_data=VarData(imports={"derived-lib": [ImportVar(tag="helper")]}),
        )
        return var_operation_return(f"({value!s} + {derived})", var_type=int)

    result = op_with_derived(Var(_js_expr="a").to(int))

    var_data = result._get_all_var_data()
    assert var_data is not None
    assert dict(var_data.imports)["derived-lib"] == (ImportVar(tag="helper"),)
    assert str(result) == "(a + derivedHelper)"


# Decorators whose function body builds a var operation's expression out of the
# function's own parameters. ``var_operation`` wraps every argument with
# ``LiteralVar.create``, so inside these bodies every parameter is a Var.
_OPERAND_BUILDER_DECORATORS = frozenset({
    "var_operation",
    "binary_number_operation",
    "comparison_operator",
})
# Plain helpers called only from such a body, mapped to the parameters the
# operation forwards its operands into. Their other parameters are ordinary
# Python values that never carried a tag to begin with.
_OPERAND_BUILDER_FUNCTIONS = {"date_compare_operation": frozenset({"lhs", "rhs"})}


def test_var_operation_bodies_interpolate_operands_with_str() -> None:
    """No operation body interpolates an operand without ``!s``.

    The rule is checked against the source rather than per operation, because
    a missed one changes no behaviour: the rendered JavaScript and the merged
    VarData come out identical, and only the leak and the cost give it away.
    A var the body creates itself is not a parameter, so it is not flagged.
    """
    import ast
    import pathlib

    from reflex_base.vars import base as base_module

    offenders: list[str] = []
    for path in sorted(pathlib.Path(base_module.__file__).parent.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            decorators = {d.id for d in node.decorator_list if isinstance(d, ast.Name)}
            if decorators & _OPERAND_BUILDER_DECORATORS:
                params = {arg.arg for arg in node.args.args}
            elif node.name in _OPERAND_BUILDER_FUNCTIONS:
                params = _OPERAND_BUILDER_FUNCTIONS[node.name]
            else:
                continue
            for joined in ast.walk(node):
                if not isinstance(joined, ast.JoinedStr):
                    continue
                for value in joined.values:
                    if (
                        isinstance(value, ast.FormattedValue)
                        and isinstance(value.value, ast.Name)
                        and value.value.id in params
                        and value.conversion != ord("s")
                    ):
                        offenders.append(
                            f"{path.name}:{value.lineno} {node.name} "
                            f"interpolates operand {value.value.id!r} without !s"
                        )

    assert not offenders, (
        "Var operation bodies must interpolate their operands with !s, which "
        "renders the expression directly; plain {} hashes the operand and "
        "registers it in _global_vars forever to recover VarData that _args "
        "already carries:\n  " + "\n  ".join(offenders)
    )


def test_var_operation_str_interpolation_matches_tagged_form() -> None:
    """``!s`` renders exactly what a tagged interpolation decodes down to.

    ``Var.__format__`` emits a tag followed by the expression, and the Var it
    is interpolated into strips the tag back off in ``__post_init__``. ``!s``
    just skips the round trip, so the two have to agree.
    """
    operand = _operand_with_var_data()

    tagged = Var(_js_expr=f"wrap({operand})").to(int)
    untagged = Var(_js_expr=f"wrap({operand!s})").to(int)

    assert str(tagged) == str(untagged) == "wrap(operandValue)"


@pytest.mark.parametrize(
    "name",
    [
        "_init_bookkeeping",
        "_get_root_state",
        "_was_touched",
        "dirty_vars",
        "get_fields",
        "get_full_name",
        "computed_vars",
        "__fields__",
        "setvar",
    ],
)
@pytest.mark.parametrize("annotated", [False, True])
def test_reserved_state_var(name: str, annotated: bool, clean_registration_context):
    """Reject framework names before state initialization can call them.

    Args:
        name: The reserved member to shadow.
        annotated: Whether to explicitly annotate the variable.
        clean_registration_context: An isolated state registry.
    """
    namespace = {"__module__": __name__, "__qualname__": "ShadowState", name: 7}
    if annotated:
        namespace["__annotations__"] = {name: int}
    with pytest.raises(StateValueError, match=name):
        type("ShadowState", (BaseState,), namespace)


def test_reserved_annotation_only(clean_registration_context):
    """Reject a reserved var even when no default is declared.

    Args:
        clean_registration_context: An isolated state registry.
    """
    with pytest.raises(StateValueError, match="_init_bookkeeping"):

        class ShadowState(BaseState):
            _init_bookkeeping: int


@pytest.mark.parametrize("state_mixin", [False, True])
def test_reserved_mixin_var(state_mixin: bool, clean_registration_context):
    """Reject collisions from both ordinary Python mixins and state mixins.

    Args:
        state_mixin: Whether the mixin subclasses BaseState.
        clean_registration_context: An isolated state registry.
    """
    with pytest.raises(StateValueError, match="_get_root_state"):
        mixin = type(
            "Mixin",
            (BaseState,) if state_mixin else (),
            {"__module__": __name__, "_get_root_state": 7},
            **({"mixin": True} if state_mixin else {}),
        )
        type("MixedState", (mixin, BaseState), {"__module__": __name__})


@pytest.mark.parametrize("name", ["_init_bookkeeping", "get_fields"])
def test_reserved_computed_var(name: str, clean_registration_context):
    """Reject computed vars that replace framework methods.

    Args:
        name: The reserved method to replace.
        clean_registration_context: An isolated state registry.
    """

    def value(self) -> int:
        """Return a constant computed value."""
        return 7

    value.__name__ = name
    with pytest.raises(StateValueError, match=name):
        type(
            "ComputedState",
            (BaseState,),
            {"__module__": __name__, name: computed_var(value)},
        )


@pytest.mark.parametrize("registration", ["var", "route", "event", "field"])
def test_dynamic_reserved_name(registration: str, clean_registration_context):
    """Reject dynamic collisions before any field or event map is changed.

    Args:
        registration: The dynamic registration path to exercise.
        clean_registration_context: An isolated state registry.
    """

    class DynamicState(BaseState):
        """State receiving a dynamic declaration."""

    fields = dict(DynamicState.get_fields())
    with pytest.raises(StateValueError, match="get_state"):
        if registration == "var":
            DynamicState.add_var("get_state", int, 7)
        elif registration == "route":
            DynamicState.setup_dynamic_args({"get_state": RouteArgType.SINGLE})
        elif registration == "event":
            DynamicState._add_event_handler("get_state", lambda self: None)
        else:
            DynamicState.add_field("get_state", LiteralVar.create(7), 7)
    assert DynamicState.get_fields() == fields
    assert "get_state" not in DynamicState.vars
    assert "get_state" not in DynamicState.event_handlers
    assert "get_state" not in DynamicState.__dict__


def test_user_vars_and_marked_override(clean_registration_context):
    """Keep normal vars, inherited vars, and explicitly marked method overrides.

    Args:
        clean_registration_context: An isolated state registry.
    """

    class Parent(BaseState):
        value: int = 1
        _backend: int = 2

    class Child(Parent):
        @_override_base_method
        def get_value(self, key: str):
            """Return a value through a supported framework override."""
            return f"override:{key}"

    parent = Parent()
    child = parent.substates[Child.get_name()]
    assert isinstance(child, Child)
    assert child.value == 1
    assert child._backend == 2
    assert child.get_value("value") == "override:value"


def test_non_state_models_keep_their_namespace():
    """Do not reserve Reflex state names on unrelated base models."""

    class Model(EvenMoreBasicBaseState):
        get_state: int = 7

    assert Model().get_state == 7


@pytest.mark.parametrize("name", ["get_fields", "_init_bookkeeping"])
@pytest.mark.parametrize("state_first", [False, True])
def test_reserved_model_mixin(name: str, state_first: bool, clean_registration_context):
    """Reject inherited model fields before the field collector sees them.

    Args:
        name: The framework name declared as a model field.
        state_first: Whether BaseState precedes the model in the MRO.
        clean_registration_context: An isolated state registry.
    """
    model = type("Model", (EvenMoreBasicBaseState,), {"__module__": __name__, name: 7})
    bases = (BaseState, model) if state_first else (model, BaseState)
    with pytest.raises(StateValueError, match=name):
        type("MixedState", bases, {"__module__": __name__})


def test_reserved_descriptor(clean_registration_context):
    """Reject a descriptor without executing its class access behavior.

    Args:
        clean_registration_context: An isolated state registry.
    """

    class Descriptor:
        def __get__(self, instance, owner):
            """Fail if validation invokes this descriptor."""
            pytest.fail("Reserved descriptor was evaluated")

    with pytest.raises(StateValueError, match="get_fields"):
        type(
            "DescriptorState",
            (BaseState,),
            {"__module__": __name__, "get_fields": Descriptor()},
        )


class _CookieMeta(BaseStateMeta):
    """A downstream-style metaclass that injects fields into the declaration."""

    def __new__(
        cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any], **kwargs
    ):
        """Add an annotated backend var before the state is constructed.

        Args:
            name: The class name.
            bases: The parent classes.
            namespace: The class namespace.
            **kwargs: Class creation keywords, e.g. `mixin`.

        Returns:
            The new state class.
        """
        namespace.setdefault("__annotations__", {})["_injected"] = str
        namespace["_injected"] = "by the metaclass"
        return super().__new__(cls, name, bases, namespace, **kwargs)


def test_state_metaclass_is_base_state_meta():
    """Keep the exported `BaseStateMeta` as the metaclass of every state."""
    assert type(BaseState) is BaseStateMeta
    assert type(State) is BaseStateMeta
    assert BaseState._reflex_state_root is BaseState
    assert State._reflex_state_root is BaseState


@pytest.mark.parametrize("mixin", [False, True])
def test_custom_state_metaclass(mixin: bool, clean_registration_context):
    """Allow a `BaseStateMeta` subclass as the metaclass of a state.

    Args:
        mixin: Whether the state is declared as a state mixin.
        clean_registration_context: An isolated state registry.
    """

    class CustomState(State, mixin=mixin, metaclass=_CookieMeta):
        value: int = 1

    assert type(CustomState) is _CookieMeta
    assert CustomState._mixin is mixin
    assert CustomState.__fields__["_injected"].default == "by the metaclass"
    assert CustomState.__fields__["value"].default == 1


def test_custom_state_metaclass_validates_reserved_names(clean_registration_context):
    """Keep rejecting reserved names declared through a custom metaclass.

    Args:
        clean_registration_context: An isolated state registry.
    """
    with pytest.raises(StateValueError, match="get_fields"):

        class ShadowState(BaseState, metaclass=_CookieMeta):
            get_fields: int = 7


def test_state_root_reserves_its_own_namespace():
    """Reserve the members of a `state_root=True` class for its whole hierarchy."""

    class Root(EvenMoreBasicBaseState, state_root=True):
        def bookkeeping(self) -> int:
            """Return a framework-style member subclasses may not shadow."""
            return 1

    class Child(Root):
        value: int = 5

    assert Child._reflex_state_root is Root
    assert Child().value == 5
    with pytest.raises(StateValueError, match="bookkeeping"):

        class ShadowMethod(Root):
            bookkeeping: int = 7

    with pytest.raises(StateValueError, match="_reflex_state_root"):
        type("ShadowMarker", (Root,), {"__module__": __name__, "_reflex_state_root": 7})


def test_state_roots_do_not_share_reserved_names():
    """Keep one root's reserved namespace out of another root's hierarchy."""

    class RootA(EvenMoreBasicBaseState, state_root=True):
        def alpha(self) -> int:
            """Return a member reserved for RootA's subclasses only."""
            return 1

    class RootB(EvenMoreBasicBaseState, state_root=True):
        def beta(self) -> int:
            """Return a member reserved for RootB's subclasses only."""
            return 2

    class A(RootA):
        beta: int = 1

    class B(RootB):
        alpha: int = 2

    assert (A().beta, B().alpha) == (1, 2)
    assert A._reflex_state_root is RootA
    assert B._reflex_state_root is RootB
    with pytest.raises(StateValueError, match="alpha"):

        class ShadowA(RootA):
            alpha: int = 3


def test_inherited_field_on_plain_model():
    """An inherited field of a model without a state tree reads from the model itself."""

    class Model(EvenMoreBasicBaseState):
        x: int = 1

    class SubModel(Model):
        pass

    model = SubModel()
    assert model.x == 1
    model.x = 2
    assert model.x == 2


def test_new_default_for_inherited_field_declares_a_field():
    """Assigning a default to an inherited field redeclares it with that default."""

    class Parent(State):
        count: int = 0

    class Child(Parent):
        count = 5

    child_field = Child.get_fields()["count"]
    assert child_field is not Parent.get_fields()["count"]
    assert child_field.default == 5
    assert child_field.outer_type_ is int
    assert "count" in Child.base_vars


class TaggedField(Field[FIELD_TYPE]):
    """A field subclass with an attribute of its own."""

    def __init__(self, *args: Any, tag: str = "", **kwargs: Any):
        """Initialize the field.

        Args:
            *args: The arguments of Field.
            tag: The tag of the field.
            **kwargs: The keyword arguments of Field.
        """
        super().__init__(*args, **kwargs)
        self.tag = tag

    def _replace(self, **kwargs: Any) -> Self:
        """Derive a field, keeping the tag.

        Args:
            **kwargs: The arguments to replace.

        Returns:
            The new field.
        """
        return super()._replace(**{"tag": self.tag, **kwargs})


def test_field_subclass_is_kept():
    """A field declared with a Field subclass stays one wherever it is copied."""

    class Parent(State):
        annotated: int = TaggedField(default=1, tag="a")  # pyright: ignore[reportAssignmentType]
        generic: TaggedField[int] = TaggedField(default=2, tag="g")
        unannotated = TaggedField(default="x", tag="u")

    class Child(Parent):
        annotated = 3

    class Mixin(State, mixin=True):
        mixed: int = TaggedField(default=4, tag="m")  # pyright: ignore[reportAssignmentType]

    class UsesMixin(Mixin, State):
        pass

    for cls, name, tag, default in (
        (Parent, "annotated", "a", 1),
        (Parent, "generic", "g", 2),
        (Parent, "unannotated", "u", "x"),
        (Child, "annotated", "a", 3),
        (UsesMixin, "mixed", "m", 4),
    ):
        declared = cls.get_fields()[name]
        assert type(declared) is TaggedField, (cls, name)
        assert declared.tag == tag
        assert declared.default_value() == default
    assert Parent.get_fields()["generic"].outer_type_ is int
    assert UsesMixin.get_fields()["mixed"] is not Mixin.get_fields()["mixed"]


def test_slot_names_are_reserved():
    """A state cannot declare a name a base keeps in a slot."""

    class Root(EvenMoreBasicBaseState, state_root=True):
        pass

    class Base(Root):
        __slots__ = ("_bookkeeping",)

    with pytest.raises(StateValueError, match="_bookkeeping"):

        class Shadow(Base):
            _bookkeeping: int = 0


def test_backend_field_is_not_type_checked():
    """Setting a backend var skips the type check, like a generic one it cannot run."""
    T = TypeVar("T")

    class Model(EvenMoreBasicBaseState):
        _value: T  # pyright: ignore[reportGeneralTypeIssues]

    model = Model()  # pyright: ignore[reportCallIssue]
    model._value = 1
    assert model._value == 1


def test_classvar_over_inherited_field_is_not_a_field():
    """A ClassVar redeclaring an inherited field stays a class attribute."""

    class Parent(State):
        count: int = 0

    class Child(Parent):
        count: ClassVar[int] = 5  # pyright: ignore[reportIncompatibleVariableOverride]

    assert Child.get_fields()["count"] is Parent.get_fields()["count"]
    assert "count" not in Child.base_vars
