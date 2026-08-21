from reflex_base.config import get_config

from reflex import State, text
from reflex.page import DECORATED_PAGES, page


def test_page_decorator():
    def foo_():
        return text("foo")

    DECORATED_PAGES.clear()
    assert len(DECORATED_PAGES) == 0
    decorated_foo_ = page()(foo_)
    assert decorated_foo_ == foo_
    assert len(DECORATED_PAGES) == 1
    page_data = DECORATED_PAGES.get(get_config().app_name, [])[0][1]
    assert page_data == {}
    DECORATED_PAGES.clear()


def test_page_decorator_accepts_state_metadata():
    """State Vars should be preserved as page metadata without bool evaluation."""

    class PageState(State):
        title: str = "Dynamic title"
        description: str = "Dynamic description"

    def foo_():
        return text("foo")

    DECORATED_PAGES.clear()
    page(title=PageState.title, description=PageState.description)(foo_)

    page_data = DECORATED_PAGES.get(get_config().app_name, [])[0][1]
    assert page_data["title"] is PageState.title
    assert page_data["description"] is PageState.description

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
        meta=[{"name": "keywords", "content": "foo, test"}],
        script_tags=["foo-script"],
        on_load=load_foo,
    )(foo_)
    assert decorated_foo_ == foo_
    assert len(DECORATED_PAGES) == 1
    page_data = DECORATED_PAGES.get(get_config().app_name, [])[0][1]
    assert page_data == {
        "description": "Foo description",
        "image": "foo.png",
        "meta": [{"name": "keywords", "content": "foo, test"}],
        "on_load": load_foo,
        "route": "foo",
        "script_tags": ["foo-script"],
        "title": "Foo",
    }

    DECORATED_PAGES.clear()
