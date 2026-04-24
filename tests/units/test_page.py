from reflex_base.registry import RegistrationContext

from reflex import text
from reflex.page import page


def test_page_decorator(clean_registration_context: RegistrationContext):
    """@page stores the decorated function on the current registration context.

    Args:
        clean_registration_context: A fresh registration context.
    """

    def foo_():
        return text("foo")

    assert clean_registration_context.decorated_pages == []
    decorated_foo_ = page()(foo_)
    assert decorated_foo_ == foo_
    assert len(clean_registration_context.decorated_pages) == 1
    _, page_data = clean_registration_context.decorated_pages[0]
    assert page_data == {}


def test_page_decorator_with_kwargs(
    clean_registration_context: RegistrationContext,
):
    """@page preserves all kwargs on the current registration context.

    Args:
        clean_registration_context: A fresh registration context.
    """

    def foo_():
        return text("foo")

    def load_foo():
        return []

    assert clean_registration_context.decorated_pages == []
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
    assert len(clean_registration_context.decorated_pages) == 1
    _, page_data = clean_registration_context.decorated_pages[0]
    assert page_data == {
        "description": "Foo description",
        "image": "foo.png",
        "meta": [{"name": "keywords", "content": "foo, test"}],
        "on_load": load_foo,
        "route": "foo",
        "script_tags": ["foo-script"],
        "title": "Foo",
    }
