"""Tests for toast components."""

from reflex_components_lucide.icon import Icon
from reflex_components_sonner import toast


def test_toast_accepts_component_icon() -> None:
    """A toast event renders a component icon and includes its imports."""
    event = toast.success("Saved", icon=Icon.create(tag="check"))

    javascript = str(event.args[0][1])
    var_data = event.args[0][1]._get_all_var_data()

    assert "jsx(LucideCheck" in javascript
    assert var_data is not None
    assert any(
        import_var.alias == "LucideCheck"
        for _, import_vars in var_data.imports
        for import_var in import_vars
    )
