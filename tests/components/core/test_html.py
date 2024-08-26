import pytest

from reflex.components.core.html import Html
from reflex.state import State


def test_html_no_children():
    with pytest.raises(ValueError):
        _ = Html.create()


def test_html_many_children():
    with pytest.raises(ValueError):
        _ = Html.create("foo", "bar")


def test_html_create():
    html = Html.create("<p>Hello !</p>")
    assert str(html.dangerouslySetInnerHTML) == '({ ["__html"] : "<p>Hello !</p>" })'  # type: ignore
    assert (
        str(html)
        == '<div className={"rx-Html"} dangerouslySetInnerHTML={({ ["__html"] : "<p>Hello !</p>" })}/>'
    )


def test_html_fstring_create():
    class TestState(State):
        """The app state."""

        myvar: str = "Blue"

    html = Html.create(f"<p>Hello {TestState.myvar}!</p>")

    assert (
        str(html.dangerouslySetInnerHTML)  # type: ignore
        == f'({{ ["__html"] : ("<p>Hello "+{str(TestState.myvar)}+"!</p>") }})'
    )
    assert (
        str(html)
        == f'<div className={{"rx-Html"}} dangerouslySetInnerHTML={{{str(html.dangerouslySetInnerHTML)}}}/>'  # type: ignore
    )
