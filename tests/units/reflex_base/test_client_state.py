"""Tests for reflex_base.client_state."""

from typing import Any

import pytest
from reflex_base.client_state import ClientStateVar, _recovered_event_arg, client_state
from reflex_base.components.client_state_context import CLIENT_STATE_APP_WRAP_PRIORITY
from reflex_base.components.memo import MEMOS
from reflex_base.constants import Dirs
from reflex_base.utils.exceptions import VarTypeError
from reflex_base.vars.base import Var, VarData
from reflex_base.vars.function import FunctionVar

import reflex as rx
from reflex.compiler import compiler


def _hook(cs: ClientStateVar) -> str:
    """Get the single hook a client state var contributes.

    Args:
        cs: The client state var.

    Returns:
        The hook source line.
    """
    hooks = list(cs._var_data.hooks)  # pyright: ignore [reportOptionalMemberAccess]
    assert len(hooks) == 1, f"expected exactly one hook, got {hooks}"
    return hooks[0]


def _app_wraps(var_data: VarData | None) -> list[tuple[int, str]]:
    """Summarize the app wraps a VarData carries.

    Args:
        var_data: The var data to inspect.

    Returns:
        A list of (priority, tag) pairs.
    """
    assert var_data is not None
    return [(priority, wrap.tag or "") for priority, wrap in var_data.app_wraps]  # pyright: ignore [reportAttributeAccessIssue]


def test_single_hook_no_useState() -> None:
    """A global var emits one useClientState hook and no raw useState/useId."""
    cs = client_state("counter", default=0)
    hook = _hook(cs)
    assert (
        hook
        == 'const [counterRxClientState, setCounter] = useClientState(0, "counter")'
    )
    assert "useState(" not in hook
    assert "useId" not in hook
    assert "refs[" not in hook


@pytest.mark.parametrize("global_ref", [True, False])
def test_omitted_default_emits_valid_javascript(global_ref: bool) -> None:
    """No default must still emit a syntactically valid hook call.

    Regression: an empty default expression rendered as
    ``useClientState(, "name")`` once the store name became a second argument,
    which is a syntax error that breaks the whole page build.
    """
    cs = client_state("counter", global_ref=global_ref)
    hook = _hook(cs)
    assert "(," not in hook
    expected = 'undefined, "counter"' if global_ref else "undefined"
    assert (
        hook == f"const [counterRxClientState, setCounter] = useClientState({expected})"
    )


def test_local_var_omits_store_name() -> None:
    """A ``global_ref=False`` var gets no name, so its slot stays private."""
    cs = client_state("copied", default=False, global_ref=False)
    assert _hook(cs) == "const [copiedRxClientState, setCopied] = useClientState(false)"


def test_hook_imports_use_client_state() -> None:
    """The hook carries the useClientState import."""
    imports = dict(cs_imports := client_state("x", default=0)._var_data.imports)  # pyright: ignore [reportOptionalMemberAccess]
    assert cs_imports is not None
    tags = {i.tag for i in imports[f"$/{Dirs.CLIENT_STATE_PATH}"]}
    assert tags == {"useClientState"}


@pytest.mark.parametrize("global_ref", [True, False])
def test_provider_app_wrap_declared(global_ref: bool) -> None:
    """The provider is requested in both modes; the hook always uses context."""
    cs = client_state("x", default=0, global_ref=global_ref)
    assert _app_wraps(cs._var_data) == [
        (CLIENT_STATE_APP_WRAP_PRIORITY, "ClientStateProvider")
    ]


def test_two_vars_dedupe_to_one_provider() -> None:
    """Two client state vars must not conflict over the app-wrap slot."""
    from reflex_base.vars.base import insert_app_wraps

    target: dict[tuple[int, str], Any] = {}
    for name in ("a", "b"):
        cs = client_state(name, default=0)
        insert_app_wraps(target, cs._var_data.app_wraps)  # pyright: ignore [reportOptionalMemberAccess]
    assert list(target) == [(CLIENT_STATE_APP_WRAP_PRIORITY, "ClientStateProvider")]


@pytest.mark.parametrize("global_ref", [True, False])
def test_value_is_marked_identifier(global_ref: bool) -> None:
    """``value`` renders the marked local binding in both modes."""
    cs = client_state("counter", default=0, global_ref=global_ref)
    assert str(cs.value) == "counterRxClientState"


def test_set_bare_is_event_chain() -> None:
    """``set`` renders the bare setter and is usable as an event trigger value."""
    from reflex_base.event import EventChain

    cs = client_state("counter", default=0)
    assert str(cs.set) == "setCounter"
    assert cs.set._var_type is EventChain


def test_set_bound_value() -> None:
    """Calling ``set`` binds a value in a zero-arg wrapper."""
    cs = client_state("counter", default=0)
    assert str(cs.set(42)) == "(() => (setCounter(42)))"


def test_set_carries_hook_import_and_app_wrap() -> None:
    """The setter must drag in its own hook, import and provider."""
    cs = client_state("counter", default=0)
    for setter in (cs.set, cs.set(42)):
        var_data = setter._get_all_var_data()
        assert var_data is not None
        assert any("useClientState" in hook for hook in var_data.hooks)
        assert f"$/{Dirs.CLIENT_STATE_PATH}" in dict(var_data.imports)
        assert _app_wraps(var_data) == [
            (CLIENT_STATE_APP_WRAP_PRIORITY, "ClientStateProvider")
        ]


@pytest.mark.parametrize(
    ("default", "fn", "expected"),
    [
        (
            0,
            lambda v: v + 1,
            "(() => (setX(((prev{n}RxClientState) => (prev{n}RxClientState + 1)))))",
        ),
        (
            False,
            lambda v: ~v,  # noqa: FURB118 - a lambda is what is under test
            "(() => (setX(((prev{n}RxClientState) => !(prev{n}RxClientState)))))",
        ),
        (
            "",
            lambda v: v.upper(),
            "(() => (setX(((prev{n}RxClientState) => prev{n}RxClientState.toUpperCase()))))",
        ),
    ],
)
def test_set_functional_updater_is_typed(default: Any, fn: Any, expected: str) -> None:
    """A lambda is traced against a placeholder typed like the var."""
    cs = client_state("x", default=default)
    rendered = str(cs.set(fn))
    # The placeholder counter is process-global; recover it from the output.
    n = rendered.split("prev", 1)[1].split("RxClientState", 1)[0]
    assert rendered == expected.format(n=n)


def test_set_zero_arg_callable_is_plain_value() -> None:
    """A zero-argument callable is treated as the value, not an updater."""
    cs = client_state("x", default=0)
    assert str(cs.set(lambda: 7)) == "(() => (setX(7)))"


def test_set_rejects_multi_arg_callable() -> None:
    """An updater may only take the current value."""
    cs = client_state("x", default=0)
    with pytest.raises(VarTypeError):
        cs.set(lambda a, b: a + b)  # pyright: ignore [reportCallIssue]  # noqa: FURB118 - a lambda is what is under test


def test_set_passes_function_var_through() -> None:
    """A FunctionVar is passed straight through as a runtime updater."""
    cs = client_state("x", default=0)
    updater = Var("(p) => p + 1").to(FunctionVar)
    assert str(cs.set(updater)) == "(() => (setX((p) => p + 1)))"


def test_set_declares_event_arg() -> None:
    """A value referencing an event arg makes the wrapper declare it."""
    cs = client_state("x", default="")
    assert (
        str(cs.set(Var('_e["target"]["value"]')))
        == '((_e) => (setX(_e["target"]["value"])))'
    )


def test_set_declares_event_arg_in_compound_expression() -> None:
    """Only the event arg is declared, not the whole expression."""
    cs = client_state("x", default="")
    assert (
        str(cs.set(Var('_e["target"]["value"] + "!"')))
        == '((_e) => (setX(_e["target"]["value"] + "!")))'
    )


def test_underscore_named_var_is_not_mistaken_for_event_arg() -> None:
    """A marked identifier is an in-scope binding, never a trigger parameter."""
    private = client_state("_private", default="")
    other = client_state("other", default="")
    assert str(other.set(private.value)) == "(() => (setOther(_privateRxClientState)))"


@pytest.mark.parametrize(
    ("value_str", "expected"),
    [
        ('_e["target"]["value"]', "_e"),
        ("_e", "_e"),
        ('_e["a"] + "b"', "_e"),
        ("_privateRxClientState", None),
        ("valueRxMemo", None),
        ("counterRxClientState", None),
        ("42", None),
        ('"literal"', None),
    ],
)
def test_recovered_event_arg(value_str: str, expected: str | None) -> None:
    """Event args are recovered; marked in-scope identifiers are not."""
    assert _recovered_event_arg(value_str) == expected


@pytest.mark.parametrize(
    "reserved",
    [
        "class",
        "const",
        "let",
        "var",
        "function",
        "return",
        "new",
        "delete",
        "default",
        "typeof",
        "await",
        "if",
        "for",
    ],
)
def test_reserved_words_are_safe(reserved: str) -> None:
    """A JS reserved word is a legal name; the marker keeps the codegen valid."""
    cs = client_state(reserved, default=1)
    hook = _hook(cs)
    assert hook.startswith(f"const [{reserved}RxClientState, ")
    # The store key stays the bare word so the backend can still address it.
    assert f'"{reserved}"' in hook
    assert cs._state_name == reserved


def test_camel_case_names_get_distinct_setters() -> None:
    """``myVar`` and ``myvar`` must not collapse onto one setter binding."""
    assert client_state("myVar")._setter_name != client_state("myvar")._setter_name


def test_var_name_rejects_var() -> None:
    """A Var name would only exist at runtime, so it is rejected."""
    with pytest.raises(ValueError, match="not a Var"):
        client_state(Var("dynamic"))  # pyright: ignore [reportArgumentType]


@pytest.mark.parametrize("bad", ["1foo", "my-name", "a b", "", "a.b"])
def test_var_name_must_be_identifier(bad: str) -> None:
    """The name is emitted as a JS identifier, so it has to be one."""
    with pytest.raises(ValueError, match="identifier"):
        client_state(bad)


def test_generated_names_are_sequential_and_distinct() -> None:
    """Unnamed vars get distinct, counter-derived names."""
    names = [client_state()._state_name for _ in range(3)]
    assert len(set(names)) == 3
    assert all(name.startswith("cs") for name in names)
    numbers = [int(name.removeprefix("cs")) for name in names]
    assert numbers == sorted(numbers)


def test_generated_names_unaffected_by_unrelated_var_names() -> None:
    """An unrelated placeholder draw must not shift the client state sequence."""
    from reflex_base.vars.base import get_unique_variable_name

    before = int(client_state()._state_name.removeprefix("cs"))
    get_unique_variable_name()
    rx.Var.create([1, 2, 3]).to(list).map(lambda x: x)  # pyright: ignore [reportAttributeAccessIssue]
    after = int(client_state()._state_name.removeprefix("cs"))
    assert after == before + 1


def test_push_builds_wire_event() -> None:
    """``push`` sends a first-class client-state event, not an eval'd script."""
    cs = client_state("counter", default=0)
    spec = cs.push(5)
    assert spec.handler.fn.__qualname__ == "_client_state_set"
    assert {str(k): str(v) for k, v in spec.args} == {
        "var_name": '"counter"',
        "value": "5",
    }


def test_retrieve_builds_wire_event() -> None:
    """``retrieve`` sends a first-class client-state event with a callback slot."""
    cs = client_state("counter", default=0)
    args = {str(k): str(v) for k, v in cs.retrieve().args}
    assert cs.retrieve().handler.fn.__qualname__ == "_client_state_get"
    assert args["var_name"] == '"counter"'
    assert "callback" in args


def test_global_accessors_render_module_functions() -> None:
    """The escape hatch reads and writes through the module-level functions."""
    cs = client_state("counter", default=0)
    assert str(cs.global_value) == 'getClientState("counter")'
    assert str(cs.global_set) == '((value) => setClientState("counter", value))'


def test_global_accessors_carry_no_hook() -> None:
    """The escape hatch must work in any scope, so it drags in no hook."""
    cs = client_state("counter", default=0)
    for accessor in (cs.global_value, cs.global_set):
        var_data = accessor._get_all_var_data()
        assert var_data is not None
        assert not var_data.hooks
        assert f"$/{Dirs.CLIENT_STATE_PATH}" in dict(var_data.imports)
        assert _app_wraps(var_data) == [
            (CLIENT_STATE_APP_WRAP_PRIORITY, "ClientStateProvider")
        ]


@pytest.mark.parametrize(
    "accessor",
    ["push", "retrieve", "global_value", "global_set"],
)
def test_name_addressed_paths_require_global(accessor: str) -> None:
    """An anonymous slot has no name, so nothing can address it."""
    cs = client_state("x", default=0, global_ref=False)
    with pytest.raises(ValueError, match="must be global"):
        if accessor == "push":
            cs.push(1)
        elif accessor == "retrieve":
            cs.retrieve()
        else:
            getattr(cs, accessor)


def test_set_value_delegates_and_deprecates(capsys: pytest.CaptureFixture) -> None:
    """``set_value`` still works, and says to use ``set``."""
    cs = client_state("counter", default=0)
    assert str(cs.set_value(42)) == str(cs.set(42))
    assert "set_value" in capsys.readouterr().out


def test_var_renders_as_null() -> None:
    """The var object itself renders as null so it can sit in a component tree."""
    assert str(client_state("x", default=0)) == "null"


def test_acceptance_throttle_controlled_input_compiles() -> None:
    """A memo composing local client state, `.set` bare and bound, and chains.

    This is the target ergonomics for the promoted API: two unnamed local vars
    in one component, `.set` attached bare to a trigger and called with a memo
    prop Var, and both forms mixed in one event-chain list.
    """

    @rx.memo
    def debounce_controlled_input(
        value: rx.Var[str],
        on_change: rx.EventHandler,
        debounce_ms: rx.Var[int],
        rest: rx.RestProp,
    ) -> rx.Component:
        lc_var = rx.client_state(global_ref=False)
        lc_last_var = rx.client_state(global_ref=False)
        return rx.el.input(
            rest,
            rx.cond(
                value != lc_var.value,
                rx.fragment(),
            ),
            rx.fragment(
                key=value,
                on_mount=[lc_var.set(value), lc_last_var.set(value)],
            ),
            value=lc_var.value,
            on_change=[lc_last_var.set(lc_var.value), lc_var.set],
        )

    component = debounce_controlled_input(
        value="hello", on_change=rx.noop(), debounce_ms=200, class_name="x"
    )
    assert component.render()

    definition = MEMOS["DebounceControlledInput", __name__]
    files, _ = compiler.compile_memo_components((definition,))
    code = "\n".join(c for _, c in files)

    hook_lines = [
        line.strip() for line in code.splitlines() if "useClientState" in line
    ]
    declarations = [line for line in hook_lines if line.startswith("const [")]
    assert len(declarations) == 2, (
        f"expected one hook per local var, got {declarations}"
    )
    # Distinct bindings, and neither is registered under a shared store name
    # (a named var would pass the name as a second, string, argument).
    assert len(set(declarations)) == 2
    assert all("useClientState(undefined)" in line for line in declarations)
    assert 'from "$/utils/client_state"' in code


def test_set_binds_memo_prop_var_without_declaring_an_arg() -> None:
    """A memo prop is an in-scope binding, so the wrapper takes no parameter."""
    captured: dict[str, rx.Var] = {}

    @rx.memo
    def comp(value: rx.Var[str]) -> rx.Component:
        captured["value"] = value
        return rx.el.input(value=value)

    comp(value="x")
    cs = rx.client_state("target", default="")
    assert str(cs.set(captured["value"])) == "(() => (setTarget(valueRxMemo)))"


def test_set_with_no_argument_is_the_bare_setter() -> None:
    """``cs.set()`` is the same forwarding setter as ``cs.set``."""
    cs = client_state("counter", default=0)
    assert str(cs.set()) == str(cs.set) == "setCounter"


def test_hash_distinguishes_vars() -> None:
    """Vars are hashable and distinct names hash differently."""
    a = client_state("a", default=0)
    b = client_state("b", default=0)
    assert hash(a) != hash(b)
    assert len({a, b, a}) == 2


def test_var_name_rejects_non_string() -> None:
    """A non-string, non-Var name is rejected."""
    with pytest.raises(ValueError, match="must be a string"):
        client_state(5)  # pyright: ignore [reportArgumentType]


def test_var_default_is_used_directly() -> None:
    """A Var default is embedded as-is and sets the var's type."""
    cs = client_state("x", default=Var("someExpr").to(int))
    assert "useClientState(someExpr" in _hook(cs)
    assert cs._var_type is int


def test_retrieve_with_callback_serializes_the_handler() -> None:
    """``retrieve(callback)`` embeds the queued-events callback in the payload."""

    class RetrieveState(rx.State):
        value: str = ""

        def got(self, value: str):
            self.value = value

    cs = client_state("counter", default=0)
    args = {str(k): str(v) for k, v in cs.retrieve(RetrieveState.got).args}
    assert args["var_name"] == '"counter"'
    assert "queueEvents" in args["callback"]
    assert "got" in args["callback"]


def test_push_plain_value_uses_json_payload() -> None:
    """A concrete value crosses the wire as JSON, not as JS source."""
    from reflex_base.event import fix_events

    cs = client_state("counter", default=0)
    event = fix_events([cs.push({"a": 1})], token="tok")[0]
    assert event.name.endswith("_client_state_set")
    assert event.payload == {"var_name": "counter", "value": {"a": 1}}


def test_push_var_is_evaluated_on_the_client() -> None:
    """A Var is a client-side expression, so it must not be sent as its text.

    A JSON payload would deliver the literal source (``"Date.now()"``), so a Var
    keeps the evaluated path, reaching the store through ``refs``.
    """
    from reflex_base.event import fix_events

    cs = client_state("counter", default=0)
    event = fix_events([cs.push(Var("Date.now()"))], token="tok")[0]
    assert event.name.endswith("_call_function")
    assert 'refs["__client_state"].set("counter", Date.now())' in str(
        event.payload["function"]
    )


def test_retrieve_callback_runs_even_without_a_store() -> None:
    """The runtime must call back with undefined rather than never resuming.

    Asserted against the shipped ``state.js`` because a handler awaiting
    ``retrieve`` would otherwise hang forever when no provider is mounted.
    """
    from pathlib import Path

    import reflex_base

    state_js = (
        Path(reflex_base.__file__).parent / ".templates" / "web" / "utils" / "state.js"
    ).read_text()
    branch = state_js.split('event.name == "_client_state_get"')[1].split("return;")[0]
    assert "applyResultCallback" in branch
    # Optional chaining rather than an early return, so a missing store still
    # reaches the callback with undefined.
    assert "store?.get(" in branch
