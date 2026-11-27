"""Tests for the matrix declaration of the parity harness."""

from types import SimpleNamespace

from ui_parity.matrix import Cell, Matrix, label


def test_label_names_a_value_in_a_cell_id():
    assert [label(value) for value in ("solid", True, 3, "Focus Visible!")] == [
        "solid",
        "true",
        "3",
        "focus-visible",
    ]


def test_cells_cross_some_dimensions_and_sweep_the_rest():
    matrix = Matrix(
        component="button",
        base={"variant": "solid", "size": "2", "children": "Save"},
        cross={"variant": ["solid", "soft"], "size": ["1", "2"]},
        sweep={
            "color_scheme": ["tomato", "indigo"],
            "size": {"responsive": {"initial": "1", "md": "3"}},
            "appearance": ["dark"],
            "state": ["hover"],
            "viewport": [520],
        },
        groups=[{"variant": ["soft"], "state": ["hover", "active"]}],
    )
    cells = matrix.cells()
    assert [cell.id for cell in cells] == [
        "base",
        "size-1",
        "size-1_variant-soft",
        "variant-soft",
        "color-scheme-tomato",
        "color-scheme-indigo",
        "size-responsive",
        "base@dark",
        "base@hover",
        "base@520",
        "variant-soft@hover",
        "variant-soft@active",
    ]
    assert cells[2] == Cell(
        props_id="size-1_variant-soft",
        props={"variant": "soft", "size": "1", "children": "Save"},
        appearance="light",
        state="rest",
        viewport=1280,
    )
    assert cells[6].props == {
        "variant": "solid",
        "size": {"initial": "1", "md": "3"},
        "children": "Save",
    }
    assert cells[-1] == Cell(
        props_id="variant-soft",
        props={"variant": "soft", "size": "2", "children": "Save"},
        appearance="light",
        state="active",
        viewport=1280,
    )
    # A page renders an element once, however many environments read it.
    assert list(matrix.rendered()) == [
        "base",
        "size-1",
        "size-1_variant-soft",
        "variant-soft",
        "color-scheme-tomato",
        "color-scheme-indigo",
        "size-responsive",
    ]
    assert matrix.rendered()["variant-soft"] == {
        "variant": "soft",
        "size": "2",
        "children": "Save",
    }


def test_create_calls_the_component_of_the_namespace_unless_told_how():
    namespace = SimpleNamespace(button=lambda **props: ("button", props))
    assert Matrix(component="button").create(namespace, {"size": "1"}) == (
        "button",
        {"size": "1"},
    )
    rendered = Matrix(
        component="button",
        render=lambda namespace, props: namespace.button(text="Save", **props),
    )
    assert rendered.create(namespace, {"size": "1"}) == (
        "button",
        {"text": "Save", "size": "1"},
    )
