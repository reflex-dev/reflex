import pytest
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


PICK_HOOK = "const pick = usePick()"


class PickedVar(ObjectVar[dict]):
    """An object var whose string form needs a hook and an import."""

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
                hooks={PICK_HOOK: None}, imports={"$/utils/pick": ["usePick"]}
            ),
        ).to(str)


def test_rendered_string_form_brings_its_hooks_and_imports():
    """An object rendered through to_string carries that var's hooks and imports."""
    comp = Bare.create(PickedVar(_js_expr="state.texts", _var_type=dict))
    assert comp.render()["contents"] == "pick(state.texts)"
    assert PICK_HOOK in comp._get_all_hooks()
    assert "$/utils/pick" in comp._get_all_imports()
