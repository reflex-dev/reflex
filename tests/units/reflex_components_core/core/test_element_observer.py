import re

import pytest
from reflex_base.components.memoize_helpers import is_snapshot_boundary
from reflex_base.plugins import CompileContext, CompilerHooks, PageContext
from reflex_base.vars import special
from reflex_base.vars.base import Var
from reflex_components_core.base.bare import Bare
from reflex_components_core.core.element_observer import ElementObserver

import reflex as rx
from reflex.compiler import compiler
from reflex.compiler.plugins import default_page_plugins


def _code(*lines: str) -> str:
    """Join the lines of compiled code.

    Args:
        lines: The lines.

    Returns:
        The code.
    """
    return "\n".join(lines)


def test_element_observer_reports_to_its_handlers_with_its_options():
    """The hook gets the observed id, a handler per trigger and the options set."""
    height = rx.client_state(0.0, name="height")
    visible = rx.client_state(False, name="visible")
    observer = ElementObserver.create(
        target="box",
        on_resize=lambda width, h: height.set(h),
        on_intersect=visible.set,
        threshold=[0, 1],
        root_margin="-10px",
        layout=True,
        disabled=visible.value,
    )

    assert [str(hook) for hook in observer.add_hooks()] == [
        (
            'useElementObserver("box", '
            '({ ["onResize"] : ((_ev_0, _ev_1) => (((_ev_0, _ev_1) => '
            "(heightRxClientStateSet(_ev_1)))(_ev_0, _ev_1))), "
            '["onIntersect"] : ((_ev_0, _ev_1) => (((...args) => '
            "(visibleRxClientStateSet(_ev_0, _ev_1, ...args)))"
            "(_ev_0, _ev_1))) }), "
            '({ ["layout"] : true, ["disabled"] : visibleRxClientState, '
            '["threshold"] : [0, 1], ["rootMargin"] : "-10px" }));'
        )
    ]
    assert observer.render() == {"name": "Fragment", "props": [], "children": []}
    assert observer._get_imports()["$/utils/helpers/element_observer"] == [
        rx.ImportVar(tag="useElementObserver", is_default=True)
    ]


def test_element_observer_reports_positions_and_ended_transitions():
    """on_move receives the position, on_transition_end the property name."""
    top = rx.client_state(0.0, name="top")
    done = rx.client_state(False, name="done")
    observer = ElementObserver.create(
        target="box",
        on_move=lambda x, y: top.set(y),
        on_transition_end=lambda name: done.set(name == "height"),
    )

    assert [str(hook) for hook in observer.add_hooks()] == [
        (
            'useElementObserver("box", '
            '({ ["onMove"] : ((_ev_0, _ev_1) => (((_ev_0, _ev_1) => (topRxClientStateSet(_ev_1)))'
            "(_ev_0, _ev_1))), "
            '["onTransitionEnd"] : ((_ev_0) => (((_ev_0) => '
            '(doneRxClientStateSet((_ev_0?.valueOf?.() === "height"?.valueOf?.()))))'
            "(_ev_0))) }), ({  }));"
        )
    ]


def test_element_observer_without_handlers_observes_nothing():
    """Without a trigger to report to there is no hook and no observer."""
    assert ElementObserver.create(target="box", layout=True).add_hooks() == []


@pytest.mark.parametrize(
    ("child", "observed_id", "child_props", "declaration"),
    [
        (rx.el.div(id="named"), '"named"', ['id:"named"', "ref:ref_named"], None),
        (rx.el.div(), "abc", ["id:abc"], "const abc = useId_abc();"),
    ],
    ids=["own id", "id from useId"],
)
def test_element_observer_observes_its_only_child(
    monkeypatch: pytest.MonkeyPatch,
    child: rx.Component,
    observed_id: str,
    child_props: list[str],
    declaration: str | None,
):
    """Without a target the child is observed, by its own id or one from useId."""
    monkeypatch.setattr(special, "get_unique_variable_name", lambda: "abc")
    shown = rx.client_state(False, name="shown")
    observer = ElementObserver.create(
        child, on_intersect=lambda visible, ratio: shown.set(visible)
    )

    [hook] = observer.add_hooks()
    assert str(hook) == (
        f"useElementObserver({observed_id}, "
        '({ ["onIntersect"] : ((_ev_0, _ev_1) => '
        "(((_ev_0) => (shownRxClientStateSet(_ev_0)))"
        "(_ev_0, _ev_1))) }), ({  }));"
    )
    assert observer.render() == {
        "name": "Fragment",
        "props": [],
        "children": [{"name": '"div"', "props": child_props, "children": []}],
    }
    # An id from useId holds within one compiled component, so the child
    # compiles into the observer's, after the hook that declares the id.
    assert is_snapshot_boundary(observer) is (declaration is not None)
    if declaration is not None:
        added = list(observer._get_added_hooks())
        assert added.index(declaration) < added.index(str(hook))


def test_element_observer_in_a_loop_observes_its_own_item(
    monkeypatch: pytest.MonkeyPatch,
):
    """Every item of rx.foreach observes its own child, not the first item's."""
    monkeypatch.setattr(special, "get_unique_variable_name", lambda: "abc")
    height = rx.client_state(0.0, name="height")
    root = rx.foreach(
        Var.create(["a", "b"]),
        lambda item: rx.element_observer(
            rx.el.div(item), on_resize=lambda width, h: height.set(h)
        ),
    )

    page_ctx = PageContext(name="page", route="/page", root_component=root)
    hooks = CompilerHooks(plugins=default_page_plugins())
    compile_ctx = CompileContext(pages=[], hooks=hooks)
    with compile_ctx, page_ctx:
        page_ctx.root_component = hooks.compile_component(
            root, page_context=page_ctx, compile_context=compile_ctx
        )
        hooks.compile_page(page_ctx, compile_context=compile_ctx)
        memo_files, _ = compiler.compile_memo_components(
            compile_ctx.auto_memo_components.values()
        )

    # Content digests, also camel-cased in prop names, change with the code.
    modules = [
        re.sub(r"_?[0-9a-fA-F]{32}", "", block).strip()
        for _path, code in memo_files
        for block in code.split("export const ")[1:]
    ]
    # The observer, called once per item, takes its id from useId and renders
    # the child with it.
    assert modules == [
        _code(
            "Elementobserver_fragment = /*#__PURE__*/ (() => {",
            "const Elementobserver_fragment = memo(({children, index:index, "
            "itemRxState:item_rx_state_}) => {",
            "    const [heightRxClientState, heightRxClientStateSet] = "
            'useClientState(0.0, "height", true)',
            "const on_resize = useCallback(((_ev_0, _ev_1) => (((_ev_0, _ev_1) => "
            "(heightRxClientStateSet(_ev_1)))(_ev_0, _ev_1))), "
            "[heightRxClientState, heightRxClientStateSet])",
            "const abc = useId_abc();",
            'useElementObserver(abc, ({ ["onResize"] : on_resize }), ({  }));',
            "    return(",
            '        jsx(Fragment,{key:index},jsx("div",{id:abc},item_rx_state_))',
            "    )",
            "});",
            'Elementobserver_fragment.displayName = "ElementObserver";',
            "return Elementobserver_fragment;",
            "})();",
        ),
        _code(
            "Foreach_comp = /*#__PURE__*/ (() => {",
            "const Foreach_comp = memo(({children}) => {",
            "    ",
            "    return(",
            '        Array.prototype.map.call(["a", "b"] ?? [],((item_rx_state_,index)=>'
            "(jsx(Elementobserver_fragment,{index:index,itemRxState:item_rx_state_,"
            "key:index},))))",
            "    )",
            "});",
            'Foreach_comp.displayName = "Foreach";',
            "return Foreach_comp;",
            "})();",
        ),
    ]


@pytest.mark.parametrize(
    "children",
    [(), (rx.el.div(), rx.el.div()), ("text",)],
    ids=["no child", "two children", "not a component"],
)
def test_element_observer_needs_a_target_or_one_child(children: tuple):
    """An observer has to know which element to observe."""
    with pytest.raises(ValueError) as error:
        ElementObserver.create(*children, on_transition_end=rx.console_log)
    assert str(error.value) == (
        "rx.element_observer needs a `target` id or exactly one child component to observe."
    )


@pytest.mark.parametrize(
    "child",
    [
        rx.fragment(rx.el.div()),
        rx.cond(Var.create(True), rx.el.div()),
        rx.match(Var.create(1), (1, rx.el.div()), rx.el.span()),
        rx.foreach(Var.create(["a"]), rx.el.div),
        Bare.create(Var.create("text")),
        ElementObserver.create(target="box", on_transition_end=rx.console_log),
    ],
    ids=["fragment", "cond", "match", "foreach", "text", "observer"],
)
def test_element_observer_needs_a_child_that_renders_an_element(child: rx.Component):
    """A child without an element of its own could never carry the id."""
    with pytest.raises(ValueError) as error:
        ElementObserver.create(child, on_transition_end=rx.console_log)
    assert str(error.value) == (
        "rx.element_observer needs a child that renders an element of its own, "
        "not a fragment, rx.cond, rx.match, rx.foreach or text; pass the id of the "
        "element to observe as `target` instead."
    )
