"""Integration test for ``VarData.module_code``.

A Var can declare module-level JS that the page compiler emits at the top of
the page module — alongside ``custom_code`` from Components. When the Var's
``_js_expr`` references that helper, it must be defined for the rendered
output to be correct.

This exercises three facets in one app:

- A Var carrying ``module_code`` directly, used twice on the same page
  (deduplication doesn't break correctness).
- Two distinct Vars with different helpers coexisting on a single page
  (merge preserves both snippets).
- A Var whose ``module_code`` rides on a *hook's* VarData (the ``__init__``
  hook-merge path on ``VarData`` propagates ``module_code`` up).
"""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def VarModuleCodeApp():
    """App where Vars contribute module-level JS helpers."""
    import reflex as rx
    from reflex.vars.base import Var, VarData

    greet_helper = "const greet = (name) => `Hello, ${name}!`;"
    pi_helper = "const PI_APPROX = 3.14;"
    counter_helper = "const fmtCount = (n) => `count=${n}`;"

    greeting = Var(
        _js_expr="greet('World')",
        _var_type=str,
        _var_data=VarData(module_code=(greet_helper,)),
    )
    pi = Var(
        _js_expr="PI_APPROX",
        _var_type=str,
        _var_data=VarData(module_code=(pi_helper,)),
    )
    counter = Var(
        _js_expr="fmtCount(0)",
        _var_type=str,
        _var_data=VarData(
            hooks={
                "const _unused_counter = 0": VarData(module_code=(counter_helper,)),
            },
        ),
    )

    def basic():
        return rx.box(
            rx.text(greeting, id="greeting"),
            rx.text(greeting, id="greeting-2"),
        )

    def multi():
        return rx.box(
            rx.text(greeting, id="greeting"),
            rx.text(pi, id="pi"),
        )

    def hook():
        return rx.box(rx.text(counter, id="counter"))

    app = rx.App()
    app.add_page(basic, route="/")
    app.add_page(multi, route="/multi")
    app.add_page(hook, route="/hook")


@pytest.fixture(scope="module")
def var_module_code_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Run the var-module-code app under an AppHarness.

    Args:
        tmp_path_factory: Pytest fixture for creating temporary directories.

    Yields:
        The running harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("var_module_code"),
        app_source=VarModuleCodeApp,
    ) as harness:
        yield harness


def test_var_module_code_renders_helper_output(
    var_module_code_app: AppHarness, page: Page
) -> None:
    """A Var whose ``_js_expr`` calls a ``module_code`` helper renders correctly.

    Two usages of the same Var on one page must both resolve — proving the
    helper is emitted at module level and that deduplication does not drop it.

    Args:
        var_module_code_app: Running app harness.
        page: Playwright page.
    """
    assert var_module_code_app.frontend_url is not None
    page.goto(var_module_code_app.frontend_url)

    expect(page.locator("#greeting")).to_have_text("Hello, World!")
    expect(page.locator("#greeting-2")).to_have_text("Hello, World!")


def test_var_module_code_multiple_distinct_helpers(
    var_module_code_app: AppHarness, page: Page
) -> None:
    """Two distinct ``module_code`` Vars on one page each resolve their helper.

    Args:
        var_module_code_app: Running app harness.
        page: Playwright page.
    """
    assert var_module_code_app.frontend_url is not None
    page.goto(var_module_code_app.frontend_url + "multi")

    expect(page.locator("#greeting")).to_have_text("Hello, World!")
    expect(page.locator("#pi")).to_have_text("3.14")


def test_var_module_code_via_hook_var_data(
    var_module_code_app: AppHarness, page: Page
) -> None:
    """``module_code`` carried on a hook's VarData propagates to the page.

    Constructing the outer ``VarData`` triggers the hook-merge fast-forward in
    ``VarData.__init__``, which must surface the inner ``module_code`` so the
    helper is emitted alongside the hook itself.

    Args:
        var_module_code_app: Running app harness.
        page: Playwright page.
    """
    assert var_module_code_app.frontend_url is not None
    page.goto(var_module_code_app.frontend_url + "hook")

    expect(page.locator("#counter")).to_have_text("count=0")
