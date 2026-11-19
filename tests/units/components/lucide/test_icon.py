import re

import pytest
from reflex_base.utils import format
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData
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


def test_dynamic_icon_name_normalizes_digit_x_digit():
    """Var-tagged icons drop the hyphen snake_case leaves in ``grid_2x_2``."""
    icon = Icon.create(Var("state_icon").to(str))
    assert (
        str(icon.render()["props"][0])
        == 'name:state_icon.replaceAll("_", "-").replace(/(\\d)x-(\\d)/g, "$1x$2")'
    )


@pytest.mark.parametrize("tag", LUCIDE_ICON_LIST)
def test_dynamic_icon_name_matches_lucide_name(tag):
    """The runtime name conversion agrees with the verified per-icon file names."""
    # Mirror the JS expression emitted by dynamic_icon_name_operation.
    name = re.sub(r"(\d)x-(\d)", r"\1x\2", tag.replace("_", "-"))
    # "fingerprint" is a Lucide alias that DynamicIcon resolves under its own
    # name; only the deep import needs the aliased file name.
    expected = (
        "fingerprint"
        if tag == "fingerprint"
        else LUCIDE_ICON_FILENAME_OVERRIDE.get(tag, format.to_kebab_case(tag))
    )
    assert name == expected


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        (
            "wifi_off",
            ImportVar(
                "WifiOff",
                is_default=True,
                alias="LucideWifiOff",
                package_path="/dist/esm/icons/wifi-off.mjs",
            ),
        ),
        (
            "fingerprint",
            ImportVar(
                "FingerprintPattern",
                is_default=True,
                alias="LucideFingerprintPattern",
                package_path="/dist/esm/icons/fingerprint-pattern.mjs",
            ),
        ),
        (
            "grid_2x_2",
            ImportVar(
                "Grid2X2",
                is_default=True,
                alias="LucideGrid2X2",
                package_path="/dist/esm/icons/grid-2x2.mjs",
            ),
        ),
    ],
)
def test_static_icon_import_var(tag: str, expected: ImportVar):
    """Expose the actual default module import through the component API.

    Args:
        tag: The static icon name.
        expected: Its deep import, including aliases and file-name overrides.
    """
    assert Icon.create(tag).import_var == expected


@pytest.mark.parametrize("is_default", [False, True])
@pytest.mark.parametrize("reactive", [False, True])
def test_dynamic_icon_import_var(is_default: bool, reactive: bool):
    """Expose the named dynamic module import through the component API.

    Args:
        is_default: Whether the caller requests a default import.
        reactive: Whether to construct the icon through the reactive factory.
    """
    name = Var("icon_name").to(str)
    icon = (
        Icon.create(name, is_default=is_default)
        if reactive
        else DynamicIcon.create(name=name, is_default=is_default)
    )
    assert icon.import_var == ImportVar("DynamicIcon", package_path="/dynamic.mjs")


@pytest.mark.parametrize("reactive", [False, True])
def test_icon_keeps_var_imports(reactive: bool):
    """Assembling icon imports retains other Lucide imports required by props.

    Args:
        reactive: Whether to render a dynamic icon.
    """
    required = ImportVar("icons", alias="lucideIcons")
    size = Var(
        "Object.keys(lucideIcons).length",
        _var_type=int,
        _var_data=VarData(imports={LUCIDE_LIBRARY: [required]}),
    )
    icon = Icon.create(Var("icon_name").to(str) if reactive else "apple", size=size)
    first = {
        library: list(import_vars)
        for library, import_vars in icon._get_imports().items()
    }
    assert required in first[LUCIDE_LIBRARY]
    assert icon.import_var in first[LUCIDE_LIBRARY]
    assert icon._get_imports() == first


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
