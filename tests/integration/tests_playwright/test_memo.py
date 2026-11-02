"""Integration tests for ``rx.memo`` runtime behavior.

Covers behaviors previously exercised by the deleted
``tests/integration/test_memo.py`` (Selenium): partial-application of an
``EventHandler`` prop (``event(some_value)``) and raw pass-through to an
inner event trigger (``on_change=event``). Also covers recursion through a
self-referencing component memo rendering a tree via ``rx.foreach``.
Exercises compiler-enabled and compiler-disabled builds in dev and prod.
"""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness, AppHarnessProd


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
        numbers: rx.Field[list[int]] = rx.field(default_factory=lambda: [1, 2, 3, 4])
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
        def replace_numbers(self):
            """Replace the source array for the frontend calculation."""
            self.numbers = [2, 4, 6, 8, 9]

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

    @rx.memo
    def framed(title: rx.Var[str], children: rx.Var[rx.Component]) -> rx.Component:
        # Stateful prop *and* a children slot: the auto-memoize pass wraps the
        # call site so the state hooks live in the generated wrapper, which
        # passes the page-rendered children straight through.
        return rx.vstack(
            rx.text(title, id="framed-title"),
            rx.box(children, id="framed-slot"),
        )

    @rx.memo(wrapper=None)
    def unwrapped_label(value: rx.Var[str]) -> rx.Component:
        # Compiled without the React ``memo`` wrapper: a bare function
        # component that must still render and follow its prop.
        return rx.text(value, id="unwrapped-label")

    @rx.memo
    def derived_count(divisor: rx.Var[int]) -> rx.Component:
        """Compute a filtered count from state in the generated component.

        Args:
            divisor: Keep numbers divisible by this value.

        Returns:
            The number of matching elements.
        """
        return rx.text(
            MemoState.numbers.filter(lambda number: number % divisor == 0).length(),
            id="derived-count",
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
            derived_count(divisor=2),
            rx.button(
                "replace-numbers",
                id="replace-numbers",
                on_click=MemoState.replace_numbers,
            ),
            framed(
                rx.text(MemoState.last_value, id="framed-child"),
                title=MemoState.last_value,
            ),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(
    scope="module", params=[False, True], ids=["compiler-off", "compiler-on"]
)
def react_compiler(request: pytest.FixtureRequest) -> bool:
    """Select whether the app uses React Compiler.

    Args:
        request: Pytest fixture request containing the compiler flag.

    Returns:
        Whether to enable React Compiler.
    """
    return request.param


@pytest.fixture(scope="module")
def memo_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
    react_compiler: bool,
) -> Generator[AppHarness, None, None]:
    """Run the memo app in dev and prod with React Compiler off and on.

    Args:
        app_harness_env: The development or production app harness.
        tmp_path_factory: Pytest fixture for creating temporary directories.
        react_compiler: Whether to enable React Compiler.

    Yields:
        The running harness.
    """
    name = f"memoapp_{app_harness_env.__name__.lower()}_{int(react_compiler)}"
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("REFLEX_REACT_COMPILER", str(react_compiler))
        with app_harness_env.create(
            root=tmp_path_factory.mktemp(name),
            app_name=name,
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


def test_memo_stateful_prop_and_children_update(
    memo_app: AppHarness, page: Page
) -> None:
    """A memo bound to state renders its children and follows state changes.

    The call site binds a state Var to a prop and passes children positionally,
    so the auto-memoize pass hoists the state hooks into a generated wrapper
    that feeds both the prop and the page-rendered children.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    _load_page(page, memo_app)

    expect(page.locator("#framed-title")).to_have_text("")
    expect(page.locator("#framed-child")).to_have_text("")

    page.locator("#memo-input").fill("framed_update")

    expect(page.locator("#framed-title")).to_have_text("framed_update")
    expect(page.locator("#framed-slot").locator("#framed-child")).to_have_text(
        "framed_update"
    )


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


def test_memo_derived_array_updates(memo_app: AppHarness, page: Page) -> None:
    """Derived values stay current after unrelated writes and array replacement.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    _load_page(page, memo_app)
    count = page.locator("#derived-count")
    expect(count).to_have_text("2")

    page.locator("#memo-input").fill("before replacement")
    expect(page.locator("#memo-last-value")).to_have_text("before replacement")
    expect(count).to_have_text("2")

    page.click("#replace-numbers")
    expect(count).to_have_text("4")

    page.locator("#memo-input").fill("after replacement")
    expect(page.locator("#memo-last-value")).to_have_text("after replacement")
    expect(count).to_have_text("4")


def test_react_compiler_transforms_generated_components(
    memo_app: AppHarness, react_compiler: bool, page: Page
) -> None:
    """Verify the actual served app component uses the compiler runtime.

    Args:
        memo_app: Running app harness.
        react_compiler: Whether React Compiler should be active.
        page: Playwright page.
    """
    if isinstance(memo_app, AppHarnessProd):
        pytest.skip("Vite serves individual source modules only in development")
    _load_page(page, memo_app)
    web_dir = memo_app.app_path / ".web"
    modules = [
        path
        for path in (web_dir / "app_components").rglob("*.jsx")
        if '"derived-count"' in path.read_text()
    ]
    assert len(modules) == 1
    assert memo_app.frontend_url is not None
    module_url = f"{memo_app.frontend_url.rstrip('/')}/{modules[0].relative_to(web_dir).as_posix()}"
    response = page.request.get(module_url)
    assert response.ok
    assert ("compiler-runtime" in response.text()) is react_compiler
