"""The browsable report of a parity run.

A directory that can be zipped or published as it is: ``index.html``, the
numbers as ``results.json``, and the reference, candidate and diff image of
every cell under ``<engine>/<component>/``.
"""

from __future__ import annotations

import dataclasses
import html
import json
import operator
from pathlib import Path
from typing import Any

from ui_parity.look import MatrixResult

RESULTS = "results.json"
INDEX = "index.html"

_STYLE = """
:root { color-scheme: light dark; font: 14px/1.4 system-ui, sans-serif; }
body { margin: 24px; }
h1 { font-size: 20px; }
h2 { font-size: 16px; margin-top: 32px; }
table { border-collapse: collapse; width: 100%; }
th, td { border-bottom: 1px solid #8884; padding: 6px 8px; text-align: left; vertical-align: top; }
td.number { font-variant-numeric: tabular-nums; white-space: nowrap; }
tr.fail td:first-child { box-shadow: inset 3px 0 #d33; }
tr.pass td:first-child { box-shadow: inset 3px 0 #2a2; }
img { image-rendering: pixelated; background: #fff; outline: 1px solid #8884; max-width: 100%; }
pre { margin: 0; white-space: pre-wrap; }
body.failures tr.pass { display: none; }
"""


def _row(result: dict[str, Any]) -> str:
    """Render the table row of a cell.

    Args:
        result: The cell's entry of the results.

    Returns:
        The row.
    """
    notes = [
        *(html.escape(problem) for problem in result["problems"]),
        *(f"allowed: {html.escape(reason)}" for reason in result["allowed"]),
        *(f"not compared {html.escape(skipped)}" for skipped in result["skipped"]),
    ]
    images = "".join(
        f'<td><a href="{html.escape(result["images"][kind])}">'
        f'<img loading="lazy" src="{html.escape(result["images"][kind])}" '
        f'alt="{kind}"></a></td>'
        for kind in ("reference", "candidate", "diff")
    )
    status = "fail" if result["problems"] else "pass"
    return (
        f'<tr class="{status}"><td>{html.escape(result["cell"])}</td>'
        f'<td class="number">{result["differing"]} / '
        f"{result['width'] * result['height']}<br>{result['ratio']:.2%}<br>"
        f"{result['antialiased']} anti-aliased</td>"
        f"{images}<td><pre>{chr(10).join(notes)}</pre></td></tr>"
    )


def _section(matrix: dict[str, Any]) -> str:
    """Render the section of a component in one engine.

    Args:
        matrix: The matrix's entry of the results.

    Returns:
        The heading, the numbers and the table of cells.
    """
    failed = sum(1 for cell in matrix["cells"] if cell["problems"])
    rows = "".join(_row(cell) for cell in matrix["cells"])
    stale = "".join(f"<p>{html.escape(line)}</p>" for line in matrix["stale"])
    return (
        f'<h2 id="{html.escape(matrix["engine"])}-{html.escape(matrix["component"])}">'
        f"{html.escape(matrix['component'])} · {html.escape(matrix['engine'])}</h2>"
        f"<p>{len(matrix['cells'])} cells, {failed} failing, "
        f"{matrix['passes']} page loads, {matrix['seconds']:.1f} s</p>{stale}"
        "<table><thead><tr><th>cell</th><th>pixels</th><th>rx (Radix)</th>"
        "<th>rx.ui</th><th>diff</th><th>differences</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def render(results: list[dict[str, Any]]) -> str:
    """Render the report.

    Args:
        results: The entry of each matrix that ran.

    Returns:
        The HTML document.
    """
    cells = sum(len(matrix["cells"]) for matrix in results)
    failed = sum(
        1 for matrix in results for cell in matrix["cells"] if cell["problems"]
    )
    seconds = sum(matrix["seconds"] for matrix in results)
    sections = "".join(_section(matrix) for matrix in results)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>rx.ui parity</title><style>{_STYLE}</style></head><body>"
        "<h1>rx.ui parity with Radix Themes</h1>"
        f"<p>{len(results)} matrices, {cells} cells, {failed} failing, "
        f"{seconds:.1f} s</p>"
        '<label><input type="checkbox" onchange="document.body.classList.toggle('
        "'failures', this.checked)\"> failing cells only</label>"
        f"{sections}</body></html>"
    )


def entry(result: MatrixResult) -> dict[str, Any]:
    """Reduce the result of a matrix to what the report keeps.

    Args:
        result: The result.

    Returns:
        The numbers of the matrix and of each cell, as JSON holds them.
    """
    return {
        "component": result.component,
        "engine": result.engine,
        "seconds": round(result.seconds, 3),
        "passes": result.passes,
        "stale": [
            f"stale allowlist entry: {item.check}, cells {item.cells}: {item.reason}"
            for item in result.stale
        ],
        "cells": [
            {
                "cell": cell.cell,
                "width": cell.width,
                "height": cell.height,
                "differing": cell.differing,
                "antialiased": cell.antialiased,
                "ratio": cell.ratio,
                "tolerance": cell.tolerance,
                "styles": [
                    dataclasses.asdict(difference) for difference in cell.styles
                ],
                "a11y": cell.a11y,
                "allowed": cell.allowed,
                "skipped": cell.skipped,
                "problems": cell.problems,
                "images": cell.images,
            }
            for cell in result.cells
        ],
    }


def write(report: Path, result: MatrixResult) -> Path:
    """Add the result of a matrix to a report.

    Args:
        report: The directory of the report.
        result: The result, whose images are already there.

    Returns:
        The page of the report.
    """
    path = report / RESULTS
    results = json.loads(path.read_text()) if path.exists() else []
    results = [
        matrix
        for matrix in results
        if (matrix["engine"], matrix["component"]) != (result.engine, result.component)
    ]
    results.append(entry(result))
    results.sort(key=operator.itemgetter("component", "engine"))
    path.write_text(json.dumps(results, indent=2) + "\n")
    index = report / INDEX
    index.write_text(render(results), encoding="utf-8")
    return index
