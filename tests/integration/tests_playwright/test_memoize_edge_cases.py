"""Integration tests for auto-memoization edge cases.

These exercise components whose memoization needs special care:

- Snapshot boundaries (``recursive=False``) such as ``AccordionTrigger`` whose
  state-dependent logic lives in a descendant. Without the snapshot wrapper
  the cond's state read leaks into the page module and the trigger fails to
  update on state transitions.
- HTML elements with constrained content models (``<title>``, ``<meta>``,
  ``<style>``, ``<script>``). Independent memoization of a stateful ``Bare``
  child renders ``jsx("title", {}, jsx(Bare_xxx, {}))`` — React stringifies
  the component child as ``[object Object]`` (or refuses to render at all
  for void elements). Snapshot-wrapping keeps the Bare a text interpolation
  inside the parent's body.
- Third-party components whose ``children`` prop asserts a string type
  (``react-markdown``). Same failure mode as constrained HTML elements:
  without snapshot-wrapping, ``rx.markdown(State.var)`` compiles to
  ``jsx(ReactMarkdown, {...}, jsx(Bare_xxx, {}))``, which raises
  "Unexpected value [object Object] for children prop, expected string"
  at render time.

Test design notes:
- The page title is supplied via ``app.add_page(..., title=MemoState.title_marker)``
  so the dynamic value flows through the standard React Router metadata path
  and shows up in ``document.title``.
- Style content is matched on a unique marker substring rather than common
  selectors like ``body`` (which conflicts with Emotion/Sonner stylesheets).
- ``<textarea>``'s runtime value semantics belong to React (children are
  initial-value-only); the no-Bare-component-child invariant is verified by
  the unit tests instead.
"""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def MemoEdgeCasesApp():
    """App exercising memoization edge cases."""
    import reflex as rx

    class SlotHelperProbe(rx.Fragment):
        """Publishes the ``$/utils/state`` slot-merge helpers on ``window``.

        Lets the browser tests assert ``mergeSlotProps`` semantics against the
        real bundled helper and the real ``mergician`` dependency, which is
        where the auto-memo wrappers' prop transparency actually runs.
        """

        def add_imports(self) -> dict[str, list[str]]:
            """Import the helpers the custom code below re-exports.

            Returns:
                The import dict for the state helpers.
            """
            return {"$/utils/state": ["mergeSlotProps", "mergeRefs"]}

        def add_custom_code(self) -> list[str]:
            """Publish the helpers on ``window`` (client only).

            Returns:
                The custom code to emit in the page module.
            """
            return [
                (
                    "if (typeof window !== 'undefined') {"
                    " window.__mergeSlotProps = mergeSlotProps;"
                    " window.__mergeRefs = mergeRefs; }"
                )
            ]

    class RenderProbe(rx.Component):
        """A div that counts how many times React rendered it.

        Used as a memo wrapper's root so the count is exactly the number of
        times the generated wrapper rendered.
        """

        tag = "RenderProbe"

        probe: rx.Var[str]

        label: rx.Var[str]

        def add_custom_code(self) -> list[str]:
            """Define the probe component in the emitting module.

            Returns:
                The custom code defining ``RenderProbe``.
            """
            return [
                """
                function RenderProbe({ probe, label, children, ...rest }) {
                  if (typeof window !== "undefined") {
                    window.__probeRenders ??= {};
                    window.__probeRenders[probe] =
                      (window.__probeRenders[probe] ?? 0) + 1;
                  }
                  return jsx(
                    "div",
                    { "data-probe": probe, "data-label": label, ...rest },
                    children,
                  );
                }
                """
            ]

    class OtherState(rx.State):
        """State the render probes deliberately do not read."""

        unrelated: int = 0

        @rx.event
        def bump_unrelated(self):
            self.unrelated = self.unrelated + 1

    class MemoState(rx.State):
        is_open: bool = False
        title_marker: str = "memo-title-home"
        css_marker: str = "memo-css-light"
        counter: int = 0
        markdown_source: str = "Initial **memo-md-home** text"
        form_default: str = "Ada"
        submitted: rx.Field[dict] = rx.field(default_factory=dict)
        probe_label: str = "one"

        @rx.event
        def next_probe_label(self):
            self.probe_label = "two" if self.probe_label == "one" else "one"

        @rx.event
        def toggle_open(self):
            self.is_open = not self.is_open

        @rx.event
        def handle_submit(self, form_data: dict):
            self.submitted = form_data

        @rx.event
        def set_title_about(self):
            self.title_marker = "memo-title-about"

        @rx.event
        def set_css_dark(self):
            self.css_marker = "memo-css-dark"

        @rx.event
        def bump(self):
            self.counter = self.counter + 1

        @rx.event
        def set_markdown_alt(self):
            self.markdown_source = "Updated **memo-md-away** text"

    def index():
        return rx.box(
            rx.el.style("body { --memo-marker: " + MemoState.css_marker + "; }"),
            rx.box(
                rx.button("toggle", on_click=MemoState.toggle_open, id="toggle"),
                rx.button("title", on_click=MemoState.set_title_about, id="set-title"),
                rx.button("css", on_click=MemoState.set_css_dark, id="set-css"),
                rx.button("bump", on_click=MemoState.bump, id="bump"),
                rx.button("md", on_click=MemoState.set_markdown_alt, id="set-markdown"),
            ),
            rx.accordion.root(
                rx.accordion.item(
                    header=rx.accordion.header(
                        rx.accordion.trigger(
                            rx.cond(
                                MemoState.is_open,
                                rx.text("Hide", id="trigger-hide"),
                                rx.text("Show", id="trigger-show"),
                            ),
                            id="accordion-trigger",
                        ),
                    ),
                    content=rx.accordion.content(rx.text("body")),
                    value="item-1",
                ),
            ),
            rx.text(MemoState.counter, id="counter"),
            # Mirrors the bug-report repro: a static-source markdown next to
            # a Var-source markdown inside the same parent. Pre-fix, the
            # Var-source sibling crashed react-markdown with
            # "Unexpected value [object Object] for children prop".
            rx.vstack(
                rx.markdown("This *is* **working**", id="md-static"),
                rx.markdown(MemoState.markdown_source, id="md-host"),
                id="md-section",
            ),
            # Mirrors reflex-dev/reflex#6849: a stateful input under a Radix
            # ``asChild`` Slot parent. The Slot clones its child (the input's
            # auto-memo wrapper) and injects ``name``/``id``/a ref onto it —
            # the wrapper must forward them to the real input or the field
            # renders unnamed and submits an empty form payload.
            rx.form.root(
                rx.form.field(
                    rx.form.control(
                        rx.input(default_value=MemoState.form_default),
                        as_child=True,
                    ),
                    rx.form.submit(
                        rx.button("Submit", id="form-submit", type="submit"),
                        as_child=True,
                    ),
                    name="full_name",
                ),
                on_submit=MemoState.handle_submit,
            ),
            rx.text(MemoState.submitted.to_string(), id="form-data-out"),
            # Render-count instrumentation. Both probes are auto-memoized on
            # the same ``MemoState.probe_label`` read, but only the first is
            # cloned by a Radix ``asChild`` Slot parent. Their render counts
            # must move together: the transparency layer must not make the
            # Slot-wrapped one render any more often than the plain one, and
            # neither may render for a state they don't read.
            SlotHelperProbe.create(),
            rx.card(
                RenderProbe.create(
                    probe="slot",
                    label=MemoState.probe_label,
                    class_name="own-probe-class",
                ),
                as_child=True,
            ),
            RenderProbe.create(
                probe="plain",
                label=MemoState.probe_label,
                class_name="own-probe-class",
            ),
            rx.button(
                "relabel", on_click=MemoState.next_probe_label, id="probe-relabel"
            ),
            rx.button(
                "unrelated", on_click=OtherState.bump_unrelated, id="probe-unrelated"
            ),
            rx.text(OtherState.unrelated, id="unrelated-out"),
        )

    app = rx.App()
    app.add_page(index, title=MemoState.title_marker)


@pytest.fixture(scope="module")
def memo_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Run the memoization edge-cases app under an AppHarness.

    Args:
        tmp_path_factory: Pytest fixture for creating temporary directories.

    Yields:
        The running harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("memo_edge_cases"),
        app_source=MemoEdgeCasesApp,
    ) as harness:
        yield harness


def test_accordion_trigger_with_stateful_cond_updates(
    memo_app: AppHarness, page: Page
) -> None:
    """AccordionTrigger holding a stateful cond updates on state changes.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)

    expect(page.locator("#trigger-show")).to_have_text("Show")
    expect(page.locator("#trigger-hide")).to_have_count(0)

    page.click("#toggle")
    expect(page.locator("#trigger-hide")).to_have_text("Hide")
    expect(page.locator("#trigger-show")).to_have_count(0)

    # Bumping an unrelated counter must not desync the trigger render.
    page.click("#bump")
    expect(page.locator("#counter")).to_have_text("1")
    expect(page.locator("#trigger-hide")).to_have_text("Hide")

    page.click("#toggle")
    expect(page.locator("#trigger-show")).to_have_text("Show")


def _document_contains_style(page: Page, marker: str) -> bool:
    """Whether any ``<style>`` element's text content contains ``marker``.

    ``<style>`` content is not "visible" text, so the Locator ``has_text``
    filter skips it. Inspect text content via JS instead.

    Args:
        page: Playwright page.
        marker: Substring to look for in style element text content.

    Returns:
        True if any ``<style>`` element's textContent contains the marker.
    """
    return page.evaluate(
        """(marker) => {
            const els = document.querySelectorAll('style');
            return Array.from(els).some(el => (el.textContent || '').includes(marker));
        }""",
        marker,
    )


def test_page_title_updates_with_state(memo_app: AppHarness, page: Page) -> None:
    """The page title (passed to ``add_page(title=...)``) tracks state.

    Verifying via ``document.title`` proves the state value flows through the
    standard page-metadata path and lands as the title's text node, not as a
    stringified JSX component child.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)
    page.wait_for_selector("#trigger-show")

    expect(page).to_have_title("memo-title-home")

    page.click("#set-title")
    expect(page).to_have_title("memo-title-about")


def test_style_element_renders_stateful_css_as_text(
    memo_app: AppHarness, page: Page
) -> None:
    """``rx.el.style(state_var)`` writes the state value as the stylesheet text.

    Uses a unique marker substring so the test does not collide with Emotion
    or Sonner stylesheets that also live in the document.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)
    page.wait_for_selector("#trigger-show")

    assert _document_contains_style(page, "memo-css-light")
    assert not _document_contains_style(page, "memo-css-dark")

    page.click("#set-css")
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('style'))
            .some(el => (el.textContent || '').includes('memo-css-dark'))""",
        timeout=5000,
    )
    assert _document_contains_style(page, "memo-css-dark")
    assert not _document_contains_style(page, "memo-css-light")


def test_markdown_with_state_var_renders_and_updates(
    memo_app: AppHarness, page: Page
) -> None:
    """``rx.markdown(State.var)`` renders the Var as a string and tracks state.

    Mirrors the bug-report repro: static-source markdown sibling next to a
    Var-source markdown. Pre-fix, the Var-source markdown crashed
    react-markdown and prevented the whole subtree from rendering.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)

    static = page.locator("#md-static")
    expect(static.locator("em")).to_have_text("is")
    expect(static.locator("strong")).to_have_text("working")

    host = page.locator("#md-host")
    expect(host.locator("strong")).to_have_text("memo-md-home")
    expect(host).not_to_contain_text("[object Object]")

    page.click("#set-markdown")

    expect(host.locator("strong")).to_have_text("memo-md-away")
    expect(host).not_to_contain_text("[object Object]")
    expect(static.locator("strong")).to_have_text("working")


def test_as_child_slot_props_reach_memoized_input(
    memo_app: AppHarness, page: Page
) -> None:
    """Slot-injected props reach a stateful input through its memo wrapper.

    Regression for reflex-dev/reflex#6849: ``rx.form.control(..., as_child=True)``
    clones its child element and injects ``name``, ``id``, ``aria-describedby``
    and a ref onto it. When the child's props reference state, the child is an
    auto-memo wrapper — if the wrapper drops the injected props, the input
    renders unnamed and ``new FormData(form)`` omits the field entirely.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)

    field_input = page.locator("input[name='full_name']")
    expect(field_input).to_have_count(1)
    expect(field_input).to_have_value("Ada")
    assert field_input.get_attribute("id"), (
        "Slot-injected id must reach the input (validation/aria wiring)"
    )

    page.click("#form-submit")
    expect(page.locator("#form-data-out")).to_contain_text('"full_name":"Ada"')


# Semantics of ``mergeSlotProps``, asserted against the real bundled helper and
# the real ``mergician`` dependency rather than a reimplementation. Each entry
# is ``(name, js_expression)``; the expression must evaluate to ``true``, with
# ``m`` bound to ``mergeSlotProps``.
MERGE_SLOT_PROPS_CASES: list[tuple[str, str]] = [
    # An empty injection is the overwhelmingly common case (no Slot parent):
    # the own props object must come back by identity so the wrapper renders
    # exactly as it did before transparency existed.
    (
        "empty injection returns own props by identity",
        """
        const own = {a: 1};
        return m({}, own) === own && m(Object.create(null), own) === own;
        """,
    ),
    (
        "own props win over injected",
        """
        const r = m({id: "slot", type: "text"}, {id: "own"});
        return r.id === "own" && r.type === "text";
        """,
    ),
    (
        "injected-only props land on the result",
        """
        const r = m({name: "full_name", "aria-describedby": "d"}, {id: "own"});
        return r.name === "full_name" && r["aria-describedby"] === "d"
            && r.id === "own";
        """,
    ),
    (
        "injected survives an own prop that has no value",
        """
        const r = m({id: "slot", name: "n"}, {id: undefined, name: null});
        return r.id === "slot" && r.name === "n";
        """,
    ),
    # Identity stability is what keeps merging from causing renders: a composed
    # handler with a fresh identity every render would defeat a memoized root's
    # bailout and churn every effect that depends on it.
    (
        "composed handlers keep a stable identity",
        """
        const own = () => {}, inj = () => {}, other = () => {};
        const a = m({onClick: inj}, {onClick: own}).onClick;
        return a === m({onClick: inj}, {onClick: own}).onClick
            && a !== m({onClick: other}, {onClick: own}).onClick
            && a !== m({onClick: inj}, {onClick: other}).onClick;
        """,
    ),
    (
        "composed handlers run own first, then injected, with all args",
        """
        const seen = [];
        const r = m(
            {onChange: (...a) => seen.push(["i", ...a])},
            {onChange: (...a) => seen.push(["o", ...a])},
        );
        r.onChange(1, 2);
        return JSON.stringify(seen) === JSON.stringify([["o", 1, 2], ["i", 1, 2]]);
        """,
    ),
    (
        "only on+Uppercase props are treated as handlers",
        """
        const r = m({once: "inj", onedge: "inj"}, {once: "own", onedge: "own"});
        return r.once === "own" && r.onedge === "own";
        """,
    ),
    # A composed ref with a fresh identity every render would make React detach
    # and reattach the node on every render of an otherwise unchanged element.
    (
        "composed refs keep a stable identity and attach to both",
        """
        const own = {current: null};
        const seen = [];
        const inj = (n) => seen.push(n);
        const composed = m({ref: inj}, {ref: own}).ref;
        if (composed !== m({ref: inj}, {ref: own}).ref) return false;
        if (composed === m({ref: (n) => seen.push(n)}, {ref: own}).ref) return false;
        const node = {};
        const cleanup = composed(node);
        if (own.current !== node || seen[0] !== node) return false;
        cleanup();
        return own.current === null && seen[1] === null;
        """,
    ),
    (
        "callback ref cleanup returns are honored",
        """
        const log = [];
        const inj = {current: null};
        const own = () => { log.push("attach"); return () => log.push("cleanup"); };
        const cleanup = m({ref: inj}, {ref: own}).ref({});
        cleanup();
        return log.join(",") === "attach,cleanup" && inj.current === null;
        """,
    ),
    (
        "a lone ref passes through untouched",
        """
        const inj = () => {};
        const own = {current: null};
        return m({ref: inj, id: "x"}, {}).ref === inj
            && m({ref: inj}, {ref: undefined}).ref === inj
            && m({id: "x"}, {ref: own}).ref === own
            && m({id: "x", ref: null}, {ref: own}).ref === own;
        """,
    ),
    (
        "className concatenates injected then own",
        """
        return m({className: "a"}, {className: "b"}).className === "a b"
            && m({className: "a"}, {className: ""}).className === "a"
            && m({className: ""}, {className: "b"}).className === "b"
            && m({className: "a", id: 1}, {}).className === "a";
        """,
    ),
    (
        "plain object props deep-merge with own winning",
        """
        const r = m(
            {style: {color: "red", padding: 1, "&:hover": {color: "blue", margin: 2}}},
            {style: {color: "green", "&:hover": {color: "black"}}},
        );
        return r.style.color === "green" && r.style.padding === 1
            && r.style["&:hover"].color === "black"
            && r.style["&:hover"].margin === 2;
        """,
    ),
    (
        "arrays, react elements and class instances are not deep-merged",
        """
        class Cfg { constructor() { this.a = 1; } }
        const arr = [3];
        const el = {$$typeof: Symbol.for("react.element"), props: {}};
        const cfg = new Cfg();
        const r = m(
            {items: [1, 2], icon: {$$typeof: Symbol.for("react.element")},
             cfg: {a: 9, b: 9}},
            {items: arr, icon: el, cfg},
        );
        return r.items === arr && r.icon === el && r.cfg === cfg;
        """,
    ),
    (
        "mergeRefs tolerates null entries",
        """
        const r = {current: null};
        const cleanup = window.__mergeRefs(null, r, undefined)({n: 1});
        if (r.current.n !== 1) return false;
        cleanup();
        return r.current === null;
        """,
    ),
]


def test_merge_slot_props_semantics(memo_app: AppHarness, page: Page) -> None:
    """``mergeSlotProps`` follows Radix Slot semantics without churning identity.

    Exercises the shipped ``$/utils/state`` helper in the browser — with the
    real ``mergician`` dependency resolved by the app's package install —
    rather than a reimplementation, so the assertions cover what the auto-memo
    wrappers actually run.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)

    page.wait_for_function("() => typeof window.__mergeSlotProps === 'function'")
    for name, body in MERGE_SLOT_PROPS_CASES:
        result = page.evaluate(
            f"() => {{ const m = window.__mergeSlotProps;\n{body}\n}}"
        )
        assert result is True, f"mergeSlotProps case failed: {name}"


def test_slot_transparency_adds_no_rerenders(memo_app: AppHarness, page: Page) -> None:
    """Prop transparency must not re-render a wrapper any more often than before.

    Two identically memoized probes read the same state var; only one is cloned
    by a Radix ``asChild`` Slot parent, so it is the only one whose props get
    merged at runtime. Their render counts must move in lockstep: a state
    neither reads renders neither, and the state both read renders both the
    same number of times. A merge that produced fresh handler or ref identities
    every render would show up here as extra renders on the Slot-wrapped probe,
    and a churning ref would remount its node.

    Args:
        memo_app: Running app harness.
        page: Playwright page.
    """
    assert memo_app.frontend_url is not None

    # Both probes must actually compile into transparent memo wrappers —
    # otherwise the render counts below would be measuring nothing.
    wrapper_sources = "\n".join(
        path.read_text() for path in (memo_app.app_path / ".web").rglob("*.jsx")
    )
    assert wrapper_sources.count("jsx(RenderProbe,{...mergeSlotProps(rest, ({") == 2, (
        "both RenderProbe call sites must compile to transparent memo wrappers"
    )

    page.goto(memo_app.frontend_url)

    slot_probe = page.locator("[data-probe='slot']")
    plain_probe = page.locator("[data-probe='plain']")
    expect(slot_probe).to_have_attribute("data-label", "one")
    expect(plain_probe).to_have_attribute("data-label", "one")
    # The wrapper is genuinely transparent here: the Card's Slot injects its
    # own class onto the child it clones, and it merges with the probe's.
    slot_classes = (slot_probe.get_attribute("class") or "").split()
    assert "own-probe-class" in slot_classes, slot_classes
    assert [c for c in slot_classes if c != "own-probe-class"], (
        f"Slot-injected className must reach the probe: {slot_classes}"
    )

    # Tag the mounted nodes so a remount (rather than a re-render) is visible.
    page.evaluate(
        "() => document.querySelectorAll('[data-probe]')"
        ".forEach((n) => { n.__mountTag = 'mounted'; })"
    )

    def counts() -> dict[str, int]:
        return page.evaluate("() => ({...window.__probeRenders})")

    before = counts()
    assert before.get("slot"), before
    assert before.get("plain"), before

    # A state the probes do not read must not render them at all.
    page.click("#probe-unrelated")
    expect(page.locator("#unrelated-out")).to_have_text("1")
    assert counts() == before, (
        "an unrelated state change must not re-render memoized wrappers"
    )

    # The state both probes read renders both — the same number of times.
    page.click("#probe-relabel")
    expect(slot_probe).to_have_attribute("data-label", "two")
    expect(plain_probe).to_have_attribute("data-label", "two")
    after = counts()
    slot_delta = after["slot"] - before["slot"]
    plain_delta = after["plain"] - before["plain"]
    assert slot_delta >= 1, after
    assert slot_delta == plain_delta, (
        "the Slot-wrapped wrapper must not render more often than the plain "
        f"one: {after} vs {before}"
    )

    assert page.evaluate(
        "() => [...document.querySelectorAll('[data-probe]')]"
        ".every((n) => n.__mountTag === 'mounted')"
    ), "re-rendering must not remount the probe nodes"
