"""The behaviour contract of a component, and how a step of it runs.

A contract is declared once and runs against the Radix component and the rx.ui
one, in every browser engine. A step runs on a page of its own, so one failure
never causes the next, and a failure names the component, the system, the
engine and the step.
"""

from __future__ import annotations

import dataclasses
import urllib.request
from collections.abc import Callable
from html.parser import HTMLParser
from typing import Any

from playwright.sync_api import Browser, ConsoleMessage, Page

from ui_parity.allowlist import Allowlist
from ui_parity.hydration import IS_HYDRATED
from ui_parity.systems import System

# What a step runs on: the HTML the server sent, the page with scripts off,
# or the page once React has hydrated it.
SERVER = "server"
NO_JAVASCRIPT = "no-javascript"
HYDRATED = "hydrated"

# The step every contract has without declaring it.
HYDRATION_STEP = "hydrates with no warnings"

VIEWPORT = {"width": 1280, "height": 720}

# Elements that have no end tag, so they never hold another.
_VOID = frozenset({
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
})


class ContractError(AssertionError):
    """A step of a contract did not go as the contract and allowlist say."""


@dataclasses.dataclass
class ServerElement:
    """An element of the HTML the server sent.

    Attributes:
        tag: The name of the element.
        attributes: Its attributes.
        text: The text of the element and of everything inside it.
    """

    tag: str
    attributes: dict[str, str | None]
    text: str = ""


class _ElementFinder(HTMLParser):
    """Find the element with an id, and collect its text."""

    def __init__(self, element_id: str):
        """Start a search.

        Args:
            element_id: The id of the element to find.
        """
        super().__init__()
        self.element_id = element_id
        self.found: ServerElement | None = None
        # How many elements are open inside the found one, itself included.
        self.depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        """Enter an element.

        Args:
            tag: The name of the element.
            attrs: Its attributes.
        """
        if self.depth:
            self.depth += tag not in _VOID
        elif self.found is None and dict(attrs).get("id") == self.element_id:
            self.found = ServerElement(tag=tag, attributes=dict(attrs))
            self.depth = int(tag not in _VOID)

    def handle_endtag(self, tag: str):
        """Leave an element.

        Args:
            tag: The name of the element.
        """
        if self.depth and tag not in _VOID:
            self.depth -= 1

    def handle_data(self, data: str):
        """Read text.

        Args:
            data: The text.
        """
        if self.depth and self.found is not None:
            self.found.text += data


@dataclasses.dataclass(frozen=True)
class ServerHtml:
    """The document the server sent for a page, before any script ran.

    Attributes:
        text: The HTML.
    """

    text: str

    def element(self, element_id: str) -> ServerElement:
        """Find an element by its id.

        Args:
            element_id: The id of the element.

        Returns:
            The element.

        Raises:
            AssertionError: If the server did not render the element.
        """
        finder = _ElementFinder(element_id)
        finder.feed(self.text)
        if finder.found is None:
            msg = f'the server HTML has no element with id "{element_id}"'
            raise AssertionError(msg)
        return finder.found


@dataclasses.dataclass
class Run:
    """What a step works with.

    Attributes:
        component: The component under contract.
        system: The system the component is of.
        engine: The browser engine of the page.
        server: The HTML the server sent for the page.
        problems: What the browser reported while the page loaded and the
            step ran: console warnings and errors, and uncaught exceptions.
        _page: The page, or None for a step that runs on the server HTML.
    """

    component: str
    system: System
    engine: str
    server: ServerHtml
    problems: list[str] = dataclasses.field(default_factory=list)
    _page: Page | None = None

    @property
    def page(self) -> Page:
        """The page the step drives.

        Returns:
            The page, showing the component.

        Raises:
            RuntimeError: If the step runs on the server HTML, where no page
                is open.
        """
        if self._page is None:
            msg = f"A step on {SERVER!r} has no page: read run.server instead."
            raise RuntimeError(msg)
        return self._page


@dataclasses.dataclass(frozen=True)
class Step:
    """One requirement of a contract.

    Attributes:
        name: What the component must do, as a failure reports it.
        check: Drives the page and asserts.
        on: What the step runs on: SERVER, NO_JAVASCRIPT or HYDRATED.
    """

    name: str
    check: Callable[[Run], None]
    on: str = HYDRATED


def _no_problems(run: Run) -> None:
    """Assert that hydrating the page reported nothing.

    Args:
        run: The run, on a hydrated page.
    """
    assert run.problems == []


@dataclasses.dataclass
class Contract:
    """The behaviour both systems' component must show.

    Attributes:
        component: The name both namespaces know the component by.
        render: Create what the contract page shows from a namespace, ``rx``
            or ``rx.ui``.
        steps: The requirements, in the order declared.
    """

    component: str
    render: Callable[[Any], Any]
    steps: list[Step] = dataclasses.field(
        default_factory=lambda: [Step(HYDRATION_STEP, _no_problems)]
    )

    def step(
        self, name: str, on: str = HYDRATED
    ) -> Callable[[Callable[[Run], None]], Callable[[Run], None]]:
        """Declare a step.

        Args:
            name: What the component must do.
            on: What the step runs on: SERVER, NO_JAVASCRIPT or HYDRATED.

        Returns:
            A decorator that adds the function as the step's check.

        Raises:
            ValueError: If the contract already has a step of that name, or
                the step runs on something unknown.
        """
        if on not in (SERVER, NO_JAVASCRIPT, HYDRATED):
            msg = f"{self.component}: a step cannot run on {on!r}."
            raise ValueError(msg)
        if any(step.name == name for step in self.steps):
            msg = f'{self.component}: two steps are named "{name}".'
            raise ValueError(msg)

        def declare(check: Callable[[Run], None]) -> Callable[[Run], None]:
            self.steps.append(Step(name=name, check=check, on=on))
            return check

        return declare


def _record(problems: list[str], message: ConsoleMessage) -> None:
    """Keep a console message that reports a problem.

    Args:
        problems: Where the problems of the page are collected.
        message: The message.
    """
    if message.type in ("warning", "error"):
        problems.append(f"console {message.type}: {message.text}")


def _check(
    browser: Browser, url: str, contract: Contract, system: System, step: Step
) -> None:
    """Run the check of a step on a page of its own.

    Args:
        browser: The browser to open the page in.
        url: The address of the contract page.
        contract: The contract the step belongs to.
        system: The system the page renders the component of.
        step: The step.
    """
    with urllib.request.urlopen(url) as response:
        server = ServerHtml(response.read().decode())
    run = Run(
        component=contract.component,
        system=system,
        engine=browser.browser_type.name,
        server=server,
    )
    if step.on == SERVER:
        step.check(run)
        return
    context = browser.new_context(
        viewport=VIEWPORT,  # pyright: ignore[reportArgumentType]
        java_script_enabled=step.on == HYDRATED,
    )
    try:
        page = run._page = context.new_page()
        page.on("console", lambda message: _record(run.problems, message))
        page.on("pageerror", lambda error: run.problems.append(f"error: {error}"))
        page.goto(url)
        if step.on == HYDRATED:
            page.wait_for_function(IS_HYDRATED)
        step.check(run)
    finally:
        context.close()


def run_step(
    browser: Browser,
    url: str,
    contract: Contract,
    system: System,
    step: Step,
    allowlist: Allowlist,
) -> None:
    """Run one step against one system, and hold it to the allowlist.

    Args:
        browser: The browser to run in.
        url: The address of the contract page of the system.
        contract: The contract the step belongs to.
        system: The system under contract.
        step: The step.
        allowlist: The intended differences.

    Raises:
        ContractError: If the step fails, or passes although the allowlist
            says the system does not pass it.
    """
    engine = browser.browser_type.name
    where = f'{contract.component} [{system.name}, {engine}] step "{step.name}"'
    allowed = next(
        (
            entry
            for entry in allowlist.contract
            if entry.covers(contract.component, step.name, system.name, engine)
        ),
        None,
    )
    try:
        _check(browser, url, contract, system, step)
    except Exception as error:
        if allowed is not None:
            return
        msg = f"{where} failed: {type(error).__name__}: {error}"
        raise ContractError(msg) from error
    if allowed is not None:
        msg = (
            f"{where} passes, but allowlist.toml says it does not "
            f'("{allowed.reason}"). Remove the entry.'
        )
        raise ContractError(msg)
