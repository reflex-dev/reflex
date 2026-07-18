"""Integration tests for ``rx.memo`` runtime behavior.

Covers behaviors previously exercised by the deleted
``tests/integration/test_memo.py`` (Selenium): partial-application of an
``EventHandler`` prop (``event(some_value)``) and raw pass-through to an
inner event trigger (``on_change=event``). Also covers recursion through a
self-referencing component memo rendering a tree via ``rx.foreach``.
"""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def MemoApp():
    """App exercising ``rx.memo`` with ``EventHandler`` props and recursion."""
    from collections.abc import Sequence
    from typing import TypedDict

    import reflex as rx

    class TreeNode(TypedDict):
        name: str
        children: Sequence["TreeNode"]

    class MemoState(rx.State):
        last_value: str = ""
        order: list[str] = ["row-a", "row-b", "row-c"]
        tree: TreeNode = TreeNode(
            name="root",
            children=[
                TreeNode(name="child1", children=[]),
                TreeNode(
                    name="child2",
                    children=[TreeNode(name="grandchild1", children=[])],
                ),
            ],
        )

        @rx.event
        def set_last_value(self, value: str):
            self.last_value = value

        @rx.event
        def replace_tree(self):
            self.tree = TreeNode(
                name="root2",
                children=[TreeNode(name="only-child", children=[])],
            )

        @rx.event
        def reverse_order(self):
            self.order = list(reversed(self.order))

    @rx.memo
    def my_memoed_component(
        some_value: rx.Var[str],
        event: rx.EventHandler[rx.event.passthrough_event_spec(str)],
    ) -> rx.Component:
        return rx.vstack(
            rx.button(some_value, id="memo-button", on_click=event(some_value)),
            rx.input(id="memo-input", on_change=event),
        )

    @rx.memo
    def tree_node(data: rx.vars.ObjectVar[TreeNode]) -> rx.Component:
        return rx.vstack(
            rx.text(data.name, class_name="tree-node-name"),
            rx.foreach(data.children, lambda child: tree_node(data=child)),
            class_name="pl-4 border-l",
        )

    @rx.memo
    def keyed_row(label: rx.Var[str]) -> rx.Component:
        # Uncontrolled input: its typed value lives in the DOM, not in state,
        # so React only preserves it across a reorder when the element keeps
        # its identity — i.e. when ``key`` is honored. ``label`` doubles as the
        # element id so each row is locatable after reordering.
        return rx.input(id=label)

    @rx.memo(wrapper=None)
    def unwrapped_label(value: rx.Var[str]) -> rx.Component:
        # Compiled without the React ``memo`` wrapper: a bare function
        # component that must still render and follow its prop.
        return rx.text(value, id="unwrapped-label")

    def index() -> rx.Component:
        return rx.vstack(
            rx.text(MemoState.last_value, id="memo-last-value"),
            my_memoed_component(
                some_value="memod_some_value", event=MemoState.set_last_value
            ),
            rx.button(
                "replace-tree", id="replace-tree", on_click=MemoState.replace_tree
            ),
            rx.box(tree_node(data=MemoState.tree), id="tree-root"),
            rx.button(
                "reverse-order", id="reverse-order", on_click=MemoState.reverse_order
            ),
            rx.box(
                rx.foreach(
                    MemoState.order, lambda item: keyed_row(label=item, key=item)
                ),
                id="keyed-rows",
            ),
            unwrapped_label(value=MemoState.last_value),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def memo_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Run the memo app under an AppHarness.

    Args:
        tmp_path_factory: Pytest fixture for creating temporary directories.

    Yields:
        The running harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("memo_app"),
        app_source=MemoApp,
    ) as harness:
        yield harness


def test_memo_event_handler_partial_application(
    memo_app: AppHarness, page: Page
) -> None:
    """Clicking a button whose ``on_click`` is ``event(some_value)`` dispatches it.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)

    expect(page.locator("#memo-last-value")).to_have_text("")
    page.click("#memo-button")
    expect(page.locator("#memo-last-value")).to_have_text("memod_some_value")


def test_memo_event_handler_raw_pass_through(memo_app: AppHarness, page: Page) -> None:
    """Typing into an input whose ``on_change`` is the raw handler dispatches it.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)

    page.locator("#memo-input").fill("typed_value")
    expect(page.locator("#memo-last-value")).to_have_text("typed_value")


def test_memo_recursive_tree_render(memo_app: AppHarness, page: Page) -> None:
    """A self-referencing component memo renders nested children via ``rx.foreach``.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)

    tree_root = page.locator("#tree-root")
    node_names = tree_root.locator(".tree-node-name")
    expect(node_names).to_have_count(4)
    expect(node_names).to_have_text(["root", "child1", "child2", "grandchild1"])


def test_memo_recursive_tree_reacts_to_state(memo_app: AppHarness, page: Page) -> None:
    """Replacing the tree in state re-renders the recursive memo with new data.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)

    node_names = page.locator("#tree-root .tree-node-name")
    expect(node_names).to_have_count(4)

    page.click("#replace-tree")

    expect(node_names).to_have_count(2)
    expect(node_names).to_have_text(["root2", "only-child"])


def test_memo_key_preserves_identity_across_reorder(
    memo_app: AppHarness, page: Page
) -> None:
    """``key`` on a memo under ``rx.foreach`` drives React's reconciliation.

    Each row is a memo with an uncontrolled input keyed by its label. Type a
    distinct value into each, reverse the list, and the values must follow
    their labels rather than their positions — which only happens if the
    ``key`` reaches React. (``rx.foreach`` would otherwise key by index, giving
    positional identity, so this asserts the explicit ``key`` is honored.)

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)

    rows = page.locator("#keyed-rows input")
    expect(rows).to_have_count(3)
    for row_id in ("row-a", "row-b", "row-c"):
        page.locator(f"#{row_id}").fill(row_id.upper())

    page.click("#reverse-order")

    # Order reversed (positional proof the reorder happened) ...
    expect(rows.first).to_have_attribute("id", "row-c")
    expect(rows.last).to_have_attribute("id", "row-a")
    # ... while each row kept the value typed into it, by key, not by slot.
    for row_id in ("row-a", "row-b", "row-c"):
        expect(page.locator(f"#{row_id}")).to_have_value(row_id.upper())


def test_memo_wrapper_none_renders_and_updates(
    memo_app: AppHarness, page: Page
) -> None:
    """A ``wrapper=None`` memo renders as a bare function component.

    The compiled module exports the component without React's ``memo``
    wrapper; it must still mount and re-render when its prop changes.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)

    expect(page.locator("#unwrapped-label")).to_have_text("")
    page.locator("#memo-input").fill("unwrapped_update")
    expect(page.locator("#unwrapped-label")).to_have_text("unwrapped_update")
