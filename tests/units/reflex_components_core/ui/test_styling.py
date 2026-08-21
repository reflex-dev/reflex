import pytest
from reflex_base.utils.imports import ImportVar
from reflex_base.vars import Var
from reflex_components_core.ui.styling import cn, variant_class

VARIANTS = {
    "primary": "bg-primary text-primary-foreground",
    "outline": "border border-input",
}


def test_cn_merges_through_clsx_and_tailwind_merge() -> None:
    """Cn should flatten inputs with clsx and resolve conflicts with twMerge."""
    merged = cn("px-2", Var("dynamic"), ["px-4", None])

    assert str(merged) == '(twMerge((clsx("px-2", dynamic, ["px-4", null]))))'
    var_data = merged._get_all_var_data()
    assert var_data is not None
    assert dict(var_data.imports) == {
        "clsx@2.1.1": (ImportVar(tag="clsx", is_default=True),),
        "tailwind-merge@3.6.0": (ImportVar(tag="twMerge"),),
    }


def test_variant_class_static_lookup() -> None:
    """Static variant values resolve to their class string at compile time."""
    assert (
        variant_class(
            "outline", VARIANTS, default="primary", prop="variant", component="c"
        )
        == VARIANTS["outline"]
    )


def test_variant_class_defaults_when_unset() -> None:
    """A None value falls back to the default variant."""
    assert (
        variant_class(None, VARIANTS, default="primary", prop="variant", component="c")
        == VARIANTS["primary"]
    )


def test_variant_class_invalid_static_value_raises() -> None:
    """Unknown static variants raise with the valid options listed."""
    with pytest.raises(ValueError, match="Invalid variant 'nope' for c"):
        variant_class(
            "nope", VARIANTS, default="primary", prop="variant", component="c"
        )


def test_variant_class_var_selects_among_literals() -> None:
    """Var values compile to an expression containing every class literal."""
    resolved = variant_class(
        Var("state.variant").to(str),
        VARIANTS,
        default="primary",
        prop="variant",
        component="c",
    )

    assert isinstance(resolved, Var)
    js_expr = str(resolved)
    for class_name in VARIANTS.values():
        assert class_name in js_expr
