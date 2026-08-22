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

        @rx.event
        def record_submit(self, item: str, position: int):
            self.last_value = f"{item}@{position}"

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

    def scoped_row(item: rx.Var[str], position: rx.Var[int]) -> rx.Component:
        # No ``rx.memo``: an inline foreach body, which is where loop vars used
        # to fall out of scope. Every consumer here compiles into its own
        # module -- the submit handler into a ``useCallback``, the client state
        # read into its own memo -- so each one only works if it can reach the
        # loop item from the scope the loop provides around the item.
        opened = rx.client_state(False, prefix="opened")
        return rx.hstack(
            rx.form(
                rx.el.button("submit", type="submit"),
                on_submit=lambda _form_data: MemoState.record_submit(item, position),
                id=f"scoped-form-{position}",
            ),
            rx.el.button(
                "toggle",
                id=f"scoped-toggle-{position}",
                on_click=opened.set(~opened.value),
            ),
            rx.text(
                rx.cond(opened.value, f"open:{item}", f"closed:{item}"),
                id=f"scoped-status-{position}",
            ),
        )

    def index() -> rx.Component:
        return rx.vstack(
            rx.input(
                value=MemoState.router.session.client_token,
                read_only=True,
                id="token",
            ),
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
            rx.box(
                rx.foreach(MemoState.order, scoped_row),
                id="scoped-rows",
            ),
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


def _load_page(page: Page, memo_app: AppHarness) -> None:
    """Navigate to the app and wait until it is hydrated and connected.

    Waits for the client token to appear so that event handlers are attached
    before the test interacts with the page.

    Args:
        page: Playwright page.
        memo_app: Running app harness.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")


def test_memo_event_handler_partial_application(
    memo_app: AppHarness, page: Page
) -> None:
    """Clicking a button whose ``on_click`` is ``event(some_value)`` dispatches it.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    _load_page(page, memo_app)

    expect(page.locator("#memo-last-value")).to_have_text("")
    page.click("#memo-button")
    expect(page.locator("#memo-last-value")).to_have_text("memod_some_value")


def test_memo_event_handler_raw_pass_through(memo_app: AppHarness, page: Page) -> None:
    """Typing into an input whose ``on_change`` is the raw handler dispatches it.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    _load_page(page, memo_app)

    page.locator("#memo-input").fill("typed_value")
    expect(page.locator("#memo-last-value")).to_have_text("typed_value")


def test_memo_recursive_tree_render(memo_app: AppHarness, page: Page) -> None:
    """A self-referencing component memo renders nested children via ``rx.foreach``.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    _load_page(page, memo_app)

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
    _load_page(page, memo_app)

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
    _load_page(page, memo_app)

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
    _load_page(page, memo_app)

    expect(page.locator("#unwrapped-label")).to_have_text("")
    page.locator("#memo-input").fill("unwrapped_update")
    expect(page.locator("#unwrapped-label")).to_have_text("unwrapped_update")


def test_foreach_item_handler_receives_its_own_loop_vars(
    memo_app: AppHarness, page: Page
) -> None:
    """A submit handler inside an inline foreach body sees its item and index.

    Regression for reflex-dev/reflex#3210: the handler compiles into a
    ``useCallback`` that the compiler lifts out of the ``.map`` body, so the
    loop vars it referenced were not in scope and the page threw
    ``ReferenceError``. Submitting each row must report that row's own values.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    _load_page(page, memo_app)

    for position, item in enumerate(("row-a", "row-b", "row-c")):
        page.locator(f"#scoped-form-{position} button").click()
        expect(page.locator("#memo-last-value")).to_have_text(f"{item}@{position}")


def test_foreach_item_client_state_is_per_item(
    memo_app: AppHarness, page: Page
) -> None:
    """An unnamed client state var in an inline foreach body is per item.

    The var is constructed once at compile time, so all three rows resolve the
    same generated name -- against the scope the loop opens around each item,
    which is what makes them independent. The rendered text also interpolates
    the loop item, so this covers the item reaching a memoized reader.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    _load_page(page, memo_app)

    expect(page.locator("#scoped-status-0")).to_have_text("closed:row-a")
    expect(page.locator("#scoped-status-1")).to_have_text("closed:row-b")

    page.locator("#scoped-toggle-1").click()

    expect(page.locator("#scoped-status-1")).to_have_text("open:row-b")
    # The other rows are untouched: each item owns its own slot.
    expect(page.locator("#scoped-status-0")).to_have_text("closed:row-a")
    expect(page.locator("#scoped-status-2")).to_have_text("closed:row-c")
