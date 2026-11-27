"""Tests for the contract declaration that need no browser."""

import pytest
from ui_parity.contract import (
    HYDRATED,
    HYDRATION_STEP,
    NO_JAVASCRIPT,
    SERVER,
    Contract,
    Run,
    ServerElement,
    ServerHtml,
)
from ui_parity.systems import CANDIDATE

DOCUMENT = ServerHtml(
    '<!DOCTYPE html><html><body><main><div id="a" class="x y">before'
    '<span id="inner">in<br>side</span><img src="i.png"> after</div>'
    '<input id="field" disabled value="v"><p>outside</p></main></body></html>'
)


def test_server_html_finds_an_element_and_its_text():
    assert DOCUMENT.element("a") == ServerElement(
        tag="div", attributes={"id": "a", "class": "x y"}, text="beforeinside after"
    )
    assert DOCUMENT.element("inner") == ServerElement(
        tag="span", attributes={"id": "inner"}, text="inside"
    )
    # An element that cannot hold text does not take what follows it.
    assert DOCUMENT.element("field") == ServerElement(
        tag="input", attributes={"id": "field", "disabled": None, "value": "v"}
    )


def test_server_html_fails_for_an_element_the_server_did_not_render():
    with pytest.raises(AssertionError) as error:
        DOCUMENT.element("missing")
    assert str(error.value) == 'the server HTML has no element with id "missing"'


def test_contract_starts_with_the_hydration_step_and_keeps_declared_order():
    contract = Contract(component="switch", render=lambda namespace: None)

    @contract.step("is a checkbox in the server render", on=SERVER)
    def server(run: Run) -> None: ...

    @contract.step("is checked with JavaScript disabled", on=NO_JAVASCRIPT)
    def without_javascript(run: Run) -> None: ...

    @contract.step("Space toggles")
    def space(run: Run) -> None: ...

    assert [(step.name, step.on) for step in contract.steps] == [
        (HYDRATION_STEP, HYDRATED),
        ("is a checkbox in the server render", SERVER),
        ("is checked with JavaScript disabled", NO_JAVASCRIPT),
        ("Space toggles", HYDRATED),
    ]
    assert [step.check for step in contract.steps[1:]] == [
        server,
        without_javascript,
        space,
    ]
    # Each contract has steps of its own.
    assert len(Contract(component="box", render=lambda namespace: None).steps) == 1


def test_contract_rejects_a_duplicate_step_and_an_unknown_page():
    contract = Contract(component="switch", render=lambda namespace: None)
    with pytest.raises(ValueError) as error:
        contract.step(HYDRATION_STEP)
    assert str(error.value) == (
        'switch: two steps are named "hydrates with no warnings".'
    )
    with pytest.raises(ValueError) as error:
        contract.step("works offline", on="offline")
    assert str(error.value) == "switch: a step cannot run on 'offline'."


def test_hydration_step_fails_on_what_the_browser_reported():
    (step,) = Contract(component="box", render=lambda namespace: None).steps
    run = Run(component="box", system=CANDIDATE, engine="chromium", server=DOCUMENT)
    step.check(run)
    run.problems.append("console error: Minified React error #418")
    with pytest.raises(AssertionError):
        step.check(run)


def test_server_step_has_no_page():
    run = Run(component="box", system=CANDIDATE, engine="chromium", server=DOCUMENT)
    with pytest.raises(RuntimeError) as error:
        run.page
    assert str(error.value) == (
        "A step on 'server' has no page: read run.server instead."
    )
