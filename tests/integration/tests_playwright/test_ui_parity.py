"""The rx.ui parity harness: the look and the behaviour of every component.

One production build of the generated app serves every test. A matrix test
compares the pixels, computed styles and accessibility tree of a component with
its Radix counterpart, and a contract test runs one step of a behaviour
contract against one of the two systems. Both run in whichever engines
``--browser`` names; ``scripts/ui_parity.py`` builds the command.
"""

import json
import os
import time
from collections.abc import Generator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page

from reflex.testing import AppHarness, AppHarnessProd

# The steps of a contract are plain asserts: have them explain themselves.
pytest.register_assert_rewrite("ui_parity")

from ui_parity import allowlist, report  # noqa: E402
from ui_parity.app import contract_route, parity_route  # noqa: E402
from ui_parity.components import CONTRACTS, MATRICES  # noqa: E402
from ui_parity.contract import HYDRATED, ContractError, Step, run_step  # noqa: E402
from ui_parity.look import StyleDifference, run_matrix  # noqa: E402
from ui_parity.systems import CANDIDATE, REFERENCE, SYSTEMS  # noqa: E402

# Where the report of a run goes, unless UI_PARITY_REPORT names a directory.
DEFAULT_REPORT = Path(allowlist.ALLOWLIST).parent / "report"
# How long the build and every matrix may take together, in seconds.
BUDGET = float(os.environ.get("UI_PARITY_BUDGET_SECONDS", "900"))
TIMINGS = "timings.json"

# What the runs of this module took: the build, then each matrix by engine and
# component.
_seconds: dict[str, float] = {}


def UIParityApp():
    """The generated app: a page per matrix and two per contract."""
    from ui_parity.app import create_app

    import reflex as rx

    app = create_app()  # noqa: F841

    config = rx.config.get_config()
    config.plugins = [rx.plugins.UIPlugin(), rx.plugins.TailwindV4Plugin()]
    # The badge floats over the page, and over whatever cell lies under it.
    config.show_built_with_reflex = False


@pytest.fixture(scope="module")
def parity_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Build the generated app for production and serve it.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        The running harness.
    """
    started = time.perf_counter()
    with AppHarnessProd.create(
        root=tmp_path_factory.mktemp("ui_parity_app"),
        app_name="ui_parity_app",
        app_source=UIParityApp,
    ) as harness:
        assert harness.frontend_url is not None, "app is not running"
        _seconds["build"] = time.perf_counter() - started
        yield harness


@pytest.fixture(scope="module")
def report_dir() -> Path:
    """Start a report: forget the results of the run before.

    The images stay, and are replaced as their cells run again: the directory
    is one a developer named, and may hold more than the report.

    Returns:
        The directory the report is written to.
    """
    directory = Path(os.environ.get("UI_PARITY_REPORT", DEFAULT_REPORT)).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    for name in (report.RESULTS, report.INDEX, TIMINGS):
        (directory / name).unlink(missing_ok=True)
    return directory


def _url(harness: AppHarness, route: str) -> str:
    """Get the address of a page of the app.

    Args:
        harness: The running harness.
        route: The route of the page.

    Returns:
        The address a production build serves the page at.
    """
    assert harness.frontend_url is not None
    return harness.frontend_url.rstrip("/") + route + "/"


@pytest.mark.parametrize("component", MATRICES)
def test_matrix(
    parity_app: AppHarness, browser: Browser, report_dir: Path, component: str
):
    """Every cell of a component looks like the Radix component."""
    result = run_matrix(
        browser,
        _url(parity_app, parity_route(component)),
        MATRICES[component],
        report_dir,
        allowlist.load(),
        scale=int(os.environ.get("UI_PARITY_SCALE", "1")),
    )
    index = report.write(report_dir, result)
    _seconds[f"{result.engine}/{component}"] = result.seconds
    failures = result.failures(report_dir)
    assert not failures, "\n".join([*failures, f"report: {index}"])


def _pad_candidate(page: Page) -> None:
    """Give every rx.ui element of a parity page a padding of its own.

    Args:
        page: The loaded page.
    """
    page.add_style_tag(
        content='[data-parity-system="candidate"] > * { padding: 3px !important }'
    )


def test_changed_padding_fails_the_matrix(
    parity_app: AppHarness, browser: Browser, tmp_path: Path
):
    """A box padded differently from the Radix one fails, with the numbers."""
    result = run_matrix(
        browser,
        _url(parity_app, parity_route("box")),
        MATRICES["box"],
        tmp_path,
        allowlist.Allowlist(),
        prepare=_pad_candidate,
    )
    base = result.cells[0]
    assert base.cell == "base"
    assert base.styles == [
        StyleDifference("", "height", "24px", "30px"),
        *(
            StyleDifference("", f"padding-{side}", "0px", "3px")
            for side in ("top", "right", "bottom", "left")
        ),
    ]
    assert base.a11y is None
    # The text moved by three pixels each way: its old and its new place differ.
    assert base.differing > 0
    assert base.ratio > base.tolerance
    assert base.problems[0] == (
        f"{base.differing} of {base.width * base.height} pixels differ "
        f"({base.ratio:.2%}, 0.00% allowed)"
    )
    # Every cell fails, each naming itself and its three images.
    failures = result.failures(tmp_path)
    assert [failure.splitlines()[0] for failure in failures] == [
        f"box [{result.engine}] cell {cell.cell}:" for cell in result.cells
    ]
    directory = tmp_path / result.engine / "box"
    assert failures[0].splitlines()[-1] == (
        f"  images: {directory}/base.{{reference,candidate,diff}}.png"
    )
    assert sorted(path.name for path in directory.iterdir()) == sorted(
        f"{cell.cell}.{kind}.png"
        for cell in result.cells
        for kind in ("reference", "candidate", "diff")
    )


def _name_candidate(page: Page) -> None:
    """Give every rx.ui element of a parity page a role the Radix one lacks.

    Args:
        page: The loaded page.
    """
    page.evaluate(
        """() => {
            for (const element of document.querySelectorAll(
                '[data-parity-system="candidate"] > *',
            )) {
                element.setAttribute("role", "note");
            }
        }"""
    )


def test_changed_role_fails_the_matrix(
    parity_app: AppHarness, browser: Browser, tmp_path: Path
):
    """A box the accessibility tree describes differently fails, once per element."""
    result = run_matrix(
        browser,
        _url(parity_app, parity_route("box")),
        MATRICES["box"],
        tmp_path,
        allowlist.Allowlist(),
        prepare=_name_candidate,
    )
    trees = ("The quick brown fox", "- note: The quick brown fox")
    assert {cell.cell: cell.a11y for cell in result.cells} == {
        "base": trees,
        "style-padding": trees,
        "style-border": trees,
        "custom-attrs-focusable": trees,
        # The same elements as above, in another environment.
        "base@dark": None,
        "base@hover": None,
        "base@520": None,
        "custom-attrs-focusable@focus-visible": None,
    }
    assert result.cells[0].problems == [
        (
            "accessibility tree: rx 'The quick brown fox', "
            "rx.ui '- note: The quick brown fox'"
        )
    ]


CONTRACT_STEPS = [
    pytest.param(component, system, step, id=f"{component}-{system.name}-{step.name}")
    for component, contract in CONTRACTS.items()
    for system in SYSTEMS
    for step in contract.steps
]


@pytest.mark.parametrize(("component", "system", "step"), CONTRACT_STEPS)
def test_contract(parity_app: AppHarness, browser: Browser, component, system, step):
    """A step of a component's contract passes, or is listed as a difference."""
    run_step(
        browser,
        _url(parity_app, contract_route(component, system)),
        CONTRACTS[component],
        system,
        step,
        allowlist.load(),
    )


def _fail(run) -> None:
    """Fail a step: the box is not what the step says it is.

    Args:
        run: The run of the step.
    """
    assert run.page.locator("#box").inner_text() == "something else"


def test_contract_failure_names_what_failed(parity_app: AppHarness, browser: Browser):
    """A failing step names the component, the system, the engine and itself."""
    engine = browser.browser_type.name
    contract = CONTRACTS["box"]
    url = _url(parity_app, contract_route("box", CANDIDATE))
    step = Step("says something else", _fail, on=HYDRATED)
    with pytest.raises(ContractError) as failure:
        run_step(browser, url, contract, CANDIDATE, step, allowlist.Allowlist())
    assert str(failure.value) == (
        f'box [rx.ui, {engine}] step "says something else" failed: '
        "AssertionError: assert 'content' == 'something else'\n"
        "  \n  - something else\n  + content"
    )

    # Listed as a difference of rx.ui in this engine, the failure passes, and
    # the same step of the Radix component is not excused by it.
    entry = allowlist.ContractEntry(
        component="box",
        step="says something else",
        system=CANDIDATE.name,
        engines=(engine,),
        reason="The box says what it was given.",
    )
    listed = allowlist.Allowlist(contract=(entry,))
    run_step(browser, url, contract, CANDIDATE, step, listed)
    with pytest.raises(ContractError):
        run_step(
            browser,
            _url(parity_app, contract_route("box", REFERENCE)),
            contract,
            REFERENCE,
            step,
            listed,
        )

    # A listed difference that is none any more fails until it is removed.
    stale = allowlist.Allowlist(
        contract=(
            allowlist.ContractEntry(
                component="box",
                step=contract.steps[0].name,
                system=CANDIDATE.name,
                engines=(),
                reason="It used to warn.",
            ),
        )
    )
    with pytest.raises(ContractError) as failure:
        run_step(browser, url, contract, CANDIDATE, contract.steps[0], stale)
    assert str(failure.value) == (
        f'box [rx.ui, {engine}] step "hydrates with no warnings" passes, but '
        'allowlist.toml says it does not ("It used to warn."). Remove the entry.'
    )


def test_run_time_is_within_budget(report_dir: Path):
    """The build and the matrices of the run fit the budget, and are recorded."""
    total = sum(_seconds.values())
    (report_dir / TIMINGS).write_text(
        json.dumps(
            {
                "budget": BUDGET,
                "total": round(total, 3),
                "seconds": {name: round(value, 3) for name, value in _seconds.items()},
            },
            indent=2,
        )
        + "\n"
    )
    assert total <= BUDGET, (
        f"The parity run took {total:.0f} s, over its budget of {BUDGET:.0f} s: "
        f"{_seconds}. Cross fewer dimensions and sweep the rest."
    )
