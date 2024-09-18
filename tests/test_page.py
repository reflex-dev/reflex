from reflex import text
from reflex.page import DECORATED_PAGES, page


def test_page_decorator():
    def foo_():
        return text("foo")

    assert len(DECORATED_PAGES) == 0
    decorated_foo_ = page()(foo_)
    assert decorated_foo_ == foo_
    assert len(DECORATED_PAGES) == 1
    DECORATED_PAGES.clear()


def test_page_decorator_with_kwargs():
    def foo_():
        return text("foo")

    assert len(DECORATED_PAGES) == 0
    decorated_foo_ = page(
        route="foo",
        title="Foo",
        image="foo.png",
        description="Foo description",
        meta=["foo-meta"],
        script_tags=["foo-script"],
        on_load=lambda: [],
    )(foo_)
    assert decorated_foo_ == foo_
    assert len(DECORATED_PAGES) == 1
    DECORATED_PAGES.clear()
