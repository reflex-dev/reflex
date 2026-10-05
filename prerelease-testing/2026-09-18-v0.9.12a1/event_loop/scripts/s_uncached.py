"""Scenario: #6946 uncached var delta dedupe. Usage: s_uncached.py <base_url> <outdir>"""

import sys
import time

sys.argv = [sys.argv[0], "uncached", *sys.argv[1:]]
from wsdrive import (  # noqa: E402
    BASE,
    OUT,
    attach,
    delta_keys,
    deltas,
    dump,
    frames,
    log,
    txt,
)
from playwright.sync_api import sync_playwright  # noqa: E402


def keys_since(t0, ctx=None):
    out = []
    for t, c, name, payload in deltas(t0, ctx):
        if name != "event":
            continue
        k = delta_keys(payload)
        if k:
            out.append((c, k))
    return out


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    attach(page, "c1")
    page.goto(f"{BASE}/uncached", wait_until="networkidle")
    page.wait_for_selector("#v-u_stable", timeout=30000)
    time.sleep(1.5)
    log("=== hydrate frames (first 3 in) ===")
    for t, c, n, pl in deltas()[:3]:
        log(" ", c, n, str(pl)[:400])

    log("\n=== initial rendered values ===")
    for sel in [
        "counter",
        "u_stable",
        "u_derived",
        "u_alt",
        "u_nan",
        "u_list",
        "u_dict",
        "u_async",
        "u_parent",
        "u_obj",
    ]:
        log(f"  {sel:10s} = {txt(page, f'#v-{sel}')!r}")

    # 1. hammer an unrelated event: no uncached var should appear in deltas
    t0 = time.time()
    for _ in range(3):
        page.click("#touch")
        page.wait_for_timeout(250)
    log("\n=== after 3x touch (unrelated var) ===")
    for c, k in keys_since(t0):
        log("  delta:", k)

    # 2. noop event: does anything get sent at all?
    t0 = time.time()
    for _ in range(2):
        page.click("#noop")
        page.wait_for_timeout(250)
    log("\n=== after 2x noop ===")
    for c, k in keys_since(t0):
        log("  delta:", k)

    # 3. bumps: u_alt flips every bump, u_derived every 3, u_async every 4
    for i in range(1, 7):
        t0 = time.time()
        page.click("#bump")
        page.wait_for_timeout(350)
        log(f"\n=== bump -> counter={i} ===")
        for c, k in keys_since(t0):
            log("  delta:", k)
        log(
            "  rendered:",
            {
                s: txt(page, f"#v-{s}")
                for s in ("u_derived", "u_alt", "u_async", "u_parent")
            },
        )

    # 4. reset: counter goes back to 0, so u_alt returns to "A", u_derived to d0
    t0 = time.time()
    page.click("#reset")
    page.wait_for_timeout(400)
    log("\n=== after reset (values return to earlier values) ===")
    for c, k in keys_since(t0):
        log("  delta:", k)
    log(
        "  rendered:",
        {s: txt(page, f"#v-{s}") for s in ("counter", "u_derived", "u_alt", "u_async")},
    )

    # 5. unkeyable-ish: complex values serialize to null
    t0 = time.time()
    for _ in range(3):
        page.click("#bumpobj")
        page.wait_for_timeout(250)
    log("\n=== after 3x bump-obj (complex -> null) ===")
    for c, k in keys_since(t0):
        log("  delta:", k)

    # 6. hard reload: same sessionStorage token, must re-hydrate fully
    page.reload(wait_until="networkidle")
    page.wait_for_selector("#v-u_stable", timeout=30000)
    time.sleep(1.5)
    log("\n=== after hard reload (same token) ===")
    for sel in ("counter", "u_stable", "u_derived", "u_alt", "u_async", "u_parent"):
        log(f"  {sel:10s} = {txt(page, f'#v-{sel}')!r}")
    page.screenshot(path=str(OUT / "uncached_after_reload.png"))

    # 7. second browser CONTEXT = separate token: must get its own values
    ctx2 = b.new_context()
    page2 = ctx2.new_page()
    attach(page2, "c2")
    page2.goto(f"{BASE}/uncached", wait_until="networkidle")
    page2.wait_for_selector("#v-u_stable", timeout=30000)
    time.sleep(1.5)
    log("\n=== second context values ===")
    for sel in ("counter", "u_stable", "u_derived", "u_alt", "u_async", "u_parent"):
        log(f"  {sel:10s} = {txt(page2, f'#v-{sel}')!r}")
    t0 = time.time()
    page2.click("#touch")
    page2.wait_for_timeout(400)
    log("  c2 touch deltas:", keys_since(t0, "c2"))
    page2.screenshot(path=str(OUT / "uncached_ctx2.png"))

    # 8. client-side navigation away and back
    t0 = time.time()
    page.click("text=home")
    page.wait_for_selector("#ready", timeout=15000)
    page.click("#l-uncached")
    page.wait_for_selector("#v-u_stable", timeout=15000)
    time.sleep(1.0)
    log("\n=== after client-side nav away and back ===")
    for sel in ("counter", "u_stable", "u_derived", "u_alt", "u_async", "u_parent"):
        log(f"  {sel:10s} = {txt(page, f'#v-{sel}')!r}")

    page.screenshot(path=str(OUT / "uncached_final.png"))
    dump("uncached")
    log("\n=== console (non-benign) ===")
    from wsdrive import console_log, errors, net  # noqa: E402

    for line in console_log:
        if any(
            s in line
            for s in ("Hey developer", "connecting", "connected", "React DevTools")
        ):
            continue
        log("  ", line)
    log("=== pageerrors ===")
    for e in errors:
        log("  ", e)
    log("=== net ===")
    for n in net:
        log("  ", n)
    log("frames total:", len(frames))
    ctx.close()
    ctx2.close()
    b.close()
