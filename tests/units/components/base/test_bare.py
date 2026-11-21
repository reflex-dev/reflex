import pytest
from reflex_base.components.component import Component
from reflex_base.components.tags.tagless import Tagless
from reflex_base.utils.imports import ImportVar
from reflex_base.vars import ObjectVar
from reflex_base.vars.base import Var, VarData
from reflex_base.vars.sequence import StringVar
from reflex_components_core.base.bare import Bare

STATE_VAR = Var(_js_expr="default_state.name")


@pytest.mark.parametrize(
    ("contents", "expected"),
    [
        ("hello", '"hello"'),
        ("{}", '"{}"'),
        (None, '""'),
        (STATE_VAR, "default_state.name"),
    ],
)
def test_fstrings(contents, expected):
    """Test that fstrings are rendered correctly.

    Args:
        contents: The contents of the component.
        expected: The expected output.
    """
    comp = Bare.create(contents).render()
    assert comp["contents"] == expected


TEXTS_HOOK = "const texts = useTexts()"
PICK_HOOK = "const pick = usePick()"


class PickedVar(ObjectVar[dict]):
    """An object var whose string form needs another hook from the same library."""

    def to_string(self, use_json: bool = True) -> StringVar:
        """Pick a text from the object with a hook.

        Args:
            use_json: Unused.

        Returns:
            The picked text.
        """
        return Var(
            _js_expr=f"pick({self!s})",
            _var_data=VarData(
                hooks={PICK_HOOK: None}, imports={"$/utils/i18n": ["usePick"]}
            ),
        ).to(str)


def test_rendered_string_form_brings_its_hooks_and_imports():
    """An object rendered through to_string carries that var's hooks and imports."""
    texts = PickedVar(
        _js_expr="texts",
        _var_type=dict,
        _var_data=VarData(
            hooks={TEXTS_HOOK: None}, imports={"$/utils/i18n": ["useTexts"]}
        ),
    )
    comp = Bare.create(texts)

    assert comp.render()["contents"] == "pick(texts)"
    assert comp._get_all_hooks() == {TEXTS_HOOK: None, PICK_HOOK: None}
    assert comp._get_all_imports(collapse=True) == {
        "$/utils/i18n": [ImportVar(tag="useTexts"), ImportVar(tag="usePick")]
    }


def test_string_form_is_built_once_per_contents():
    """The string form is built once per contents and shared by the vars and the render."""
    comp = Bare.create(Var(_js_expr="flag", _var_type=bool).guess_type())
    assert isinstance(comp, Bare)
    contents, rendered = comp._get_vars()

    assert contents is comp.contents
    assert tuple(map(id, comp._get_vars())) == (id(contents), id(rendered))
    assert str(rendered) == "(JSON.stringify(flag))"
    assert comp.render() == {"contents": "(JSON.stringify(flag))"}
    assert comp._render() == Tagless(contents="(JSON.stringify(flag))")

    comp.contents = Var(_js_expr="items", _var_type=dict).guess_type()

    assert comp.render() == {"contents": "(JSON.stringify(items))"}
    assert [str(var) for var in comp._get_vars()] == [
        "items",
        "(JSON.stringify(items))",
    ]


BOX_HOOK = "const box = useBox()"
BOX_CODE = "const boxDefaults = {};"


class HookedBox(Component):
    """A component with a hook and custom code of its own."""

    tag = "HookedBox"
    library = "hooked-box"

    def add_hooks(self) -> list[str]:
        """Add the box hook.

        Returns:
            The hooks.
        """
        return [BOX_HOOK]

    def add_custom_code(self) -> list[str]:
        """Add the box defaults.

        Returns:
            The custom code.
        """
        return [BOX_CODE]


class BoxedVar(ObjectVar[dict]):
    """An object var whose string form renders through a component."""

    def to_string(self, use_json: bool = True) -> StringVar:
        """Render the object through a box component.

        Args:
            use_json: Unused.

        Returns:
            The boxed text.
        """
        return Var(
            _js_expr=f"box({self!s})",
            _var_data=VarData(components=(HookedBox.create(id="box"),)),
        ).to(str)


def test_rendered_string_form_brings_its_components():
    """Components carried by the string form count like those of the contents."""
    comp = Bare.create(BoxedVar(_js_expr="data", _var_type=dict))

    assert comp.render()["contents"] == "box(data)"
    assert comp._get_all_hooks() == {
        'const ref_box = useRegisteredRef("ref_box");': None,
        BOX_HOOK: None,
    }
    assert comp._get_all_custom_code() == {BOX_CODE: None}
    assert comp._get_all_refs() == {"ref_box": None}
    # the compiler reaches the box's imports through the prop traversal too
    assert [type(c) for c in comp._get_components_in_props()] == [HookedBox]
    assert comp._get_all_imports(collapse=True) == {
        "$/utils/state": [ImportVar(tag="useRegisteredRef")],
        "hooked-box": [ImportVar(tag="HookedBox")],
    }
