from reflex import text
from reflex.config import get_config
from reflex.page import DECORATED_PAGES, get_decorated_pages, page


def test_page_decorator():
    def foo_():
        return text("foo")

    assert len(DECORATED_PAGES) == 0
    decorated_foo_ = page()(foo_)
    assert decorated_foo_ == foo_
    assert len(DECORATED_PAGES) == 1
    page_data = DECORATED_PAGES.get(get_config().app_name, [])[0][1]
    assert page_data == {}
    DECORATED_PAGES.clear()


def test_page_decorator_with_kwargs():
    def foo_():
        return text("foo")

    def load_foo():
        return []

    DECORATED_PAGES.clear()
    assert len(DECORATED_PAGES) == 0
    decorated_foo_ = page(
        route="foo",
        title="Foo",
        image="foo.png",
        description="Foo description",
        meta=["foo-meta"],
        script_tags=["foo-script"],
        on_load=load_foo,
    )(foo_)
    assert decorated_foo_ == foo_
    assert len(DECORATED_PAGES) == 1
    page_data = DECORATED_PAGES.get(get_config().app_name, [])[0][1]
    assert page_data == {
        "description": "Foo description",
        "image": "foo.png",
        "meta": ["foo-meta"],
        "on_load": load_foo,
        "route": "foo",
        "script_tags": ["foo-script"],
        "title": "Foo",
    }

    DECORATED_PAGES.clear()


def test_get_decorated_pages():
    assert get_decorated_pages() == []

    def foo_():
        return text("foo")

    page()(foo_)

    assert get_decorated_pages() == []
    assert get_decorated_pages(omit_implicit_routes=False) == [{}]

    page(route="foo2")(foo_)

    assert get_decorated_pages() == [{"route": "foo2"}]
    assert get_decorated_pages(omit_implicit_routes=False) == [{}, {"route": "foo2"}]

    page(route="foo3", title="Foo3")(foo_)

    assert get_decorated_pages() == [
        {"route": "foo2"},
        {"route": "foo3", "title": "Foo3"},
    ]
    assert get_decorated_pages(omit_implicit_routes=False) == [
        {},
        {"route": "foo2"},
        {"route": "foo3", "title": "Foo3"},
    ]
