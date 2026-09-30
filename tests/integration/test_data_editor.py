"""Integration test for DataEditor compile-time callback wiring.

The DataEditor derives its ``getCellContent`` callback name deterministically at
creation and emits the matching hook from ``add_hooks`` without mutating the
frozen component. This exercises the full compile pipeline to confirm that:

* identical editors share one callback (their hooks dedupe to a single function),
* editors with different bindings get distinct callbacks,
* every ``getCellContent`` prop resolves to a declared function and no name is
  declared twice, and
* the resulting bundle is valid JS, so the page actually mounts in a browser.
"""

import re
from collections.abc import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness

CALLBACK = r"getData_[0-9a-f]+"


def DataEditorCallbackApp():
    """Reflex app with identical and distinct DataEditors on one page."""
    import reflex as rx

    columns = [
        {"title": "Name", "type": "str"},
        {"title": "Age", "type": "int"},
    ]
    data_a = [["Alice", 30], ["Bob", 25]]
    data_b = [["Carol", 40]]

    def index() -> rx.Component:
        return rx.box(
            rx.data_editor(columns=columns, data=data_a),
            rx.data_editor(
                columns=columns, data=data_a
            ),  # identical -> shared callback
            rx.data_editor(columns=columns, data=data_b),  # distinct -> own callback
            id="editors",
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture
def data_editor_app(tmp_path) -> Generator[AppHarness, None, None]:
    """Start DataEditorCallbackApp at tmp_path via AppHarness.

    Args:
        tmp_path: pytest temporary directory for the app.

    Yields:
        A running AppHarness instance.
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=DataEditorCallbackApp,
    ) as harness:
        yield harness


def test_data_editor_callbacks_compile_and_agree(data_editor_app: AppHarness):
    """Derived callbacks dedupe, stay distinct, and yield a mountable bundle."""
    assert data_editor_app.app_instance is not None, "app is not running"

    web_sources = "\n".join(
        path.read_text() for path in (data_editor_app.app_path / ".web").rglob("*.jsx")
    )

    referenced = set(re.findall(rf"getCellContent:({CALLBACK})", web_sources))
    declared = re.findall(rf"function ({CALLBACK})\(", web_sources)

    # Two distinct (columns, data) bindings across three editors: the identical
    # pair collapses to one callback, the distinct editor gets its own.
    assert len(referenced) == 2, f"expected 2 distinct callbacks, got {referenced}"

    # Every getCellContent prop resolves to a function declared in the output, and
    # no name is declared twice (a clash would be conflicting hook bodies).
    assert referenced <= set(declared), "a getCellContent prop references no function"
    assert len(declared) == len(set(declared)), "a callback is declared more than once"
    assert set(declared) == referenced, "an orphan callback was emitted"

    # The page mounts: a duplicate/undeclared callback would crash the bundle and
    # React would never render the wrapper.
    driver = data_editor_app.frontend()
    assert AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "editors")
    )
