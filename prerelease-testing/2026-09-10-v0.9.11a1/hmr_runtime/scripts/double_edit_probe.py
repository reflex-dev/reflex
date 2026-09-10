"""Probe whether a second save shortly after a first one is picked up by `reflex run`'s backend reloader.

For each gap: rewrite the heading in the app source (vN), wait `gap` seconds, rewrite again (vN+1), then wait up
to 40s for the compiled `.web/app/routes/_index.jsx` to contain vN+1. Also counts "Changes detected" lines in the
server log during each probe. No browser needed: the compiled output is the ground truth for what Vite can serve.

    python double_edit_probe.py --app-file .../hmr_app/hmr_app.py --web-dir .../hmr_app/.web --server-log .../dev.log \
        --gaps 0.3,0.5,1.0,2.0,4.0 --out .../logs/double_probe_new.json
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

HEADING_RE = re.compile(r'rx\.heading\("(HMR Runtime App[^"]*)", id="heading"\)')


def compiled_heading(web_dir: Path) -> str | None:
    try:
        m = re.search(r"HMR Runtime App[^\"<]*", (web_dir / "app/routes/_index.jsx").read_text())
    except OSError:
        return None
    return m.group(0) if m else None


def count_reloads(log: Path) -> int:
    try:
        return log.read_text(errors="replace").count("Changes detected, reloading workers")
    except OSError:
        return -1


def set_heading(app_file: Path, text: str):
    src = app_file.read_text()
    new = HEADING_RE.sub(f'rx.heading("{text}", id="heading")', src, count=1)
    assert new != src or text in src, "heading marker not found"
    app_file.write_text(new)


def wait_compiled(web_dir: Path, text: str, timeout: float) -> float | None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if compiled_heading(web_dir) == text:
            return round(time.time() - t0, 2)
        time.sleep(0.2)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-file", required=True)
    ap.add_argument("--web-dir", required=True)
    ap.add_argument("--server-log", required=True)
    ap.add_argument("--gaps", default="0.3,0.5,1.0,2.0,4.0")
    ap.add_argument("--out", required=True)
    ap.add_argument("--vary-length", action="store_true", help="make the second edit a different byte length than the first")
    args = ap.parse_args()
    app_file, web_dir, log = Path(args.app_file), Path(args.web_dir), Path(args.server_log)
    results = []
    n = 100
    for gap in [float(g) for g in args.gaps.split(",")]:
        # start from a settled single edit
        n += 1
        base = f"HMR Runtime App p{n}"
        set_heading(app_file, base)
        settled = wait_compiled(web_dir, base, 40)
        time.sleep(3)
        reloads0 = count_reloads(log)
        first, second = f"HMR Runtime App p{n}a", (f"HMR Runtime App p{n}b-longer" if args.vary_length else f"HMR Runtime App p{n}b")
        t0 = time.time()
        set_heading(app_file, first)
        time.sleep(gap)
        set_heading(app_file, second)
        got_second = wait_compiled(web_dir, second, 40)
        time.sleep(2)
        reloads = count_reloads(log) - reloads0
        res = {
            "gap_s": gap,
            "same_length_edits": len(first) == len(second),
            "single_edit_settled_s": settled,
            "second_edit_compiled_after_s": got_second,
            "compiled_heading_after_wait": compiled_heading(web_dir),
            "source_heading": HEADING_RE.search(app_file.read_text()).group(1),
            "reloads_detected_during_probe": reloads,
            "lost": got_second is None,
        }
        results.append(res)
        print(json.dumps(res), flush=True)
        if got_second is None:
            # nudge: a third save recovers? record whether the compiled output catches up
            time.sleep(1)
            set_heading(app_file, f"HMR Runtime App p{n}c")
            res["recovery_edit_compiled_after_s"] = wait_compiled(web_dir, f"HMR Runtime App p{n}c", 40)
            print("  recovery:", res["recovery_edit_compiled_after_s"], flush=True)
            time.sleep(2)
    Path(args.out).write_text(json.dumps(results, indent=2))
    print("written", args.out)


if __name__ == "__main__":
    main()
