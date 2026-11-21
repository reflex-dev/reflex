import dataclasses

from reflex_base.vars.base import Var
from reflex_base.vars.object import ObjectVar, var_access_path


@dataclasses.dataclass
class Tagged:
    """An object with an attribute to read into."""

    tags: list[str] = dataclasses.field(default_factory=list)


def test_var_access_path_follows_attribute_item_and_index_access() -> None:
    """Attribute, item and index access walk down through casts to the var read from."""
    rows = Var(_js_expr="state.rows")
    mapping = Var(_js_expr="state.mapping")

    root, keys = var_access_path(rows.to(list[Tagged])[0].tags.to(list[str])[-1])
    assert root is rows
    assert keys == (0, "tags", -1)

    root, keys = var_access_path(
        mapping.to(dict[int, Tagged])[1].to(ObjectVar, Tagged).tags
    )
    assert root is mapping
    assert keys == (1, "tags")

    root, keys = var_access_path(rows.to(list[int]))
    assert root is rows
    assert keys == ()


def test_var_access_path_keeps_keys_that_are_vars() -> None:
    """A key or index that is no literal is kept as its var."""
    rows = Var(_js_expr="state.rows")
    index = Var(_js_expr="state.index").to(int)
    key = Var(_js_expr="state.key").to(str)

    root, keys = var_access_path(rows.to(list[dict[str, int]])[index][key])

    assert root is rows
    assert len(keys) == 2
    assert keys[0] is index
    assert keys[1] is key


def test_var_access_path_stops_at_other_operations() -> None:
    """Any other operation is the root, with the keys read off its result."""
    n = Var(_js_expr="state.n").to(int)
    items = Var(_js_expr="state.items").to(list[int])

    root, keys = var_access_path(n + 1)
    assert str(root) == "(state.n + 1)"
    assert keys == ()

    root, keys = var_access_path(items.reverse()[0])
    assert str(root) == str(items.reverse())
    assert keys == (0,)
