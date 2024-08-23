from reflex.utils.string import remove_prefix


def test_remove_prefix():
    assert remove_prefix("hello world", "hello ") == "world"
