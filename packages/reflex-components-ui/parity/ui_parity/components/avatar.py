"""The avatar: an image, and the fallback that shows until it loads or when it fails."""

from __future__ import annotations

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, LIGHT, Matrix
from ui_parity.samples import ACCENTS

# A checkerboard of eight pixels a side: nothing is loaded from a network.
IMAGE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAJUlEQVR4nGM8YRPFAAMJcnlwNhMDDkC6BKNG1Ak4Z8GjSbSwAwDxyAW3Fur+BAAAAABJRU5ErkJggg=="
# An address that is no image.
BROKEN = "data:image/png;base64,AAAA"

SIZES = ["1", "2", "3", "4", "5", "6", "7", "8", "9"]
RESPONSIVE = rx.breakpoints(initial="1", sm="4", lg="2")
# From a size with a smaller size for two letters to one without.
RESPONSIVE_LARGE = rx.breakpoints(initial="2", sm="6")

MATRIX = Matrix(
    component="avatar",
    base={"fallback": "AB"},
    cross={"size": SIZES, "fallback": ["A", "AB", "ABC"]},
    sweep={
        "variant": ["solid", "soft"],
        "color_scheme": ACCENTS,
        "radius": ["none", "small", "medium", "large", "full"],
        "high_contrast": [True],
        "src": {"image": IMAGE, "broken": BROKEN},
        "size": {"responsive": RESPONSIVE},
        "appearance": [DARK],
        "viewport": [520],
    },
    groups=[
        {
            "variant": ["solid", "soft"],
            "high_contrast": [False, True],
            "appearance": [LIGHT, DARK],
        },
        {
            "variant": ["solid", "soft"],
            "color_scheme": ["ruby", "gray", "yellow"],
            "high_contrast": [False, True],
        },
        {"src": {"image": IMAGE, "broken": BROKEN}, "size": ["1", "5", "9"]},
        {
            "src": {"image": IMAGE, "broken": BROKEN},
            "variant": ["solid", "soft"],
            "radius": ["none", "full"],
        },
        {"radius": ["none", "full"], "size": ["1", "5", "9"]},
        {"size": {"responsive": RESPONSIVE}, "viewport": [520, 800, 1100, 1280]},
        {"size": {"responsive-large": RESPONSIVE_LARGE}, "viewport": [520, 800]},
    ],
    stage=(200, 200),
    # An avatar of Radix is empty until JavaScript has run, and shows its
    # image or its fallback some time after the page is hydrated.
    ready=(
        "[...document.querySelectorAll('[data-parity-system=reference]')].every("
        "stage => stage.querySelector('.rt-AvatarFallback, img'))"
    ),
    # Not held to zero, for the image alone: at a threshold of zero every
    # cell without an image is equal pixel for pixel, and so are most with
    # one. The image is a checkerboard of eight pixels scaled up, and where
    # its two colors meet the browser interpolates them by where the avatar
    # is on the page: 3 of the 13 cells with an image differ there, by at
    # most 80 pixels of 30976.
)

CONTRACT = Contract(
    component="avatar",
    render=lambda namespace: namespace.box(
        rx.el.div(namespace.avatar(src=IMAGE, fallback="AB", alt="Ada"), id="loaded"),
        rx.el.div(namespace.avatar(src=BROKEN, fallback="CD", alt="Bo"), id="broken"),
        rx.el.div(namespace.avatar(fallback="EF"), id="none"),
    ),
)


@CONTRACT.step("a loaded image is shown, with its text for the accessibility tree")
def _loaded(run: Run) -> None:
    image = run.page.locator("#loaded").get_by_role("img", name="Ada")
    image.wait_for()
    box = image.bounding_box()
    assert box is not None
    assert (box["width"], box["height"]) == (40, 40)
    assert run.page.locator("#loaded").get_by_text("AB").is_hidden()


@CONTRACT.step("the fallback is shown for an image that fails", on=HYDRATED)
def _broken(run: Run) -> None:
    fallback = run.page.locator("#broken").get_by_text("CD")
    fallback.wait_for()
    box = fallback.bounding_box()
    assert box is not None
    assert (box["width"], box["height"]) == (40, 40)
    run.page.wait_for_function(
        "!document.querySelector('#broken img')"
        " || getComputedStyle(document.querySelector('#broken img')).display === 'none'"
    )


@CONTRACT.step("the fallback is shown without an image", on=HYDRATED)
def _none(run: Run) -> None:
    assert run.page.locator("#none").get_by_text("EF").is_visible()
    assert run.page.locator("#none img").count() == 0


@CONTRACT.step("the fallback is in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    assert run.server.element("none").text == "EF"
    assert run.server.element("loaded").text == "AB"
    assert run.server.element("broken").text == "CD"


@CONTRACT.step(
    "shows a loaded image and the fallback without JavaScript",
    on=NO_JAVASCRIPT,
)
def _without_javascript(run: Run) -> None:
    assert run.page.locator("#none").get_by_text("EF").is_visible()
    image = run.page.locator("#loaded img")
    assert image.evaluate("image => image.complete && image.naturalWidth") == 8
    box = image.bounding_box()
    assert box is not None
    assert (box["width"], box["height"]) == (40, 40)
    # The image covers the fallback, which is the same box.
    assert run.page.locator("#loaded span > span").bounding_box() == box
