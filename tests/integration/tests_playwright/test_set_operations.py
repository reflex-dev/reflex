from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def SetOperationsApp():
    import reflex as rx

    class SetOperationsState(rx.State):
        tags: rx.Field[set[str]] = rx.field({"a", "b"})
        other: rx.Field[frozenset[str]] = rx.field(frozenset({"b", "c"}))
        points: rx.Field[set[tuple[int, int]]] = rx.field({(1, 2), (3, 4)})
        maybe: rx.Field[set[str] | None] = rx.field(None)
        received: rx.Field[list[str]] = rx.field([])

        @rx.event
        def add_tag(self):
            self.tags.add("c")

        @rx.event
        def remove_tag(self):
            self.tags.discard("a")

        @rx.event
        def set_maybe(self):
            self.maybe = {"m"}

        @rx.event
        def receive(self, tags: set[str]):
            # The frontend sends the set back as a JSON array.
            self.received = sorted(tags)

    def sorted_text(var, id: str):
        return rx.text(var.to_array().join(","), id=id)

    app = rx.App()

    @app.add_page
    def index():
        return rx.vstack(
            rx.input(
                value=SetOperationsState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            sorted_text(SetOperationsState.tags, "tags"),
            rx.text(SetOperationsState.tags.length(), id="length"),
            rx.text(SetOperationsState.tags.contains("a"), id="has_a"),
            rx.text(SetOperationsState.tags.contains("c"), id="has_c"),
            sorted_text(
                SetOperationsState.tags.union(SetOperationsState.other), "union"
            ),
            sorted_text(
                SetOperationsState.tags.intersection(SetOperationsState.other),
                "intersection",
            ),
            sorted_text(
                SetOperationsState.tags.difference(SetOperationsState.other),
                "difference",
            ),
            sorted_text(
                SetOperationsState.tags.symmetric_difference(SetOperationsState.other),
                "symmetric_difference",
            ),
            rx.text(
                SetOperationsState.tags.issubset(SetOperationsState.other),
                id="issubset",
            ),
            rx.text(
                SetOperationsState.tags.issuperset({"b"}),
                id="issuperset",
            ),
            rx.text(
                SetOperationsState.tags.isdisjoint(["z"]),
                id="isdisjoint",
            ),
            rx.foreach(
                SetOperationsState.tags,
                lambda tag: rx.text(tag, class_name="tag"),
            ),
            # Tuple elements compare by value, not by array identity.
            rx.text(SetOperationsState.points.contains((1, 2)), id="has_point"),
            rx.text(
                SetOperationsState.points.union({(3, 4), (5, 6)}).length(),
                id="points_union_length",
            ),
            rx.text(
                SetOperationsState.points.intersection({(3, 4)}).length(),
                id="points_intersection_length",
            ),
            # A plain list operand may hold duplicates; the result is still a set.
            rx.text(
                SetOperationsState.points.symmetric_difference([
                    (3, 4),
                    (5, 6),
                    (5, 6),
                ]).length(),
                id="points_symmetric_difference_length",
            ),
            rx.text(SetOperationsState.points.contains("o[1,2]"), id="has_key_string"),
            # An unset optional set renders no children instead of failing.
            rx.foreach(
                SetOperationsState.maybe,
                lambda tag: rx.text(tag, class_name="maybe"),
            ),
            rx.text(SetOperationsState.received.join(","), id="received"),
            rx.button("Add", id="add", on_click=SetOperationsState.add_tag),
            rx.button("Remove", id="remove", on_click=SetOperationsState.remove_tag),
            rx.button(
                "Set maybe", id="set_maybe", on_click=SetOperationsState.set_maybe
            ),
            rx.button(
                "Send",
                id="send",
                on_click=SetOperationsState.receive(SetOperationsState.tags),
            ),
            rx.button(
                "Send union",
                id="send_union",
                on_click=SetOperationsState.receive(
                    SetOperationsState.tags.union(SetOperationsState.other)
                ),
            ),
        )


@pytest.fixture
def set_operations_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start the set operations app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("set_operations_app"),
        app_source=SetOperationsApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def _sorted_text(page: Page, id: str) -> str:
    text = page.locator(f"id={id}").text_content() or ""
    return ",".join(sorted(part for part in text.split(",") if part))


def test_set_operations(set_operations_app: AppHarness, page: Page):
    assert set_operations_app.frontend_url is not None

    page.goto(set_operations_app.frontend_url)
    expect(page).to_have_url(set_operations_app.frontend_url)
    # Wait for the backend connection so clicks reach the event handlers.
    expect(page.locator("#token")).not_to_have_value("")

    expect(page.locator("id=length")).to_have_text("2")
    assert _sorted_text(page, "tags") == "a,b"
    expect(page.locator("id=has_a")).to_have_text("true")
    expect(page.locator("id=has_c")).to_have_text("false")
    assert _sorted_text(page, "union") == "a,b,c"
    assert _sorted_text(page, "intersection") == "b"
    assert _sorted_text(page, "difference") == "a"
    assert _sorted_text(page, "symmetric_difference") == "a,c"
    expect(page.locator("id=issubset")).to_have_text("false")
    expect(page.locator("id=issuperset")).to_have_text("true")
    expect(page.locator("id=isdisjoint")).to_have_text("true")
    expect(page.locator(".tag")).to_have_count(2)

    expect(page.locator("id=has_point")).to_have_text("true")
    expect(page.locator("id=points_union_length")).to_have_text("3")
    expect(page.locator("id=points_intersection_length")).to_have_text("1")
    expect(page.locator("id=points_symmetric_difference_length")).to_have_text("2")
    expect(page.locator("id=has_key_string")).to_have_text("false")

    expect(page.locator(".maybe")).to_have_count(0)
    page.locator("id=set_maybe").click()
    expect(page.locator(".maybe")).to_have_count(1)

    # A backend mutation of the set re-renders every operation.
    page.locator("id=add").click()
    expect(page.locator("id=length")).to_have_text("3")
    expect(page.locator("id=has_c")).to_have_text("true")
    assert _sorted_text(page, "tags") == "a,b,c"
    assert _sorted_text(page, "intersection") == "b,c"
    assert _sorted_text(page, "symmetric_difference") == "a"
    expect(page.locator("id=issuperset")).to_have_text("true")
    expect(page.locator(".tag")).to_have_count(3)

    page.locator("id=remove").click()
    expect(page.locator("id=length")).to_have_text("2")
    expect(page.locator("id=has_a")).to_have_text("false")
    expect(page.locator("id=issubset")).to_have_text("true")
    assert _sorted_text(page, "difference") == ""

    # The set round-trips through an event argument.
    page.locator("id=send").click()
    expect(page.locator("id=received")).to_have_text("b,c")
    page.locator("id=send_union").click()
    expect(page.locator("id=received")).to_have_text("b,c")
    page.locator("id=add").click()
    page.locator("id=send_union").click()
    expect(page.locator("id=received")).to_have_text("b,c")
