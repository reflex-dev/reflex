"""Integration tests for stateful ``rx.cond`` and ``rx.match`` rendering."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def CondMatchApp():
    """App exercising conditional rendering across state transitions."""
    from copy import deepcopy

    import reflex as rx

    class CondMatchState(rx.State):
        val_a: str = "A"
        val_b: str = "B"
        previous: rx.Field[dict[str, dict[str, str]]] = rx.field(
            default_factory=lambda: {
                "wall": {"color": "red", "finish": "matte"},
                "roof": {"color": "gray"},
            }
        )
        current: rx.Field[dict[str, dict[str, str]]] = rx.field(
            default_factory=lambda: {
                "roof": {"color": "gray"},
                "wall": {"finish": "matte", "color": "red"},
            }
        )

        @rx.event
        def select_a(self):
            self.val_a = "A"

        @rx.event
        def select_b(self):
            self.val_a = "B"

        @rx.event
        def select_c(self):
            self.val_a = "C"

        @rx.event
        def change_color(self):
            """Change a nested value in the current form data."""
            self.current["wall"]["color"] = "blue"

        @rx.event
        def reorder_keys(self):
            """Reverse object key order without changing the form values."""
            self.current = dict(reversed(tuple(self.current.items())))

        @rx.event
        def save(self):
            """Save an independent snapshot of the current form data."""
            self.previous = deepcopy(self.current)

    def index():
        """Render conditional branches and a form that tracks nested changes.

        Returns:
            The conditional components, comparison results, and form controls.
        """
        equal = CondMatchState.current.deep_equals(CondMatchState.previous)
        return rx.box(
            rx.hstack(
                rx.button("A", on_click=CondMatchState.select_a, id="select-a"),
                rx.button("B", on_click=CondMatchState.select_b, id="select-b"),
                rx.button("C", on_click=CondMatchState.select_c, id="select-c"),
            ),
            rx.text(CondMatchState.val_a, id="current-value"),
            rx.box(
                rx.cond(
                    CondMatchState.val_a == "A",
                    rx.text(CondMatchState.val_a, id="cond-true"),
                    rx.text(CondMatchState.val_b, id="cond-false"),
                ),
                id="cond-container",
            ),
            rx.box(
                rx.match(
                    CondMatchState.val_a,
                    ("A", rx.text(CondMatchState.val_a + " is selected", id="match-a")),
                    ("B", rx.text(CondMatchState.val_b + " is selected", id="match-b")),
                    rx.text("No value selected", id="match-default"),
                ),
                id="match-container",
            ),
            rx.el.input(
                id="token",
                value=CondMatchState.router.session.client_token,
                read_only=True,
            ),
            rx.text(rx.cond(equal, "clean", "dirty"), id="deep-status"),
            rx.text(CondMatchState.current.to_string(), id="deep-current"),
            rx.text(
                (CondMatchState.current == CondMatchState.previous).to_string(),
                id="identity-equal",
            ),
            rx.text(
                CondMatchState.current.deep_equals({
                    "wall": {"color": "red", "finish": "matte"},
                    "roof": {"color": "gray"},
                }).to_string(),
                id="deep-state-literal",
            ),
            rx.button("Change color", on_click=CondMatchState.change_color),
            rx.button("Reorder keys", on_click=CondMatchState.reorder_keys),
            rx.button("Save", on_click=CondMatchState.save, disabled=equal),
            *[
                rx.text(
                    rx.Var.create(left).deep_equals(right).to_string(),
                    id=f"deep-{name}",
                )
                for name, left, right in [
                    ("key-order", {"a": 1, "b": 2}, {"b": 2, "a": 1}),
                    (
                        "nested-equal",
                        {"a": {"b": [1, None, True], "c": "red"}},
                        {"a": {"c": "red", "b": [1, None, True]}},
                    ),
                    ("nested-different", {"a": {"b": 1}}, {"a": {"b": 2}}),
                    ("missing-key", {"a": None}, {}),
                    ("array-equal", [1, {"a": None}], [1, {"a": None}]),
                    ("array-order", [1, 2], [2, 1]),
                    ("array-length", [1], [1, 2]),
                    ("empty-object", {}, {}),
                    ("empty-array", [], []),
                    ("array-vs-object", [], {}),
                    ("null", None, None),
                    ("null-vs-object", None, {}),
                    ("bool-vs-number", True, 1),
                    ("number-vs-string", 1, "1"),
                ]
            ],
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def cond_match_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Create a harness for the cond/match regression app.

    Args:
        app_harness_env: AppHarness environment for dev or production builds.
        tmp_path_factory: Pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness for the test app.
    """
    name = f"cond_match_{app_harness_env.__name__.lower()}"
    with app_harness_env.create(
        root=tmp_path_factory.mktemp(name),
        app_name=name,
        app_source=CondMatchApp,
    ) as harness:
        yield harness


def test_cond_and_match_render_only_selected_branch(
    cond_match_app: AppHarness, page: Page
):
    """Cond and Match should render exactly one active branch per state value.

    Args:
        cond_match_app: Running harness for the cond/match app.
        page: Playwright page.
    """
    assert cond_match_app.frontend_url is not None
    page.goto(cond_match_app.frontend_url)

    expect(page.locator("#current-value")).to_have_text("A")
    expect(page.locator("#cond-true")).to_have_text("A")
    expect(page.locator("#cond-false")).to_have_count(0)
    expect(page.locator("#match-a")).to_have_text("A is selected")
    expect(page.locator("#match-b")).to_have_count(0)
    expect(page.locator("#match-default")).to_have_count(0)

    page.click("#select-b")
    expect(page.locator("#current-value")).to_have_text("B")
    expect(page.locator("#cond-true")).to_have_count(0)
    expect(page.locator("#cond-false")).to_have_text("B")
    expect(page.locator("#match-a")).to_have_count(0)
    expect(page.locator("#match-b")).to_have_text("B is selected")
    expect(page.locator("#match-default")).to_have_count(0)

    page.click("#select-c")
    expect(page.locator("#current-value")).to_have_text("C")
    expect(page.locator("#cond-true")).to_have_count(0)
    expect(page.locator("#cond-false")).to_have_text("B")
    expect(page.locator("#match-a")).to_have_count(0)
    expect(page.locator("#match-b")).to_have_count(0)
    expect(page.locator("#match-default")).to_have_text("No value selected")


def test_deep_equals_literals(cond_match_app: AppHarness, page: Page):
    """Compare nested literals by value while preserving types and array order.

    Args:
        cond_match_app: Running harness for the comparison app.
        page: Playwright page.
    """
    assert cond_match_app.frontend_url is not None
    page.goto(cond_match_app.frontend_url)

    for name, expected in [
        ("key-order", "true"),
        ("nested-equal", "true"),
        ("nested-different", "false"),
        ("missing-key", "false"),
        ("array-equal", "true"),
        ("array-order", "false"),
        ("array-length", "false"),
        ("empty-object", "true"),
        ("empty-array", "true"),
        ("array-vs-object", "false"),
        ("null", "true"),
        ("null-vs-object", "false"),
        ("bool-vs-number", "false"),
        ("number-vs-string", "false"),
    ]:
        expect(page.locator(f"#deep-{name}")).to_have_text(expected)


def test_deep_equals_state_updates(cond_match_app: AppHarness, page: Page):
    """Track nested form edits and saved snapshots using frontend deep equality.

    Args:
        cond_match_app: Running harness for the comparison app.
        page: Playwright page.
    """
    assert cond_match_app.frontend_url is not None
    page.goto(cond_match_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    status = page.locator("#deep-status")
    literal_equal = page.locator("#deep-state-literal")
    save = page.get_by_role("button", name="Save", exact=True)
    expect(status).to_have_text("clean")
    expect(literal_equal).to_have_text("true")
    expect(page.locator("#identity-equal")).to_have_text("false")
    expect(save).to_be_disabled()

    page.get_by_role("button", name="Change color").click()
    expect(status).to_have_text("dirty")
    expect(literal_equal).to_have_text("false")
    expect(save).to_be_enabled()

    save.click()
    expect(status).to_have_text("clean")
    expect(literal_equal).to_have_text("false")
    expect(save).to_be_disabled()
    expect(page.locator("#identity-equal")).to_have_text("false")

    current = page.locator("#deep-current")
    before_reorder = current.inner_text()
    page.get_by_role("button", name="Reorder keys").click()
    expect(current).not_to_have_text(before_reorder)
    expect(status).to_have_text("clean")
    expect(save).to_be_disabled()
