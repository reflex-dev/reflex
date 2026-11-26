import importlib

import pytest
from reflex_components_core.core.element_observer import ElementObserver

import reflex as rx


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
    ("child", "observed_id"),
    [(rx.el.div(id="named"), "named"), (rx.el.div(), "element_observer_abc")],
    ids=["own id", "generated id"],
)
def test_element_observer_observes_its_only_child(
    monkeypatch: pytest.MonkeyPatch, child: rx.Component, observed_id: str
):
    """Without a target the child is observed, by its own id or a generated one."""
    monkeypatch.setattr(
        importlib.import_module("reflex_components_core.core.element_observer"),
        "get_unique_variable_name",
        lambda: "abc",
    )
    shown = rx.client_state(False, name="shown")
    observer = ElementObserver.create(
        child, on_intersect=lambda visible, ratio: shown.set(visible)
    )

    assert [str(hook) for hook in observer.add_hooks()] == [
        (
            f'useElementObserver("{observed_id}", '
            '({ ["onIntersect"] : ((_ev_0, _ev_1) => '
            "(((_ev_0) => (shownRxClientStateSet(_ev_0)))"
            "(_ev_0, _ev_1))) }), ({  }));"
        )
    ]
    assert observer.render() == {
        "name": "Fragment",
        "props": [],
        "children": [
            {
                "name": '"div"',
                "props": [f'id:"{observed_id}"', f"ref:ref_{observed_id}"],
                "children": [],
            }
        ],
    }


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
