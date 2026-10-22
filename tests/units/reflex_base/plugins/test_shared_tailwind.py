import pytest
from reflex_base.plugins.shared_tailwind import tailwind_config_js_template


@pytest.mark.parametrize(
    ("important", "expected"),
    [(True, "important: true,"), ("#app", 'important: "#app",')],
)
def test_config_template_emits_important_key(important: bool | str, expected: str):
    """The `important` option should be written under Tailwind's `important` key."""
    code = tailwind_config_js_template(default_content=[], important=important)

    assert expected in code
    assert "importants" not in code


def test_config_template_omits_important_when_unset():
    """No `important` key should be written when the option is not set."""
    code = tailwind_config_js_template(default_content=[])

    assert "important" not in code
