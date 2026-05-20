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
