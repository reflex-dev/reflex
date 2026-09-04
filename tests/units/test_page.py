import importlib

import pytest
from pytest_mock import MockerFixture
from reflex_base.config import get_config
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


def test_decorated_pages_shim_from_import(
    clean_registration_context: RegistrationContext, mocker: MockerFixture
):
    """The deprecated `from reflex.page import DECORATED_PAGES` still works.

    Args:
        clean_registration_context: A fresh registration context.
        mocker: The pytest-mock fixture.
    """
    deprecate = mocker.patch("reflex_base.utils.console.deprecate")

    def foo_():
        return text("foo")

    page(route="foo")(foo_)

    from reflex.page import DECORATED_PAGES

    assert (
        next(iter(DECORATED_PAGES.values()))
        is clean_registration_context.decorated_pages
    )
    deprecate.assert_called_once()
    assert deprecate.call_args.kwargs["feature_name"] == "reflex.page.DECORATED_PAGES"


def test_decorated_pages_shim_module_attribute(
    clean_registration_context: RegistrationContext, mocker: MockerFixture
):
    """`reflex.page.DECORATED_PAGES` maps the app name to the context's pages.

    Args:
        clean_registration_context: A fresh registration context.
        mocker: The pytest-mock fixture.
    """
    mocker.patch("reflex_base.utils.console.deprecate")
    page_module = importlib.import_module("reflex.page")

    pages = page_module.DECORATED_PAGES
    assert pages[get_config().app_name] is clean_registration_context.decorated_pages
    # 0.9.8 exposed a defaultdict(list), so unknown keys resolve to empty lists.
    assert pages["some-other-app"] == []


def test_page_namespace_unknown_attribute_raises():
    """Unknown attributes on the page namespace raise AttributeError."""
    page_module = importlib.import_module("reflex.page")
    with pytest.raises(AttributeError, match=r"reflex\.page"):
        _ = page_module.definitely_not_an_attribute
