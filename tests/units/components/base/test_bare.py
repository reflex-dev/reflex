import pytest
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
