"""Tests for the comparison of a matrix that need no browser."""

from pathlib import Path

import pytest
from ui_parity.allowlist import Allowlist, LookEntry
from ui_parity.look import (
    SHAPE,
    CellResult,
    MatrixResult,
    StyleDifference,
    _crop,
    _Excuses,
    _style_differences,
    _unmatched,
    split_a11y,
    use_fonts,
)
from ui_parity.matrix import Matrix


def test_split_a11y_gives_each_frame_its_tree():
    snapshot = (
        "- main:\n"
        '  - group "reference:base":\n'
        '    - button "Save"\n'
        '  - group "candidate:base":\n'
        '    - button "Save":\n'
        "      - img\n"
        '  - group "reference:size-1"\n'
        '  - group "candidate:size-1": text\n'
        "  - paragraph: between\n"
        "    - text: not of a frame\n"
        '  - group "candidate:base@x":\n'
        "    - text: after\n"
        "- contentinfo"
    )
    assert split_a11y(snapshot) == {
        ("reference", "base"): '- button "Save"',
        ("candidate", "base"): '- button "Save":\n  - img',
        ("reference", "size-1"): "",
        ("candidate", "size-1"): "text",
        ("candidate", "base@x"): "- text: after",
    }


def frame(stage: list[float], target: list[float]) -> dict:
    """Describe a frame as the page reports it.

    Args:
        stage: The left, top, width and height of the frame.
        target: The same of its element.

    Returns:
        The frame.
    """
    return {"stage": stage, "target": target}


def test_crop_is_the_union_of_both_elements_and_a_margin_within_the_frame():
    matrix = Matrix(component="button", stage=(240, 120), margin=8)
    reference = frame([8, 8, 240, 120], [24, 24, 80.5, 32])
    candidate = frame([256, 8, 240, 120], [272, 24, 84, 30.25])
    # Each element starts 16 pixels into its frame; the wider and the taller
    # one set the far edges, rounded out to whole pixels.
    assert _crop(matrix, reference, candidate) == (8, 8, 108, 56)
    # An element that fills its frame is cropped by the frame.
    full = frame([8, 8, 240, 120], [8, 8, 240, 120])
    assert _crop(matrix, full, full) == (0, 0, 240, 120)
    whole = Matrix(component="tooltip", stage=(300, 200), crop="stage")
    assert _crop(whole, reference, candidate) == (0, 0, 300, 200)


def test_style_differences_name_the_part_and_both_values():
    reference = {
        "": {"color": "rgb(0, 0, 0)", "height": "32px"},
        "thumb": {"width": "16px"},
        "arrow": {"width": "8px"},
    }
    candidate = {
        "": {"color": "rgb(0, 0, 0)", "height": "30px"},
        "thumb": {"width": "14px"},
    }
    assert _style_differences(reference, candidate) == [
        StyleDifference("", "height", "32px", "30px"),
        StyleDifference("arrow", "(element)", "present", None),
        StyleDifference("thumb", "width", "16px", "14px"),
    ]
    assert _style_differences(reference, reference) == []


def test_style_differences_reach_the_elements_inside_that_correspond():
    """An element inside is compared while both systems build it alike."""
    reference = {
        "": {"color": "red"},
        "> 1": {"isolation": "isolate"},
        "> 1 > 1": {"color": "red"},
        "> 2": {"color": "red"},
        "> 2 > 1": {"color": "red"},
        "> 2 > 2": {"color": "red"},
        "> 3": {"color": "red"},
        SHAPE: {
            "": "3 a",
            "> 1": "1 code",
            "> 1 > 1": "0 b",
            "> 2": "2 span",
            "> 2 > 1": "0 i",
            "> 2 > 2": "0 i",
            "> 3": "0 svg",
        },
    }
    candidate = {
        "": {"color": "red"},
        "> 1": {"isolation": "auto"},
        "> 1 > 1": {"color": "blue"},
        "> 2": {"color": "green"},
        # Built differently: what is inside is not compared.
        "> 2 > 1": {"color": "blue"},
        # Named as a part in this system, and compared as one.
        "icon": {"color": "red"},
        SHAPE: {
            "": "3 a",
            "> 1": "1 code",
            "> 1 > 1": "0 span",
            "> 2": "1 span",
            "> 2 > 1": "0 i",
            "> 3": "0 svg",
        },
    }
    assert _style_differences(reference, candidate) == [
        StyleDifference("> 1 <code>", "isolation", "isolate", "auto"),
        StyleDifference("> 1 > 1 <b>", "color", "red", "blue"),
        StyleDifference("icon", "(element)", None, "present"),
    ]
    assert _unmatched(reference, candidate) == {
        # Built differently: neither it nor what is inside it is compared.
        "> 2": "at and inside > 2 <span>: rx has 2 element children, rx.ui 1"
    }
    # Nothing inside an element that differs at its root is compared.
    assert _style_differences(
        {**reference, SHAPE: {**reference[SHAPE], "": "4 a"}}, candidate
    ) == [StyleDifference("icon", "(element)", None, "present")]
    assert _unmatched(
        {**reference, SHAPE: {**reference[SHAPE], "": "4 a"}}, candidate
    ) == {"": "inside <a>: rx has 4 element children, rx.ui 3"}
    assert _unmatched(reference, reference) == {}


def result(cell: str, differing: int, **differences) -> CellResult:
    """Build the result of a cell of 100 by 50 pixels.

    Args:
        cell: The id of the cell.
        differing: The pixels that differ.
        differences: The other fields of the result.

    Returns:
        The result.
    """
    fields = {
        "styles": [],
        "a11y": None,
        "allowed": [],
        "images": {
            kind: f"chromium/button/{cell}.{kind}.png"
            for kind in ("reference", "candidate", "diff")
        },
        **differences,
    }
    return CellResult(
        cell=cell,
        width=100,
        height=50,
        differing=differing,
        antialiased=0,
        tolerance=0.005,
        **fields,
    )


def test_problems_say_which_check_failed_and_by_how_much():
    assert result("base", 25).problems == []
    assert result("base", 26).ratio == pytest.approx(0.0052)
    assert result("base", 26).problems == [
        "26 of 5000 pixels differ (0.52%, 0.50% allowed)"
    ]
    assert result("base", 26, pixels_allowed=True).problems == []
    assert result(
        "base",
        0,
        styles=[
            StyleDifference("", "height", "32px", "30px"),
            StyleDifference("thumb", "width", "16px", None),
        ],
        a11y=('- button "Save"', "- text: Save"),
    ).problems == [
        "height: rx '32px', rx.ui '30px'",
        "thumb width: rx '16px', rx.ui None",
        "accessibility tree: rx '- button \"Save\"', rx.ui '- text: Save'",
    ]


def test_failures_name_the_cell_and_where_its_images_are():
    stale = LookEntry(
        component="button",
        check="pixels",
        cells="*@hover",
        properties=(),
        engines=(),
        reason="The hover is lighter.",
    )
    matrix = MatrixResult(
        component="button",
        engine="chromium",
        cells=[
            result("base", 0),
            result(
                "size-1@hover",
                400,
                styles=[StyleDifference("", "height", "32px", "30px")],
            ),
        ],
        seconds=1.5,
        passes=1,
        stale=[stale],
    )
    # The images are named as the system names a path.
    images = (
        Path("/report") / "chromium/button/size-1@hover.{reference,candidate,diff}.png"
    )
    assert matrix.failures(Path("/report")) == [
        (
            "button [chromium] cell size-1@hover:\n"
            "  - 400 of 5000 pixels differ (8.00%, 0.50% allowed)\n"
            "  - height: rx '32px', rx.ui '30px'\n"
            f"  images: {images}"
        ),
        (
            "button [chromium]: nothing differs as the allowlist.toml entry says "
            "(pixels, cells '*@hover': \"The hover is lighter.\"). Remove the entry."
        ),
    ]


def test_excuses_match_by_check_cell_and_property_and_report_the_unused():
    def entry(check: str, **fields) -> LookEntry:
        return LookEntry(**{
            "component": "select",
            "check": check,
            "cells": "*",
            "properties": (),
            "engines": (),
            "reason": check,
            **fields,
        })

    position = entry("style", properties=("top",), reason="position")
    arrow = entry("pixels", cells="*@open", reason="arrow")
    webkit = entry("a11y", engines=("webkit",), reason="webkit")
    other = entry("pixels", component="tooltip", reason="other")
    unused = entry("a11y", reason="unused")
    excuses = _Excuses(
        Allowlist(look=(position, arrow, webkit, other, unused)), "select", "chromium"
    )
    assert excuses.entries == [position, arrow, unused]
    assert excuses.reasons("style", "base", "top") == ["position"]
    assert excuses.reasons("style", "base", "left") == []
    assert excuses.reasons("pixels", "base") == []
    assert excuses.stale() == [arrow, unused]
    assert excuses.reasons("pixels", "base@open") == ["arrow"]
    assert excuses.stale() == [unused]


def test_use_fonts_sets_the_fonts_of_both_systems_and_waits_for_them():
    """The fonts are forced on every element, code apart, before a read."""
    calls = []

    class FakePage:
        def add_style_tag(self, *, content: str) -> None:
            calls.append(("style", content))

        def evaluate(self, expression: str) -> None:
            calls.append(("evaluate", expression))

    use_fonts("DejaVu Sans", "Liberation Mono")(FakePage())  # pyright: ignore[reportArgumentType]
    css = (
        '* { font-family: "DejaVu Sans" !important; }\n'
        "code, code *, kbd, kbd *, pre, pre * "
        '{ font-family: "Liberation Mono" !important; }'
    )
    assert calls == [
        ("style", css),
        ("evaluate", "document.fonts.ready"),
    ]
