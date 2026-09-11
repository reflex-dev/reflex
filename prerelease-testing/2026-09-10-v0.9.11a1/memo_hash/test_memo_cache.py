"""#6947: two apps compiled in one process must not share auto-memoization names.

Both apps define an `rx.memo` component with the *same* function name and a different
body, plus a hook-bearing component used under `rx.foreach` (the auto-memoization path).
If the naming cache leaks across compiles, the second app renders the first app's markup.
"""

from collections.abc import Generator

import pytest
from reflex.testing import AppHarness


def AppOne():
    """First app: memo named `card`, renders ONE-<v>."""
    import reflex as rx

    class S1(rx.State):
        items: list[str] = ["a", "b"]
        n: int = 1

        @rx.event
        def bump(self):
            self.n += 1

    @rx.memo
    def card(v: rx.Var[str]) -> rx.Component:
        return rx.text(f"ONE-{v}")

    def row(v: rx.Var[str]) -> rx.Component:
        return rx.hstack(rx.text(v), card(v=v))

    def index() -> rx.Component:
        return rx.vstack(
            rx.text(S1.n, id="n"),
            rx.foreach(S1.items, row),
            rx.button("bump", on_click=S1.bump, id="bump"),
            id="root",
        )

    app = rx.App()
    app.add_page(index)


def AppTwo():
    """Second app: a memo with the SAME name, rendering TWO=<v>."""
    import reflex as rx

    class S2(rx.State):
        items: list[str] = ["x", "y", "z"]
        n: int = 100

        @rx.event
        def bump(self):
            self.n += 1

    @rx.memo
    def card(v: rx.Var[str]) -> rx.Component:
        return rx.text(f"TWO={v}!")

    def row(v: rx.Var[str]) -> rx.Component:
        return rx.hstack(rx.text(v), card(v=v))

    def index() -> rx.Component:
        return rx.vstack(
            rx.text(S2.n, id="n"),
            rx.foreach(S2.items, row),
            rx.button("bump", on_click=S2.bump, id="bump"),
            id="root",
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def app_one(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """First app harness."""
    with AppHarness.create(root=tmp_path_factory.mktemp("memo_one"), app_source=AppOne) as h:
        yield h


@pytest.fixture(scope="module")
def app_two(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Second app harness, created in the same process after the first."""
    with AppHarness.create(root=tmp_path_factory.mktemp("memo_two"), app_source=AppTwo) as h:
        yield h


def _compiled(harness: AppHarness) -> dict[str, str]:
    """Every generated .web source file of a harness, by relative path."""
    web = harness.app_path / ".web"
    out = {}
    for path in web.rglob("*.js*"):
        if "node_modules" in path.parts or ".vite" in path.parts:
            continue
        out[str(path.relative_to(web))] = path.read_text(encoding="utf-8", errors="replace")
    return out


def _memo_names(sources: dict[str, str]) -> set[str]:
    """Names of the memo() components defined in a compiled app."""
    import re

    names = set()
    for text in sources.values():
        names.update(re.findall(r"export const (\w+) = memo\(", text))
        names.update(re.findall(r"const (\w+) = memo\(", text))
    return names


def test_first_app_compiles_its_own_memo(app_one: AppHarness):
    """The first app compiled in this process emits its own memo body."""
    blob = "\n".join(_compiled(app_one).values())
    assert "ONE-" in blob
    assert "TWO=" not in blob


def test_second_app_compiles_its_own_memo(app_one: AppHarness, app_two: AppHarness):
    """The second app compiled in the same process emits ITS memo, not the first's."""
    blob = "\n".join(_compiled(app_two).values())
    assert "TWO=" in blob
    assert "ONE-" not in blob, "second app emitted the first app's memoized component"


def test_first_app_output_not_corrupted(app_one: AppHarness, app_two: AppHarness):
    """Compiling the second app must not rewrite the first app's output."""
    blob = "\n".join(_compiled(app_one).values())
    assert "ONE-" in blob
    assert "TWO=" not in blob


def test_memo_names_are_generated_for_both(app_one: AppHarness, app_two: AppHarness):
    """Both apps name their memo components; report the names for the record."""
    one, two = _memo_names(_compiled(app_one)), _memo_names(_compiled(app_two))
    print("app_one memo names:", sorted(one))
    print("app_two memo names:", sorted(two))
    assert one, "no memo() components found in the first app"
    assert two, "no memo() components found in the second app"


def test_backends_both_respond(app_one: AppHarness, app_two: AppHarness):
    """Both apps are still serving after the other was compiled."""
    import urllib.request

    for h in (app_one, app_two):
        assert h.frontend_url is not None
        with urllib.request.urlopen(h.frontend_url, timeout=30) as resp:
            assert resp.status == 200
