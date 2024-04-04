from reflex import _reverse_mapping  # type: ignore


def test__reverse_mapping():
    assert _reverse_mapping({"a": ["b"], "c": ["d"]}) == {"b": "a", "d": "c"}


def test__reverse_mapping_duplicate():
    assert _reverse_mapping({"a": ["b", "c"], "d": ["b"]}) == {"b": "a", "c": "a"}
