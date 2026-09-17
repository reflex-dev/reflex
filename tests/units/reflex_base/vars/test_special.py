"""Tests for reflex_base.vars.special hook-backed vars."""

from collections.abc import Callable
from typing import Any, TypedDict

import pytest
from reflex_base.components.component import Component
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData
from reflex_base.vars.function import FunctionVar
from reflex_base.vars.number import BooleanVar, NumberVar
from reflex_base.vars.object import ObjectVar
from reflex_base.vars.sequence import StringVar
from reflex_base.vars.special import (
    const,
    const_fields,
    const_unpack,
    hook_fn,
    use_hook_var,
    use_id,
)


class HookComponent(Component):
    """A minimal component for asserting hook var hoisting."""

    library = "test-lib"

    tag = "HookComponent"


class DropzoneState(TypedDict):
    """The shape returned by a fictional useDropzone hook."""

    getRootProps: dict[str, Any]
    isDragActive: bool


def hooks_of(var: Var) -> tuple[str, ...]:
    """Get the hook statements a var carries.

    Args:
        var: The var to inspect.

    Returns:
        The hook statements.
    """
    var_data = var._get_all_var_data()
    assert var_data is not None
    return var_data.hooks


def alias_of(var: Var, library: str) -> str:
    """Get the single import alias a var pulls from a library.

    Args:
        var: The var to inspect.
        library: The library the import comes from.

    Returns:
        The alias the hook is imported under.
    """
    var_data = var._get_all_var_data()
    assert var_data is not None
    imports = dict(var_data.imports)[library]
    assert len(imports) == 1
    alias = imports[0].alias
    assert alias is not None
    return alias


def test_const_binds_to_unique_name():
    """The value is bound to a fresh name, and the declaration comes along."""
    v = const(Var("useThing()"))
    assert hooks_of(v) == (f"const {v!s} = useThing();",)
    assert str(v) != "useThing()"


def test_const_uses_given_name_verbatim():
    """A supplied name is used exactly, with no unique suffix."""
    v = const(Var("useThing()"), name="myThing")
    assert str(v) == "myThing"
    assert hooks_of(v) == ("const myThing = useThing();",)


def test_const_names_are_unique_by_default():
    """Each unnamed call binds to a fresh variable name."""
    assert len({str(const(Var("useThing()"))) for _ in range(5)}) == 5


def test_const_same_name_and_value_dedupes_in_component():
    """Identical declarations collapse into one hook in a component."""
    first = const(Var("useThing()"), name="shared")
    second = const(Var("useThing()"), name="shared")
    comp = HookComponent.create(id=first, title=second)
    assert list(comp._get_all_hooks()) == ["const shared = useThing();"]


def test_const_preserves_var_type():
    """The binding is typed as, and downcast to, the value's type."""
    v = const(Var("useCount()", _var_type=int))
    assert isinstance(v, NumberVar)
    assert v._var_type is int


def test_const_carries_value_var_data_first():
    """The value's own hooks are declared before the statement using them."""
    inner = const(Var("useThing()"), name="inner")
    outer = const(inner, name="outer")
    assert hooks_of(outer) == (
        "const inner = useThing();",
        "const outer = inner;",
    )


def test_const_unwraps_call_parentheses():
    """A call operation is assigned without its embedding parentheses."""
    v = const(hook_fn("some-lib", "useThing").call(), name="thing")
    alias = alias_of(v, "some-lib")
    assert hooks_of(v) == (f"const thing = {alias}();",)


def test_const_unpack_binds_elements_with_types():
    """Array destructuring types each binding by its index."""
    value = Var("useState(0)", _var_type=tuple[int, Callable])
    count, set_count = const_unpack(value, 2, names=("count", "setCount"))
    assert hooks_of(count) == ("const [count, setCount] = useState(0);",)
    assert isinstance(count, NumberVar)
    assert count._var_type is int
    assert set_count._var_type is Callable
    assert isinstance(set_count.to(FunctionVar), FunctionVar)


def test_const_unpack_generates_names():
    """Unnamed elements bind to fresh unique names."""
    first, second = const_unpack(Var("pair()", _var_type=tuple[int, str]), 2)
    assert str(first) != str(second)
    assert hooks_of(first) == (f"const [{first!s}, {second!s}] = pair();",)


def test_const_unpack_skips_holes():
    """A None name leaves the slot empty and returns no Var for it."""
    value = Var("useState(0)", _var_type=tuple[int, Callable])
    (set_count,) = const_unpack(value, 2, names=(None, "setCount"))
    assert str(set_count) == "setCount"
    assert hooks_of(set_count) == ("const [, setCount] = useState(0);",)


def test_const_unpack_rest_element():
    """A rest element binds the remaining items and is typed by slicing."""
    value = Var("triple()", _var_type=tuple[int, str, bool])
    first, others = const_unpack(value, 1, names=("first",), rest="others")
    assert hooks_of(first) == ("const [first, ...others] = triple();",)
    assert others._var_type == tuple[str, bool]


def test_const_unpack_rest_of_sequence_keeps_type():
    """Resting over a homogeneous sequence keeps the sequence type."""
    _, others = const_unpack(Var("items()", _var_type=list[str]), 1, rest=True)
    assert others._var_type == list[str]


def test_const_unpack_rejects_count_beyond_tuple():
    """Unpacking more elements than a fixed tuple has is an error."""
    value = Var("useState(0)", _var_type=tuple[int, Callable])
    with pytest.raises(ValueError, match="Cannot unpack 3 elements"):
        const_unpack(value, 3)


def test_const_unpack_rejects_mismatched_names():
    """The number of names must match the number of elements."""
    with pytest.raises(ValueError, match="2 names for 3 elements"):
        const_unpack(Var("items()"), 3, names=("a", "b"))


def test_const_fields_renames_and_types_fields():
    """Object destructuring types each binding by its field."""
    value = Var("useDropzone(opts)", _var_type=DropzoneState)
    root, drag = const_fields(
        value, "getRootProps", "isDragActive", names=("rootProps", "dragActive")
    )
    assert hooks_of(root) == (
        (
            "const { getRootProps: rootProps, isDragActive: dragActive } "
            "= useDropzone(opts);"
        ),
    )
    assert isinstance(root, ObjectVar)
    assert isinstance(drag, BooleanVar)
    assert drag._var_type is bool


def test_const_fields_uses_shorthand_for_matching_name():
    """Binding a field to its own name renders JS shorthand."""
    value = Var("useContext(ColorModeContext)", _var_type=dict[str, str])
    (resolved,) = const_fields(value, "resolvedColorMode", names=("resolvedColorMode",))
    assert hooks_of(resolved) == (
        "const { resolvedColorMode } = useContext(ColorModeContext);",
    )


def test_const_fields_quotes_non_identifier_keys():
    """A field that is not a bare identifier is quoted as an object key."""
    (value,) = const_fields(Var("o", _var_type=dict[str, int]), "data-foo")
    assert hooks_of(value) == (f'const {{ "data-foo": {value!s} }} = o;',)


def test_const_fields_rest_element():
    """A rest element binds the remaining fields."""
    value = Var("initOptions", _var_type=dict[str, Any])
    app_id, options = const_fields(
        value, "appId", names=("appId",), rest="updateOptions"
    )
    assert hooks_of(app_id) == ("const { appId, ...updateOptions } = initOptions;",)
    assert str(options) == "updateOptions"


def test_const_fields_rejects_unknown_field():
    """Destructuring a field a typed object does not declare is an error."""
    value = Var("useDropzone(opts)", _var_type=DropzoneState)
    with pytest.raises(Exception, match="has no attribute 'nope'"):
        const_fields(value, "nope")


def test_const_fields_resolves_method_named_field():
    """A field named like an ObjectVar method resolves as a field."""
    (keys,) = const_fields(Var("o", _var_type=dict[str, int]), "keys")
    assert keys._var_type is int
    assert hooks_of(keys) == (f"const {{ keys: {keys!s} }} = o;",)


def test_hook_fn_imports_under_alias():
    """The hook is imported under a unique alias and is callable."""
    fn = hook_fn("some-lib", "useThing")
    call = fn.call()
    alias = alias_of(call, "some-lib")
    assert alias.startswith("useThing_")
    var_data = call._get_all_var_data()
    assert var_data is not None
    assert var_data.imports == (
        ("some-lib", (ImportVar(tag="useThing", alias=alias),)),
    )


def test_hook_fn_return_type_flows_through_call():
    """The declared return type reaches the called value."""
    assert hook_fn("some-lib", "useCount", returns=int).call()._var_type is int


def test_use_hook_var_var_data():
    """The hook statement and its import are carried in VarData."""
    v = use_hook_var(library="some-lib", hook="useThing")
    assert v._var_type is Any
    alias = alias_of(v, "some-lib")
    assert hooks_of(v) == (f"const {v!s} = {alias}();",)
    var_data = v._get_all_var_data()
    assert var_data is not None
    assert var_data.imports == (
        ("some-lib", (ImportVar(tag="useThing", alias=alias),)),
    )


def test_use_hook_var_guesses_var_type():
    """The returned Var is downcast to the class matching _var_type."""
    count = use_hook_var(library="some-lib", hook="useCount", _var_type=int)
    assert isinstance(count, NumberVar)
    assert count._var_type is int

    maybe = use_hook_var(library="some-lib", hook="useMaybe", _var_type=int | None)
    assert maybe._var_type == (int | None)


def test_use_hook_var_names_are_unique():
    """Each call binds the hook value to a fresh variable name."""
    names = {str(use_hook_var(library="some-lib", hook="useThing")) for _ in range(5)}
    assert len(names) == 5


def test_use_hook_var_forwards_arguments():
    """Positional arguments are passed to the hook call."""
    ctx = Var("SomeContext")
    v = use_hook_var("react", "useContext", ctx)
    alias = alias_of(v, "react")
    assert hooks_of(v) == (f"const {v!s} = {alias}(SomeContext);",)


def test_use_hook_var_rejects_positional_var_type():
    """A type passed positionally is rejected rather than rendered as an arg."""
    with pytest.raises(TypeError, match="`_var_type=`"):
        use_hook_var("some-lib", "useThing", int)
    with pytest.raises(TypeError, match="`_var_type=`"):
        use_hook_var("some-lib", "useThing", int | None)


def test_same_named_hook_imports_are_aliased():
    """Same-named hooks from different libraries do not collide in JS imports."""
    first = use_hook_var(library="first-lib", hook="useThing")
    second = use_hook_var(library="second-lib", hook="useThing")
    assert alias_of(first, "first-lib") != alias_of(second, "second-lib")


def test_use_id():
    """use_id returns a str Var bound to React's useId hook."""
    v = use_id()
    assert isinstance(v, StringVar)
    assert v._var_type is str
    alias = alias_of(v, "react")
    assert hooks_of(v) == (f"const {v!s} = {alias}();",)


def test_hook_var_hoisted_into_component():
    """A component using a hook var renders the hook and pulls its import."""
    v = use_id()
    alias = alias_of(v, "react")
    comp = HookComponent.create(id=v)
    assert f"const {v!s} = {alias}();" in comp._get_all_hooks()
    assert ImportVar(tag="useId", alias=alias) in comp._get_all_imports()["react"]
    assert comp.render()["props"] == [f"id:{v!s}"]


def test_destructured_vars_hoisted_once_into_component():
    """Several bindings from one statement emit that statement once."""
    value = Var(
        "useDropzone(opts)",
        _var_type=DropzoneState,
        _var_data=VarData(imports={"react-dropzone": "useDropzone"}),
    )
    root, drag = const_fields(
        value, "getRootProps", "isDragActive", names=("rootProps", "dragActive")
    )
    comp = HookComponent.create(id=root, title=drag)
    assert list(comp._get_all_hooks()) == [
        (
            "const { getRootProps: rootProps, isDragActive: dragActive } "
            "= useDropzone(opts);"
        )
    ]
