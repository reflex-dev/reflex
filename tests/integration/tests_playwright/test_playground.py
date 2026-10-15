"""Integration tests for the benchmark contract of examples/playground."""

import re
import shutil
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness
from scripts.hash_examples import PLAYGROUND_DIR, hashed_files

# Each hot reload target: the file holding its pragma line and the element showing it.
HMR_TARGETS = {
    "leaf": ("playground/components/marker.py", "#bench-marker-leaf"),
    "root": ("playground/layout.py", "#bench-marker-root"),
    "handler": ("playground/state.py", "#bench-handler-value"),
}


@pytest.fixture(scope="module")
def playground(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Run a copy of the files the playground's content hash covers.

    Args:
        tmp_path_factory: Pytest temporary path factory.

    Yields:
        The running application harness.
    """
    root = tmp_path_factory.mktemp("playground")
    for path in hashed_files(PLAYGROUND_DIR):
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PLAYGROUND_DIR / path, root / path)
    with AppHarness.create(root=root, app_name="playground") as harness:
        yield harness


def _open(playground: AppHarness, page: Page, path: str = "/") -> None:
    """Open a page of the playground and wait for its readiness marker.

    Args:
        playground: The running playground.
        page: Playwright page.
        path: The route to open.
    """
    assert playground.frontend_url is not None
    page.goto(playground.frontend_url.rstrip("/") + path)
    expect(page.locator("#bench-hydrated")).to_be_attached()


def test_hmr_targets_show_their_pragma_values(playground: AppHarness, page: Page):
    _open(playground, page)
    page.click("#bench-handler")
    for name, (path, selector) in HMR_TARGETS.items():
        source = (playground.app_path / path).read_text(encoding="utf-8")
        # The hot reload benchmarks rewrite the string on exactly this line.
        values = re.findall(
            rf'^\w+ = "([^"]*)"  # bench:hmr-target {name}$', source, re.MULTILINE
        )
        assert len(values) == 1, f"{path} needs one `# bench:hmr-target {name}` line"
        expect(page.locator(selector)).to_have_text(values[0])


def test_set_seq_round_trip(playground: AppHarness, page: Page):
    _open(playground, page)
    expect(page.locator("#bench-seq")).to_have_text("0")
    page.click("#bench-set-seq")
    expect(page.locator("#bench-seq")).to_have_text("7")


def test_counter(playground: AppHarness, page: Page):
    _open(playground, page, "/counter")
    count = page.locator("#count")
    expect(count).to_have_text("0")
    expect(page.get_by_text("even", exact=True)).to_be_visible()
    page.click("#increment")
    expect(count).to_have_text("1")
    expect(page.get_by_text("odd", exact=True)).to_be_visible()
    page.click("#decrement")
    expect(count).to_have_text("0")


def test_item_route(playground: AppHarness, page: Page):
    _open(playground, page, "/item/42")
    expect(page.locator("#item-id")).to_have_text("42")
    # The index page links each item of its rx.foreach list to the dynamic route.
    page.get_by_role("link", name="Home").click()
    page.get_by_role("link", name="beta").click()
    expect(page.locator("#item-id")).to_have_text("beta")
