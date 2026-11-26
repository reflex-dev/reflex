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
            '({ ["onResize"] : ((_width, _height) => (((_width, _height) => '
            "(heightRxClientStateSet(_height)))(_width, _height))), "
            '["onIntersect"] : ((_is_intersecting, _ratio) => (((...args) => '
            "(visibleRxClientStateSet(_is_intersecting, _ratio, ...args)))"
            "(_is_intersecting, _ratio))) }), "
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
            '({ ["onMove"] : ((_x, _y) => (((_x, _y) => (topRxClientStateSet(_y)))'
            "(_x, _y))), "
            '["onTransitionEnd"] : ((_property_name) => (((_property_name) => '
            '(doneRxClientStateSet((_property_name?.valueOf?.() === "height"?.valueOf?.()))))'
            "(_property_name))) }), ({  }));"
        )
    ]


def test_element_observer_without_handlers_observes_nothing():
    """Without a trigger to report to there is no hook and no observer."""
    assert ElementObserver.create(target="box", layout=True).add_hooks() == []


def test_element_observer_observes_its_only_child(monkeypatch: pytest.MonkeyPatch):
    """Without a target the child is observed, by its own id or a generated one."""
    shown = rx.client_state(False, name="shown")

    named = ElementObserver.create(
        rx.el.div(id="named"), on_intersect=lambda visible, ratio: shown.set(visible)
    )
    assert [str(hook) for hook in named.add_hooks()] == [
        (
            'useElementObserver("named", '
            '({ ["onIntersect"] : ((_is_intersecting, _ratio) => '
            "(((_is_intersecting) => (shownRxClientStateSet(_is_intersecting)))"
            "(_is_intersecting, _ratio))) }), ({  }));"
        )
    ]

    monkeypatch.setattr(
        importlib.import_module("reflex_components_core.core.element_observer"),
        "get_unique_variable_name",
        lambda: "abc",
    )
    unnamed = ElementObserver.create(
        rx.el.div(), on_intersect=lambda visible, ratio: shown.set(visible)
    )
    assert [str(hook) for hook in unnamed.add_hooks()] == [
        (
            'useElementObserver("element_observer_abc", '
            '({ ["onIntersect"] : ((_is_intersecting, _ratio) => '
            "(((_is_intersecting) => (shownRxClientStateSet(_is_intersecting)))"
            "(_is_intersecting, _ratio))) }), ({  }));"
        )
    ]
    assert unnamed.render() == {
        "name": "Fragment",
        "props": [],
        "children": [
            {
                "name": '"div"',
                "props": [
                    'id:"element_observer_abc"',
                    "ref:ref_element_observer_abc",
                ],
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
