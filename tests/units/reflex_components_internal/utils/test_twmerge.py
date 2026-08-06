from reflex_base.utils.imports import ImportVar
from reflex_base.vars import Var
from reflex_components_internal.utils.twmerge import cn


def test_cn_uses_clsx_and_tailwind_merge() -> None:
    """The class utility should flatten inputs before resolving Tailwind conflicts."""
    merged = cn(
        "px-2",
        Var("dynamic"),
        ["px-4", None],
        ("font-bold",),
    )

    assert (
        str(merged)
        == '(twMerge((clsx("px-2", dynamic, ["px-4", null], ["font-bold"]))))'
    )
    var_data = merged._get_all_var_data()
    assert var_data is not None
    assert dict(var_data.imports) == {
        "clsx@2.1.1": (ImportVar(tag="clsx", is_default=True),),
        "tailwind-merge@3.6.0": (ImportVar(tag="twMerge"),),
    }
