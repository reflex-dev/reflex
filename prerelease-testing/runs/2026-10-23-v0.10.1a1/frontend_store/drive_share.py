"""Drive the fs_app share lab (/) and compare the DOM with the backend truth after every op.

    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
      $SB/envs/driver/bin/python drive_share.py --url http://localhost:3220/ \
      --truth $SB/apps/frontend_store/truth/t.json --out report.json

Exit 0 when every op matched and no console error / page error happened.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"

DEFAULT_OPS = [
    "append", "pop", "pop0", "insert1", "sort_qty", "sort_qty_desc", "reverse", "replace_equal",
    "bump0", "tag0", "meta0", "meta0_del", "rename_last", "same_twice", "noop",
    "nested_add", "nested_upd", "nested_del_inner", "nested_del", "nested_reset", "nested_reorder",
    "set_same_nested", "blob_none", "blob_dict", "poly_obj", "poly_arr",
    "matrix_mut", "matrix_row", "matrix_pop_inner", "bases_mut", "bases_replace", "pyd_mut",
    "when_tick", "tags_add", "tags_rm", "pair_swap",
    "big_fill", "big_mut_mid", "big_append", "big_pop0",
    "both", "deep_bump", "many", "clear", "reset", "bg_run", "pop", "append",
]

BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]

SNAPSHOT_JS = """
() => {
  const txt = (sel) => (document.querySelector(sel) || {}).textContent;
  const lis = (sel) => Array.from(document.querySelectorAll(sel + ' > li')).map(li => li.textContent);
  const pres = {};
  for (const el of document.querySelectorAll('pre[id^="v-"]')) pres[el.id.slice(2)] = el.textContent;
  const cards = Array.from(document.querySelectorAll('#cards .card')).map(c => ({
    id: c.querySelector('.card-id').textContent,
    name: c.querySelector('.card-name').textContent,
    qty: c.querySelector('.card-qty').textContent,
    tags: c.querySelector('.card-tags').textContent,
    meta: c.querySelector('.card-meta').textContent,
    renders: c.querySelector('span[data-renders]').getAttribute('data-renders'),
  }));
  return {
    step: txt('#step'), pres, idx: lis('#idx'), keyed: lis('#keyed'),
    nested_entries: lis('#nested-entries'), matrix_rows: lis('#matrix-rows'),
    big_list: lis('#big-list'), cards,
    cond_nested: txt('#cond-nested'), cond_blob: txt('#cond-blob'),
  };
}
"""


def jd(v) -> str:
    """JSON.stringify-compatible dump."""
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False)


def find_state(state: dict, suffix: str) -> dict:
    for k, v in state.items():
        if k.endswith(suffix):
            # var names in State.dict() carry the "_rx_state_" suffix
            return {name.removesuffix("_rx_state_"): value for name, value in v.items()}
    raise KeyError(suffix)


def expected_from_truth(truth: dict) -> dict:
    st = truth["state"]
    share = find_state(st, "share_state")
    sub_a = find_state(st, "sub_a")
    sub_b = find_state(st, "sub_b")
    deep3 = find_state(st, "deep3")
    deep1 = find_state(st, "deep1")
    items = share["items"]
    nested = share["nested"]
    big = share["big"]

    def item_line(i, it, with_index):
        parts = [str(it["id"]), it["name"], str(it["qty"]), ",".join(it["tags"]), jd(it["meta"])]
        if with_index:
            parts.insert(0, str(i))
        return "|".join(parts)

    pres = {
        "items": items, "nested": nested, "blob": share["blob"], "poly": share["poly"],
        "matrix": share["matrix"], "bases": share["bases"], "pyd": share["pyd"],
        "when": share["when"], "tags": sorted(share["tags"]), "pair": share["pair"],
        "summary": share["summary"], "big_len": share["big_len"], "big_sum": share["big_sum"],
        "a": sub_a["a"], "b": sub_b["b"], "d1": deep1["d1"], "d3": deep3["d3"],
    }
    a = nested.get("a")
    cond_nested = "big" if isinstance(a, dict) and isinstance(a.get("x"), (int, float)) and a["x"] > 1 else "small"
    return {
        "step": str(truth["step"]),
        "pres": pres,
        "idx": [item_line(i, it, True) for i, it in enumerate(items)],
        "keyed": [item_line(i, it, False) for i, it in enumerate(items)],
        "nested_entries": [f"{k}={jd(v)}" for k, v in nested.items()],
        "matrix_rows": [",".join(map(str, row)) for row in share["matrix"]],
        "big_list": [str(n) for n in big],
        "big_js_len": str(len(big)),
        "big_2500": str(big[2500]) if len(big) > 2500 else "",
        "cards": [{"id": str(it["id"]), "name": it["name"], "qty": str(it["qty"]), "tags": ",".join(it["tags"]), "meta": jd(it["meta"])} for it in items],
        "cond_nested": cond_nested,
        "cond_blob": "has-blob" if share["blob"] is not None else "no-blob",
    }


def compare(snap: dict, exp: dict) -> list[dict]:
    diffs = []

    def chk(name, dom, want):
        if dom != want:
            diffs.append({"field": name, "dom": dom, "truth": want})

    chk("step", snap["step"], exp["step"])
    for name, want in exp["pres"].items():
        raw = snap["pres"].get(name)
        try:
            dom = json.loads(raw) if raw not in (None, "") else raw
        except json.JSONDecodeError:
            dom = raw
        if name == "tags" and isinstance(dom, list):
            dom = sorted(dom)
        chk(f"pre:{name}", dom, want)
    chk("pre:big_js_len", snap["pres"].get("big_js_len"), exp["big_js_len"])
    chk("pre:big_2500", snap["pres"].get("big_2500"), exp["big_2500"])
    for name in ("idx", "keyed", "nested_entries", "matrix_rows", "big_list"):
        chk(name, snap[name], exp[name])
    cards = [{k: v for k, v in c.items() if k != "renders"} for c in snap["cards"]]
    chk("cards", cards, exp["cards"])
    chk("cond_nested", snap["cond_nested"], exp["cond_nested"])
    chk("cond_blob", snap["cond_blob"], exp["cond_blob"])
    return diffs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--truth", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ops", default=",".join(DEFAULT_OPS))
    ap.add_argument("--screenshot-dir", default=None)
    ap.add_argument("--timeout", type=int, default=20000)
    ap.add_argument("--settle", type=int, default=150, help="ms to wait after the step counter updates")
    args = ap.parse_args()
    ops = [o for o in args.ops.split(",") if o]
    truth_path = Path(args.truth)
    if truth_path.exists():
        truth_path.unlink()

    console, errors, failed, bad = [], [], [], []
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        ctx = browser.new_context(viewport={"width": 1100, "height": 900})
        page = ctx.new_page()
        page.on("console", lambda m: console.append({"type": m.type, "text": m.text}))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("requestfailed", lambda r: failed.append(f"{r.method} {r.url} {r.failure}"))
        page.on("response", lambda r: bad.append(f"{r.status} {r.url}") if r.status >= 400 else None)
        t0 = time.time()
        page.goto(args.url, wait_until="load", timeout=args.timeout)
        page.wait_for_function("() => document.querySelector('#hydrated')?.textContent === 'true'", timeout=args.timeout)
        hydrate_ms = int((time.time() - t0) * 1000)
        snap0 = page.evaluate(SNAPSHOT_JS)
        step = int(snap0["step"])
        for op in ops:
            expect_step = step + (5 if op == "bg_run" else 1)
            t1 = time.time()
            page.click(f"#op-{op}", timeout=args.timeout)
            ok = True
            try:
                page.wait_for_function(
                    f"() => document.querySelector('#step')?.textContent === '{expect_step}'",
                    timeout=args.timeout,
                )
            except Exception as e:  # noqa: BLE001
                ok = False
                results.append({"op": op, "ok": False, "error": f"step {expect_step} not reached: {e}"})
            # wait for the truth file to reach the step
            deadline = time.time() + 10
            truth = None
            while time.time() < deadline:
                try:
                    truth = json.loads(truth_path.read_text())
                    if truth["step"] == expect_step:
                        break
                except (FileNotFoundError, json.JSONDecodeError, KeyError):
                    pass
                time.sleep(0.05)
            page.wait_for_timeout(args.settle)
            snap = page.evaluate(SNAPSHOT_JS)
            elapsed_ms = int((time.time() - t1) * 1000)
            if truth is None or truth["step"] != expect_step:
                results.append({"op": op, "ok": False, "error": f"truth not at step {expect_step}: {truth and truth.get('step')}"})
                step = int(snap["step"]) if snap["step"].isdigit() else expect_step
                continue
            diffs = compare(snap, expected_from_truth(truth))
            if ok:
                results.append({
                    "op": op, "ok": not diffs, "step": expect_step, "ms": elapsed_ms, "diffs": diffs,
                    "card_renders": {c["id"]: c["renders"] for c in snap["cards"]},
                })
            if args.screenshot_dir and diffs:
                Path(args.screenshot_dir).mkdir(parents=True, exist_ok=True)
                page.screenshot(path=f"{args.screenshot_dir}/{op}.png", full_page=False)
            step = expect_step
        page.wait_for_timeout(300)
        browser.close()

    noisy = [c for c in console if not any(b.search(c["text"]) for b in BENIGN)]
    report = {
        "url": args.url, "hydrate_ms": hydrate_ms, "results": results,
        "n_fail": sum(1 for r in results if not r["ok"]),
        "console": noisy, "pageerrors": errors, "requestfailed": [f for f in failed if "favicon" not in f],
        "http_errors": [b for b in bad if "favicon" not in b],
    }
    Path(args.out).write_text(json.dumps(report, indent=1, ensure_ascii=False))
    for r in results:
        flag = "ok " if r["ok"] else "FAIL"
        extra = r.get("error") or (f"{len(r['diffs'])} diffs: " + "; ".join(d["field"] for d in r["diffs"]) if r.get("diffs") else "")
        print(f"[{flag}] {r['op']:16s} step={r.get('step')} {r.get('ms', '')}ms {extra}")
    print(f"console(non-benign)={len(noisy)} pageerrors={len(errors)} requestfailed={len(report['requestfailed'])} http_errors={len(report['http_errors'])} hydrate_ms={hydrate_ms}")
    for c in noisy[:20]:
        print("  console:", c["type"], c["text"][:300])
    for e in errors[:10]:
        print("  pageerror:", e[:300])
    return 0 if report["n_fail"] == 0 and not errors and not [c for c in noisy if c["type"] == "error"] else 1


if __name__ == "__main__":
    sys.exit(main())
