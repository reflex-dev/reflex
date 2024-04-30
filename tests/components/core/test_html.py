import pytest

from reflex.components.core.html import Html


def test_html_no_children():
    with pytest.raises(ValueError):
        _ = Html.create()


def test_html_many_children():
    with pytest.raises(ValueError):
        _ = Html.create("foo", "bar")


def test_html_create():
    html = Html.create("<p>Hello !</p>")
    assert str(html.dangerouslySetInnerHTML) == '{"__html": "<p>Hello !</p>"}'  # type: ignore
    assert (
        str(html)
        == '<div className={`rx-Html`} dangerouslySetInnerHTML={{"__html": "<p>Hello !</p>"}}/>'
    )
