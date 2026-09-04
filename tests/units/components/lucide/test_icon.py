import pytest
from reflex_base.utils import format
from reflex_base.vars.base import Var
from reflex_components_lucide.icon import (
    LUCIDE_ICON_FILENAME_OVERRIDE,
    LUCIDE_ICON_LIST,
    LUCIDE_ICON_MAPPING_OVERRIDE,
    LUCIDE_LIBRARY,
    DynamicIcon,
    Icon,
)


@pytest.mark.parametrize("tag", LUCIDE_ICON_LIST)
def test_icon(tag):
    icon = Icon.create(tag)
    assert icon.alias == "Lucide" + LUCIDE_ICON_MAPPING_OVERRIDE.get(
        tag, format.to_title_case(tag)
    )


def _lucide_imports(component):
    return [
        var
        for lib, vars_ in component._get_imports().items()
        if "lucide-react" in lib
        for var in vars_
    ]


def test_static_icon_deep_import():
    """Static string icons import from a deep per-icon module, not the barrel."""
    icon = Icon.create("wifi_off")
    (import_var,) = _lucide_imports(icon)
    assert import_var.package_path == "/dist/esm/icons/wifi-off.mjs"
    assert import_var.is_default
    assert import_var.alias == "LucideWifiOff"
    # The barrel import (package_path "/") must not be emitted.
    assert import_var.package_path != "/"


@pytest.mark.parametrize("tag", LUCIDE_ICON_LIST)
def test_static_icon_import_path(tag):
    """Every icon maps to a deep import using its kebab-case file name."""
    icon = Icon.create(tag)
    (import_var,) = _lucide_imports(icon)
    file_name = LUCIDE_ICON_FILENAME_OVERRIDE.get(tag, format.to_kebab_case(tag))
    assert import_var.package_path == f"/dist/esm/icons/{file_name}.mjs"
    assert import_var.is_default


# Literal expected paths — independent of LUCIDE_ICON_FILENAME_OVERRIDE and the
# kebab helper — so a typo in an override value (the hand-maintained, drift-prone
# part) is actually caught instead of being mirrored on both sides of the assert.
# The override file names were verified to exist under lucide-react's
# dist/esm/icons; the plain entries spot-check the default kebab conversion.
@pytest.mark.parametrize(
    ("tag", "expected_path"),
    [
        ("fingerprint", "/dist/esm/icons/fingerprint-pattern.mjs"),
        ("grid_2x_2", "/dist/esm/icons/grid-2x2.mjs"),
        ("grid_2x_2_check", "/dist/esm/icons/grid-2x2-check.mjs"),
        ("grid_2x_2_plus", "/dist/esm/icons/grid-2x2-plus.mjs"),
        ("grid_2x_2_x", "/dist/esm/icons/grid-2x2-x.mjs"),
        ("grid_3x_3", "/dist/esm/icons/grid-3x3.mjs"),
        # grid_3x2 is NOT an override — its kebab file name already matches.
        ("grid_3x2", "/dist/esm/icons/grid-3x2.mjs"),
        ("wifi_off", "/dist/esm/icons/wifi-off.mjs"),
        ("circle_help", "/dist/esm/icons/circle-help.mjs"),
        ("activity", "/dist/esm/icons/activity.mjs"),
    ],
)
def test_static_icon_import_path_literal(tag, expected_path):
    """Spot-check concrete import paths, especially the file-name overrides."""
    (import_var,) = _lucide_imports(Icon.create(tag))
    assert import_var.package_path == expected_path


def test_dynamic_icon_uses_dynamic_module():
    """Var-tagged icons still resolve through lucide-react/dynamic.mjs."""
    icon = Icon.create(Var("state_icon").to(str))
    assert isinstance(icon, DynamicIcon)
    (import_var,) = _lucide_imports(icon)
    assert import_var.tag == "DynamicIcon"
    assert import_var.package_path == "/dynamic.mjs"
    assert not import_var.is_default


def test_static_icon_import_idempotent():
    """Repeated import computation (cache hits) yields the same deep import."""
    icon = Icon.create("wifi_off")
    first = _lucide_imports(icon)
    second = _lucide_imports(icon)
    assert first == second
    assert all(var.package_path == "/dist/esm/icons/wifi-off.mjs" for var in second)


def test_lucide_library_constant():
    assert LUCIDE_LIBRARY.startswith("lucide-react")


def test_icon_missing_tag():
    with pytest.raises(AttributeError):
        _ = Icon.create()


def test_icon_invalid_tag():
    invalid = Icon.create("invalid-tag")
    assert invalid.tag == "CircleHelp"


def test_icon_multiple_children():
    with pytest.raises(AttributeError):
        _ = Icon.create("activity", "child1", "child2")


def test_icon_add_style():
    ic = Icon.create("activity")
    assert ic.add_style() is None
