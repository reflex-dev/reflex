"""Compare the look of a component's matrix between the two systems.

Each pass loads the parity page once under one viewport and color scheme. The
cells at rest are read from a single screenshot and a single script call; a
cell in an interactive state is driven through the pointer or the keyboard, one
element at a time. Both systems are cropped by the same rectangle relative to
their frame, so two equal renderings give equal images.
"""

from __future__ import annotations

import dataclasses
import io
import re
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from PIL import Image
from playwright.sync_api import Browser, Locator, Page

from ui_parity.allowlist import Allowlist, LookEntry
from ui_parity.diff import diff_images
from ui_parity.hydration import IS_HYDRATED, NOT_RENDERED
from ui_parity.matrix import ACTIVE, FOCUS_VISIBLE, HOVER, REST, Cell, Matrix, Selector
from ui_parity.systems import CANDIDATE, REFERENCE, SYSTEMS, System

# The height of the viewport, which no cell depends on: screenshots are of the
# whole page.
VIEWPORT_HEIGHT = 800

# The space left above a frame the page is scrolled to, in CSS pixels.
GAP = 8

# The tallest screenshot taken at once, in CSS pixels. Browsers cap the size of
# a capture, so a long page is read in bands.
BAND = 8000

# Nothing may still be moving when a pixel or a computed value is read.
FREEZE_CSS = """
*, *::before, *::after {
    transition: none !important;
    animation-duration: 0s !important;
    animation-delay: 0s !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
}
"""


def use_fonts(text: str, code: str) -> Callable[[Page], None]:
    """Make a page render both systems in other fonts than the theme's.

    A look that only matches in the fonts of one machine is not the same
    look: the box of a line follows the metrics of its font.

    Args:
        text: The font family of everything but code.
        code: The font family of ``code``, ``kbd`` and ``pre``.

    Returns:
        The ``prepare`` of ``run_matrix`` that sets the fonts.
    """
    css = (
        f'* {{ font-family: "{text}" !important; }}\n'
        f'code, code *, kbd, kbd *, pre, pre * {{ font-family: "{code}" !important; }}'
    )

    def prepare(page: Page) -> None:
        page.add_style_tag(content=css)
        page.evaluate("document.fonts.ready")

    return prepare


# Resolves once the page is hydrated, in the color scheme asked for, with its
# fonts loaded.
READY_SCRIPT = f"""async (appearance) => {{
    if (
        !{IS_HYDRATED}
        || !document.documentElement.classList.contains(appearance)
    ) {{
        return false;
    }}
    await document.fonts.ready;
    return document.fonts.status === "loaded";
}}"""

# How long nothing may change in a page before it is read, in milliseconds.
# The fallback of the avatar of Radix Themes fills in some 250 milliseconds
# after the page is hydrated on a busy machine, with no change in between.
SETTLE_MS = 500

# Resolves once nothing in the page has changed for that long: a component
# may still be rebuilt after the page is flagged as hydrated, and what is
# inside an element is read as well as the element.
SETTLED_SCRIPT = """(quiet) => new Promise((resolve) => {
    let timer = setTimeout(done, quiet);
    const observer = new MutationObserver(() => {
        clearTimeout(timer);
        timer = setTimeout(done, quiet);
    });
    function done() {
        observer.disconnect();
        resolve(true);
    }
    observer.observe(document.body, {
        subtree: true, childList: true, attributes: true, characterData: true,
    });
})"""

# The first element of a frame that renders: not a style tag a library left
# beside the component.
_FIRST_RENDERED = ":scope > " + "".join(f":not({tag})" for tag in NOT_RENDERED)

# Where the styles of a frame keep the shape of its element: how many element
# children it and each element inside it have, by the path of the element.
SHAPE = "(shape)"

# Reads the geometry and the computed style of the frames: all of them, or the
# one of a system and props id.
READ_SCRIPT = """({properties, targets, parts, only, matches, first, notRendered, shapeKey}) => {
    const read = (element) => {
        const style = getComputedStyle(element);
        return Object.fromEntries(
            properties.map((name) => [name, style.getPropertyValue(name)]),
        );
    };
    const box = (element) => {
        const rect = element.getBoundingClientRect();
        return [
            rect.left + window.scrollX,
            rect.top + window.scrollY,
            rect.width,
            rect.height,
        ];
    };
    const selector = only === null
        ? "[data-parity-stage]"
        : `[data-parity-stage="${only.id}"][data-parity-system="${only.system}"]`;
    return Array.from(document.querySelectorAll(selector), (stage) => {
        const system = stage.dataset.paritySystem;
        const target = stage.querySelector(targets[system] ?? first);
        const styles = {};
        const missing = [];
        const named = new Set();
        for (const [name, selectors] of Object.entries(parts)) {
            const part = stage.querySelector(selectors[system]);
            if (part === null) {
                missing.push(name);
            } else {
                styles[name] = read(part);
                named.add(part);
            }
        }
        // The elements inside the target, by the path of their places among
        // the element children: "> 2 > 1". The shape says how many each has
        // and what it is, which decides the ones of the two systems that
        // correspond.
        const shape = {};
        const walk = (element, path) => {
            const children = Array.from(element.children).filter(
                (child) => !child.matches(notRendered),
            );
            shape[path] = `${children.length} ${element.localName}`;
            children.forEach((child, index) => {
                const place = `${path}${path && " "}> ${index + 1}`;
                if (!named.has(child)) styles[place] = read(child);
                walk(child, place);
            });
        };
        if (target === null) {
            missing.push("target");
        } else {
            styles[""] = read(target);
            walk(target, "");
            styles[shapeKey] = shape;
        }
        return {
            id: stage.dataset.parityStage,
            system,
            stage: box(stage),
            target: target === null ? null : box(target),
            styles,
            missing,
            matched: matches === null || (target !== null && target.matches(matches)),
            view: [window.scrollX, window.scrollY, window.innerWidth, window.innerHeight],
        };
    });
}"""

# A frame in an ARIA snapshot: its name, then its text when it holds only text.
# Scrolls a frame to the top of the viewport, and reports where the page ended
# up.
_SCROLL_SCRIPT = """(top) => {
    window.scrollTo(0, top);
    return [window.scrollX, window.scrollY];
}"""

_GROUP = re.compile(r'( *)- group "(reference|candidate):([^"]*)"(?:: (.+)|:)?')


class CaptureError(RuntimeError):
    """The page could not be put in the condition a cell asks for."""


Point = tuple[float, float]
# Left, top, width and height, in CSS pixels.
Clip = tuple[float, float, float, float]


@dataclasses.dataclass(frozen=True)
class State:
    """How an element is put in an interactive state, and taken out of it.

    A driver is called with the page, the element, and the middle of the
    element in the viewport, which the page is scrolled to show.

    Attributes:
        enter: Drives the page so the element is in the state.
        leave: Undoes it. Without one the page is loaded again.
        matches: A selector the element must match once in the state, which
            fails the run rather than comparing two elements at rest.
    """

    enter: Callable[[Page, Locator, Point], None]
    leave: Callable[[Page, Locator, Point], None] | None = None
    matches: str | None = None


def _hover(page: Page, target: Locator, point: Point) -> None:
    """Put the pointer on an element.

    Args:
        page: The page.
        target: The element.
        point: The middle of the element.
    """
    page.mouse.move(*point)


def _unhover(page: Page, target: Locator, point: Point) -> None:
    """Move the pointer off every frame.

    Args:
        page: The page.
        target: The element that was hovered.
        point: The middle of the element.
    """
    page.mouse.move(0, 0)


def _focus(page: Page, target: Locator, point: Point) -> None:
    """Focus an element as the keyboard does.

    Args:
        page: The page.
        target: The element.
        point: The middle of the element.
    """
    # A key press makes the keyboard the page's input, so the focus that
    # follows shows its ring.
    page.keyboard.press("Tab")
    target.focus()


def _blur(page: Page, target: Locator, point: Point) -> None:
    """Take the focus off an element.

    Args:
        page: The page.
        target: The element that was focused.
        point: The middle of the element.
    """
    target.blur()


def _press(page: Page, target: Locator, point: Point) -> None:
    """Hold the pointer down on an element.

    Args:
        page: The page.
        target: The element.
        point: The middle of the element.
    """
    page.mouse.move(*point)
    page.mouse.down()


def _release(page: Page, target: Locator, point: Point) -> None:
    """Release the pointer away from an element, so it is never clicked.

    Args:
        page: The page.
        target: The element that was pressed.
        point: The middle of the element.
    """
    page.mouse.move(0, 0)
    page.mouse.up()
    # Dragging off the element selected its text.
    page.evaluate("() => getSelection().removeAllRanges()")


# The states the runner drives.
STATES: Mapping[str, State] = {
    HOVER: State(enter=_hover, leave=_unhover, matches=":hover"),
    FOCUS_VISIBLE: State(enter=_focus, leave=_blur, matches=":focus-visible"),
    ACTIVE: State(enter=_press, leave=_release, matches=":active"),
}


@dataclasses.dataclass(frozen=True)
class StyleDifference:
    """A computed property the two systems disagree on.

    Attributes:
        part: The inner element it was read from, or the empty string for the
            element itself.
        property: The CSS property.
        reference: Its computed value on the Radix component.
        candidate: Its computed value on the rx.ui component.
    """

    part: str
    property: str
    reference: str | None
    candidate: str | None


@dataclasses.dataclass
class CellResult:
    """How one cell compared.

    Attributes:
        cell: The id of the cell.
        width: The width of the compared images, in device pixels.
        height: The height of the compared images, in device pixels.
        differing: The pixels that differ, anti-aliasing left out.
        antialiased: The differing pixels set aside as anti-aliasing.
        tolerance: The share of the pixels that may differ.
        styles: The computed properties that differ.
        a11y: The accessibility tree of the reference and of the candidate
            when they differ, or None.
        allowed: The reasons of the allowlist entries that excused a
            difference of the cell.
        images: The files of the reference, the candidate and the diff,
            relative to the report.
        pixels_allowed: Whether the allowlist excuses the pixels.
        skipped: The elements whose insides were not compared, because the
            two systems build them differently, and how.
    """

    cell: str
    width: int
    height: int
    differing: int
    antialiased: int
    tolerance: float
    styles: list[StyleDifference]
    a11y: tuple[str, str] | None
    allowed: list[str]
    images: dict[str, str]
    pixels_allowed: bool = False
    skipped: list[str] = dataclasses.field(default_factory=list)

    @property
    def ratio(self) -> float:
        """The share of the cell's pixels that differ.

        Returns:
            The differing pixels over all pixels, from 0 to 1.
        """
        return self.differing / (self.width * self.height)

    @property
    def problems(self) -> list[str]:
        """Describe what fails the cell.

        Returns:
            A line for the pixels, one per computed property and one for the
            accessibility tree, or nothing when the cell passes.
        """
        problems = []
        if self.ratio > self.tolerance and not self.pixels_allowed:
            problems.append(
                f"{self.differing} of {self.width * self.height} pixels differ "
                f"({self.ratio:.2%}, {self.tolerance:.2%} allowed)"
            )
        problems.extend(
            f"{difference.part + ' ' if difference.part else ''}"
            f"{difference.property}: rx {difference.reference!r}, "
            f"rx.ui {difference.candidate!r}"
            for difference in self.styles
        )
        if self.a11y is not None:
            problems.append(
                f"accessibility tree: rx {self.a11y[0]!r}, rx.ui {self.a11y[1]!r}"
            )
        return problems


@dataclasses.dataclass
class MatrixResult:
    """How the matrix of a component compared in one engine.

    Attributes:
        component: The component.
        engine: The browser engine.
        cells: The result of each cell, in the order of the matrix.
        seconds: How long the run took.
        passes: How many times the page was loaded.
        stale: Allowlist entries of the component no difference matched.
    """

    component: str
    engine: str
    cells: list[CellResult]
    seconds: float
    passes: int
    stale: list[LookEntry]

    def failures(self, report: Path) -> list[str]:
        """Describe everything that fails the matrix.

        Args:
            report: The directory the images were written to.

        Returns:
            For each failing cell: the cell, each difference with its size,
            and where its images are. Then each stale allowlist entry.
        """
        failures = []
        for result in self.cells:
            if problems := result.problems:
                # The three images differ by their last name but one.
                images = report / result.images["diff"].replace(
                    ".diff.", ".{reference,candidate,diff}."
                )
                failures.append(
                    f"{self.component} [{self.engine}] cell {result.cell}:\n"
                    + "".join(f"  - {problem}\n" for problem in problems)
                    + f"  images: {images}"
                )
        failures.extend(
            f"{self.component} [{self.engine}]: nothing differs as the "
            f"allowlist.toml entry says ({entry.check}, cells {entry.cells!r}: "
            f'"{entry.reason}"). Remove the entry.'
            for entry in self.stale
        )
        return failures


def _per_system(selector: Selector | None) -> dict[str, str | None]:
    """Spread a selector over the systems.

    Args:
        selector: One selector for both systems, one for each, or None.

    Returns:
        The selector of each system, by role.
    """
    if selector is None or isinstance(selector, str):
        return {REFERENCE.role: selector, CANDIDATE.role: selector}
    return {REFERENCE.role: selector[0], CANDIDATE.role: selector[1]}


def split_a11y(snapshot: str) -> dict[tuple[str, str], str]:
    """Split the accessibility tree of a parity page by frame.

    Args:
        snapshot: The ARIA snapshot of the page, where each frame is a group
            named after its system and props id.

    Returns:
        The tree inside each frame, by system role and props id.
    """
    trees: dict[tuple[str, str], list[str]] = {}
    current: list[str] | None = None
    # What every line inside the current frame starts with.
    inside = ""
    for line in snapshot.splitlines():
        if match := _GROUP.fullmatch(line):
            current = trees.setdefault((match[2], match[3]), [])
            inside = match[1] + "  "
            if match[4] is not None:
                current.append(match[4])
        elif current is not None and line.startswith(inside):
            current.append(line.removeprefix(inside))
        else:
            current = None
    return {key: "\n".join(lines) for key, lines in trees.items()}


def _crop(
    matrix: Matrix, reference: dict[str, Any], candidate: dict[str, Any]
) -> tuple[int, int, int, int]:
    """Choose the rectangle of a frame that is compared.

    Args:
        matrix: The matrix.
        reference: What the page reported of the reference frame.
        candidate: What the page reported of the candidate frame.

    Returns:
        Left, top, right and bottom, in CSS pixels from the frame's corner:
        the same for both systems.
    """
    width, height = matrix.stage
    if matrix.crop == "stage":
        return (0, 0, width, height)
    left, top, right, bottom = width, height, 0, 0
    for frame in (reference, candidate):
        x, y, w, h = (
            frame["target"][0] - frame["stage"][0],
            frame["target"][1] - frame["stage"][1],
            frame["target"][2],
            frame["target"][3],
        )
        left, top = min(left, x), min(top, y)
        right, bottom = max(right, x + w), max(bottom, y + h)
    return (
        max(int(left) - matrix.margin, 0),
        max(int(top) - matrix.margin, 0),
        min(-int(-right // 1) + matrix.margin, width),
        min(-int(-bottom // 1) + matrix.margin, height),
    )


def _unmatched(
    reference: dict[str, dict[str, str]], candidate: dict[str, dict[str, str]]
) -> dict[str, str]:
    """Find the elements whose insides the two systems build differently.

    The elements inside the compared one correspond while each has as many
    element children in one system as in the other. Where it does not, what
    is inside it cannot be told apart and is not compared.

    Args:
        reference: The computed properties of the reference, by part.
        candidate: The computed properties of the candidate, by part.

    Returns:
        Why what is inside an element is not compared, by the path of the
        element: the empty string for the compared element itself.
    """
    ours, theirs = reference.get(SHAPE, {}), candidate.get(SHAPE, {})
    unmatched: dict[str, str] = {}
    # A parent before what is inside it.
    for path in sorted(ours.keys() & theirs.keys(), key=lambda path: path.count(">")):
        if any(_inside(path, root) for root in unmatched):
            continue
        (count, tag), (their_count, _) = ours[path].split(), theirs[path].split()
        if count != their_count:
            unmatched[path] = (
                f"inside {_describe_path(path, tag)}: rx has {count} element "
                f"children, rx.ui {their_count}"
            )
    return unmatched


def _inside(path: str, root: str) -> bool:
    """Tell whether a path is of an element inside another.

    Args:
        path: The path of the element.
        root: The path of the other, the empty string for the compared element.

    Returns:
        Whether the element is below the other.
    """
    return path.startswith(f"{root} > " if root else "> ")


def _describe_path(path: str, tag: str) -> str:
    """Name an element inside the compared one.

    Args:
        path: Its path, the empty string for the compared element.
        tag: Its tag in the reference.

    Returns:
        The name differences and skipped elements are reported under.
    """
    return f"{path} <{tag}>" if path else f"<{tag}>"


def _style_differences(
    reference: dict[str, dict[str, str]], candidate: dict[str, dict[str, str]]
) -> list[StyleDifference]:
    """Compare the computed styles of two frames.

    The element, its named parts, and every element inside it that
    corresponds to one of the other system are compared.

    Args:
        reference: The computed properties of the reference, by part.
        candidate: The computed properties of the candidate, by part.

    Returns:
        The properties that differ, a missing part as a property of its own.
    """
    unmatched = _unmatched(reference, candidate)
    tags = reference.get(SHAPE, {})
    differences = []
    for part in sorted({*reference, *candidate} - {SHAPE}):
        ours, theirs = reference.get(part), candidate.get(part)
        name = part
        if part.startswith(">"):
            # Not one a system names as a part, nor inside what differs in shape.
            if (
                ours is None
                or theirs is None
                or any(_inside(part, root) for root in unmatched)
            ):
                continue
            name = _describe_path(part, tags[part].split()[1])
        if ours is None or theirs is None:
            differences.append(
                StyleDifference(
                    part=name,
                    property="(element)",
                    reference=None if ours is None else "present",
                    candidate=None if theirs is None else "present",
                )
            )
            continue
        differences.extend(
            StyleDifference(name, property_, value, theirs[property_])
            for property_, value in ours.items()
            if theirs[property_] != value
        )
    return differences


class _Pass:
    """One load of a parity page, under one viewport and color scheme."""

    def __init__(
        self,
        browser: Browser,
        url: str,
        matrix: Matrix,
        viewport: int,
        appearance: str,
        scale: int,
        prepare: Callable[[Page], None] | None,
    ):
        """Open the page.

        Args:
            browser: The browser.
            url: The address of the parity page.
            matrix: The matrix of the page.
            viewport: The width of the page, in CSS pixels.
            appearance: The color scheme of the page.
            scale: The device pixels per CSS pixel.
            prepare: Called with the page once it is ready, before it is read.
        """
        self.url = url
        self.matrix = matrix
        self.appearance = appearance
        self.scale = scale
        self.prepare = prepare
        self.context = browser.new_context(
            viewport={"width": viewport, "height": VIEWPORT_HEIGHT},
            device_scale_factor=scale,
            color_scheme=appearance,  # pyright: ignore[reportArgumentType]
            reduced_motion="reduce",
        )
        self.page = self.context.new_page()
        self.load()

    def load(self) -> None:
        """Load the page and wait until it is still."""
        self.page.goto(self.url)
        self.page.wait_for_function(READY_SCRIPT, arg=self.appearance)
        self.page.evaluate(SETTLED_SCRIPT, SETTLE_MS)
        self.page.add_style_tag(content=FREEZE_CSS)
        if self.prepare is not None:
            self.prepare(self.page)

    def read(
        self, only: tuple[str, System] | None = None, matches: str | None = None
    ) -> list[dict[str, Any]]:
        """Read the geometry and computed style of the frames.

        Args:
            only: The props id and system of the one frame to read, or None
                for every frame.
            matches: A selector to test each frame's element against.

        Returns:
            What the page reported of each frame.

        Raises:
            CaptureError: If a frame lacks the element the matrix names.
        """
        frames = self.page.evaluate(
            READ_SCRIPT,
            {
                "properties": self.matrix.properties,
                "targets": _per_system(self.matrix.target),
                "parts": {
                    name: _per_system(selector)
                    for name, selector in self.matrix.parts.items()
                },
                "only": None
                if only is None
                else {"id": only[0], "system": only[1].role},
                "matches": matches,
                "first": _FIRST_RENDERED,
                "notRendered": ",".join(NOT_RENDERED),
                "shapeKey": SHAPE,
            },
        )
        for frame in frames:
            if "target" in frame["missing"]:
                msg = (
                    f"{self.matrix.component}: the {frame['system']} frame of "
                    f"{frame['id']} has no element to compare."
                )
                raise CaptureError(msg)
        return frames

    def shoot(
        self, clip: tuple[float, float, float, float], full_page: bool = True
    ) -> Image.Image:
        """Take a screenshot of a rectangle of the page.

        Args:
            clip: Left, top, width and height, in CSS pixels.
            full_page: Whether the rectangle is given from the corner of the
                document, wherever the page is scrolled to, rather than from
                the corner of the viewport. Slower the longer the page is.

        Returns:
            The image, in device pixels.
        """
        return Image.open(
            io.BytesIO(
                self.page.screenshot(
                    full_page=full_page,
                    clip={
                        "x": clip[0],
                        "y": clip[1],
                        "width": clip[2],
                        "height": clip[3],
                    },
                    animations="disabled",
                    caret="hide",
                    scale="device",
                )
            )
        ).convert("RGB")

    def shoot_page(self) -> Callable[[tuple[float, float, float, float]], Image.Image]:
        """Take a screenshot of the whole page, in bands.

        Returns:
            A function cutting a rectangle, given in CSS pixels of the
            document, out of the screenshot.
        """
        width, height = self.page.evaluate(
            "() => [document.documentElement.scrollWidth,"
            " document.documentElement.scrollHeight]"
        )
        bands = [
            (top, self.shoot((0, top, width, min(BAND, height - top))))
            for top in range(0, height, BAND)
        ]
        scale = self.scale

        def cut(clip: tuple[float, float, float, float]) -> Image.Image:
            x, y, w, h = clip
            top, band = bands[int(y // BAND)]
            if y + h > top + BAND:
                # The rectangle straddles two bands: read it on its own.
                return self.shoot(clip)
            return band.crop((
                round(x * scale),
                round((y - top) * scale),
                round((x + w) * scale),
                round((y - top + h) * scale),
            ))

        return cut

    def target(self, props_id: str, system: System) -> Locator:
        """Locate the element of a frame.

        Args:
            props_id: The props id of the frame.
            system: The system of the frame.

        Returns:
            The element the matrix compares.
        """
        stage = self.page.locator(
            f'[data-parity-stage="{props_id}"][data-parity-system="{system.role}"]'
        )
        selector = _per_system(self.matrix.target)[system.role]
        return stage.locator(_FIRST_RENDERED if selector is None else selector).first

    def close(self) -> None:
        """Close the page."""
        self.context.close()


class _Excuses:
    """The allowlist entries of one matrix run, and which of them were needed."""

    def __init__(self, allowlist: Allowlist, component: str, engine: str):
        """Select the entries of a component in an engine.

        Args:
            allowlist: The intended differences.
            component: The component of the matrix.
            engine: The browser engine of the run.
        """
        self.component = component
        self.engine = engine
        self.entries = [
            entry
            for entry in allowlist.look
            if entry.component == component
            and (not entry.engines or engine in entry.engines)
        ]
        self.used: set[int] = set()

    def reasons(self, check: str, cell: str, name: str | None = None) -> list[str]:
        """Find why a difference of a cell is intended, if it is.

        Args:
            check: The check that found the difference.
            cell: The id of the cell.
            name: The computed property that differs, for a style.

        Returns:
            The reason of each entry that lists the difference.
        """
        reasons = []
        for index, entry in enumerate(self.entries):
            if entry.covers(self.component, check, cell, self.engine) and (
                name is None or name in entry.properties
            ):
                self.used.add(index)
                reasons.append(entry.reason)
        return reasons

    def stale(self) -> list[LookEntry]:
        """List the entries that excused nothing.

        Returns:
            The entries no difference of the run matched.
        """
        return [
            entry for index, entry in enumerate(self.entries) if index not in self.used
        ]


def _compare(
    matrix: Matrix,
    cell: Cell,
    images: dict[str, Image.Image],
    styles: dict[str, dict[str, dict[str, str]]],
    a11y: tuple[str, str] | None,
    report: Path,
    directory: Path,
    excuses: _Excuses,
) -> CellResult:
    """Compare what was read of a cell in both systems, and save its images.

    Args:
        matrix: The matrix of the cell.
        cell: The cell.
        images: The screenshot of each system, by role.
        styles: The computed properties of each system, by role then part.
        a11y: The accessibility trees when they differ, or None.
        report: The directory of the report.
        directory: Where the images go, relative to the report.
        excuses: The intended differences of the run.

    Returns:
        The result of the cell.
    """
    diff = diff_images(
        images[REFERENCE.role], images[CANDIDATE.role], threshold=matrix.threshold
    )
    files = {
        kind: (directory / f"{cell.id}.{kind}.png").as_posix()
        for kind in (REFERENCE.role, CANDIDATE.role, "diff")
    }
    for kind, image in (*images.items(), ("diff", diff.image)):
        image.save(report / files[kind])
    allowed: dict[str, None] = {}
    remaining = []
    for difference in _style_differences(
        styles[REFERENCE.role], styles[CANDIDATE.role]
    ):
        if reasons := excuses.reasons("style", cell.id, difference.property):
            allowed.update(dict.fromkeys(reasons))
        else:
            remaining.append(difference)
    pixel_reasons = (
        excuses.reasons("pixels", cell.id) if diff.ratio > matrix.tolerance else []
    )
    allowed.update(dict.fromkeys(pixel_reasons))
    if a11y is not None and (a11y_reasons := excuses.reasons("a11y", cell.id)):
        allowed.update(dict.fromkeys(a11y_reasons))
        a11y = None
    return CellResult(
        cell=cell.id,
        width=diff.width,
        height=diff.height,
        differing=diff.differing,
        antialiased=diff.antialiased,
        tolerance=matrix.tolerance,
        styles=remaining,
        a11y=a11y,
        allowed=list(allowed),
        images=files,
        skipped=list(
            _unmatched(styles[REFERENCE.role], styles[CANDIDATE.role]).values()
        ),
        pixels_allowed=bool(pixel_reasons),
    )


def _drive(
    current: _Pass,
    cell: Cell,
    state: State,
    frames: dict[tuple[str, str], dict[str, Any]],
    clips: dict[str, Clip],
) -> tuple[dict[str, Image.Image], dict[str, dict[str, dict[str, str]]]]:
    """Put the element of each system in a state, and read it there.

    Args:
        current: The loaded page.
        cell: The cell, whose state is not rest.
        state: The driver of the state.
        frames: What the page reported of each frame at rest, by props id and
            role.
        clips: The rectangle of the document to capture for each system, by
            role.

    Returns:
        The screenshot and the computed properties of each system, by role.

    Raises:
        CaptureError: If an element does not enter the state.
    """
    images, styles = {}, {}
    for system in SYSTEMS:
        frame = frames[cell.props_id, system.role]
        # Scrolled to before it is driven, so the page is still afterwards and
        # the screenshot is of the viewport: far faster than of a long page.
        scroll_x, scroll_y = current.page.evaluate(
            _SCROLL_SCRIPT, frame["stage"][1] - GAP
        )
        x, y, width, height = frame["target"]
        point = (x + width / 2 - scroll_x, y + height / 2 - scroll_y)
        target = current.target(cell.props_id, system)
        state.enter(current.page, target, point)
        (driven,) = current.read((cell.props_id, system), state.matches)
        if not driven["matched"]:
            msg = (
                f"{current.matrix.component} cell {cell.id}: the {system.name} "
                f"element did not enter {cell.state} (it does not match "
                f"{state.matches})."
            )
            raise CaptureError(msg)
        styles[system.role] = driven["styles"]
        left, top, clip_width, clip_height = clips[system.role]
        # Read again: driving the element may have scrolled the page.
        scroll_x, scroll_y, view_width, view_height = driven["view"]
        left, top = left - scroll_x, top - scroll_y
        if (
            left >= 0
            and top >= 0
            and left + clip_width <= view_width
            and top + clip_height <= view_height
        ):
            images[system.role] = current.shoot(
                (left, top, clip_width, clip_height), full_page=False
            )
        else:
            images[system.role] = current.shoot(clips[system.role])
        if state.leave is None:
            current.load()
        else:
            state.leave(current.page, target, point)
    return images, styles


def run_matrix(
    browser: Browser,
    url: str,
    matrix: Matrix,
    report: Path,
    allowlist: Allowlist,
    scale: int = 1,
    prepare: Callable[[Page], None] | None = None,
) -> MatrixResult:
    """Compare every cell of a matrix and write its images.

    Args:
        browser: The browser to render in.
        url: The address of the component's parity page.
        matrix: The matrix.
        report: The directory of the report. The images go to a directory
            named after the engine and the component.
        allowlist: The intended differences.
        scale: The device pixels per CSS pixel.
        prepare: Called with each loaded page before it is read, to change
            what is compared.

    Returns:
        The result of each cell.

    Raises:
        CaptureError: If a cell names a state nothing drives, or an element
            does not enter its state.
    """
    started = time.perf_counter()
    engine = browser.browser_type.name
    directory = Path(engine) / matrix.component
    (report / directory).mkdir(parents=True, exist_ok=True)
    states = {**STATES, **matrix.states}
    excuses = _Excuses(allowlist, matrix.component, engine)
    all_cells = matrix.cells()

    passes: dict[tuple[int, str], list[Cell]] = {}
    for cell in all_cells:
        if cell.state != REST and cell.state not in states:
            msg = f'{matrix.component}: no driver for the state "{cell.state}".'
            raise CaptureError(msg)
        passes.setdefault((cell.viewport, cell.appearance), []).append(cell)

    results: dict[str, CellResult] = {}
    # Read once, and compared at the first cell at rest of each element: the
    # tree depends on neither the viewport nor the scheme.
    trees: dict[tuple[str, str], str] | None = None
    described: set[str] = set()
    for (viewport, appearance), cells in passes.items():
        current = _Pass(browser, url, matrix, viewport, appearance, scale, prepare)
        try:
            frames = {(frame["id"], frame["system"]): frame for frame in current.read()}
            if trees is None:
                trees = split_a11y(current.page.locator("main").aria_snapshot())
            cut = current.shoot_page()
            for cell in cells:
                left, top, right, bottom = _crop(
                    matrix,
                    frames[cell.props_id, REFERENCE.role],
                    frames[cell.props_id, CANDIDATE.role],
                )
                clips: dict[str, Clip] = {
                    system.role: (
                        frames[cell.props_id, system.role]["stage"][0] + left,
                        frames[cell.props_id, system.role]["stage"][1] + top,
                        right - left,
                        bottom - top,
                    )
                    for system in SYSTEMS
                }
                a11y = None
                if cell.state != REST:
                    images, styles = _drive(
                        current, cell, states[cell.state], frames, clips
                    )
                else:
                    images = {role: cut(clip) for role, clip in clips.items()}
                    styles = {
                        system.role: frames[cell.props_id, system.role]["styles"]
                        for system in SYSTEMS
                    }
                    pair = (
                        trees.get((REFERENCE.role, cell.props_id), ""),
                        trees.get((CANDIDATE.role, cell.props_id), ""),
                    )
                    if cell.props_id not in described and pair[0] != pair[1]:
                        a11y = pair
                    described.add(cell.props_id)
                results[cell.id] = _compare(
                    matrix, cell, images, styles, a11y, report, directory, excuses
                )
        finally:
            current.close()

    return MatrixResult(
        component=matrix.component,
        engine=engine,
        # In the order of the matrix, whichever pass rendered a cell.
        cells=[results[cell.id] for cell in all_cells],
        seconds=time.perf_counter() - started,
        passes=len(passes),
        stale=excuses.stale(),
    )
