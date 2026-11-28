"""Tests for the report of a parity run."""

import json
from pathlib import Path

from ui_parity import report
from ui_parity.look import CellResult, MatrixResult, StyleDifference


def matrix(component: str, engine: str, differing: int) -> MatrixResult:
    """Build the result of a matrix of one cell.

    Args:
        component: The component.
        engine: The browser engine.
        differing: The pixels of the cell that differ.

    Returns:
        The result.
    """
    return MatrixResult(
        component=component,
        engine=engine,
        cells=[
            CellResult(
                cell="size-1@hover",
                width=100,
                height=50,
                differing=differing,
                antialiased=3,
                tolerance=0.005,
                styles=[StyleDifference("", "height", "32px", "30px")]
                if differing
                else [],
                a11y=None,
                allowed=["Tooltips have <no> arrow."],
                images={
                    kind: f"{engine}/{component}/size-1@hover.{kind}.png"
                    for kind in ("reference", "candidate", "diff")
                },
                skipped=["inside <button>: rx has 2 element children, rx.ui 1"],
            )
        ],
        seconds=1.5,
        passes=1,
        stale=[],
    )


ENTRY = {
    "component": "button",
    "engine": "chromium",
    "seconds": 1.5,
    "passes": 1,
    "stale": [],
    "cells": [
        {
            "cell": "size-1@hover",
            "width": 100,
            "height": 50,
            "differing": 400,
            "antialiased": 3,
            "ratio": 0.08,
            "tolerance": 0.005,
            "styles": [
                {
                    "part": "",
                    "property": "height",
                    "reference": "32px",
                    "candidate": "30px",
                }
            ],
            "a11y": None,
            "allowed": ["Tooltips have <no> arrow."],
            "skipped": ["inside <button>: rx has 2 element children, rx.ui 1"],
            "problems": [
                "400 of 5000 pixels differ (8.00%, 0.50% allowed)",
                "height: rx '32px', rx.ui '30px'",
            ],
            "images": {
                "reference": "chromium/button/size-1@hover.reference.png",
                "candidate": "chromium/button/size-1@hover.candidate.png",
                "diff": "chromium/button/size-1@hover.diff.png",
            },
        }
    ],
}


def image(kind: str) -> str:
    """Get the table cell the report shows an image of the entry in.

    Args:
        kind: Which image: the reference, the candidate or the diff.

    Returns:
        The HTML of the cell.
    """
    path = f"chromium/button/size-1@hover.{kind}.png"
    return (
        f'<td><a href="{path}"><img loading="lazy" src="{path}" alt="{kind}"></a></td>'
    )


PAGE = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    f"<title>rx.ui parity</title><style>{report._STYLE}</style></head><body>"
    "<h1>rx.ui parity with Radix Themes</h1>"
    "<p>1 matrices, 1 cells, 1 failing, 1.5 s</p>"
    '<label><input type="checkbox" onchange="document.body.classList.toggle('
    "'failures', this.checked)\"> failing cells only</label>"
    '<h2 id="chromium-button">button · chromium</h2>'
    "<p>1 cells, 1 failing, 1 page loads, 1.5 s</p>"
    "<table><thead><tr><th>cell</th><th>pixels</th><th>rx (Radix)</th>"
    "<th>rx.ui</th><th>diff</th><th>differences</th></tr></thead><tbody>"
    '<tr class="fail"><td>size-1@hover</td>'
    '<td class="number">400 / 5000<br>8.00%<br>3 anti-aliased</td>'
    f"{image('reference')}{image('candidate')}{image('diff')}"
    "<td><pre>400 of 5000 pixels differ (8.00%, 0.50% allowed)\n"
    "height: rx &#x27;32px&#x27;, rx.ui &#x27;30px&#x27;\n"
    "allowed: Tooltips have &lt;no&gt; arrow.\n"
    "not compared inside &lt;button&gt;: rx has 2 element children, rx.ui 1"
    "</pre></td></tr>"
    "</tbody></table></body></html>"
)


def test_entry_keeps_the_numbers_of_every_cell():
    assert report.entry(matrix("button", "chromium", 400)) == ENTRY


def test_render_shows_each_cell_with_its_images_and_differences():
    assert report.render([ENTRY]) == PAGE


def test_write_adds_a_matrix_and_replaces_its_earlier_run(tmp_path: Path):
    index = report.write(tmp_path, matrix("button", "webkit", 0))
    assert index == tmp_path / "index.html"
    report.write(tmp_path, matrix("button", "chromium", 0))
    report.write(tmp_path, matrix("box", "webkit", 0))
    report.write(tmp_path, matrix("button", "chromium", 400))
    results = json.loads((tmp_path / "results.json").read_text())
    assert [(entry["component"], entry["engine"]) for entry in results] == [
        ("box", "webkit"),
        ("button", "chromium"),
        ("button", "webkit"),
    ]
    assert results[1] == ENTRY
    assert index.read_text(encoding="utf-8") == report.render(results)
