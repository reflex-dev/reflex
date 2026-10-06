"""Type-check logging (#7353): count server-log lines per wrong-typed var over 20 events."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

PATTERNS = {
    "bad_inner": "Computed var 'TypeLogState.bad_inner'",
    "bad_inner_const": "Computed var 'TypeLogState.bad_inner_const'",
    "bad_outer": "Computed var 'TypeLogState.bad_outer'",
    "bad_uncached": "Computed var 'TypeLogState.bad_uncached'",
    "nums_field": "Expected field 'TypeLogState.nums'",
}


def _segment(text: str, start: str, end: str) -> str:
    i = text.rfind(f"TYPELOG_MARK {start}")
    j = text.find(f"TYPELOG_MARK {end}", i)
    return text[i:j] if i >= 0 and j >= 0 else ""


def _count(seg: str) -> dict:
    flat = re.sub(r"\s*\n\s*", " ", seg)
    return {k: flat.count(v) for k, v in PATTERNS.items()}


def _mark(h, page, label):
    page.click(f"#tl-mark-{label.lower()}")


def t_typelog(h):
    log_path = Path(os.environ["EV_SERVER_LOG"])
    ctx, page = h.new_context_page("typelog")
    h.goto(page, "/typelog")
    n0 = int(h.text(page, "tl-n"))
    _mark(h, page, "A")
    for i in range(20):
        page.click("#tl-bump")
        h.wait_text(page, "tl-n", str(n0 + i + 1), 5)
    _mark(h, page, "B")
    for i in range(20):
        page.click("#tl-assign-inner")
        page.wait_for_timeout(120)
    _mark(h, page, "C")
    for i in range(20):
        page.click("#tl-assign-outer")
        page.wait_for_timeout(120)
    _mark(h, page, "D")
    page.wait_for_timeout(2500)
    text = log_path.read_text(errors="replace")
    seg_bump, seg_inner, seg_outer = _segment(text, "A", "B"), _segment(text, "B", "C"), _segment(text, "C", "D")
    res = {
        "bump_x20": _count(seg_bump),
        "assign_inner_x20": _count(seg_inner),
        "assign_outer_x20": _count(seg_outer),
        "ui_nums": h.text(page, "tl-nums"),
        "ui_bad_outer": h.text(page, "tl-bad-outer"),
        "segments_found": [bool(seg_bump), bool(seg_inner), bool(seg_outer)],
    }
    h.record("typelog.counts", "info", res)
    ctx.close()


ALL = [t_typelog]
