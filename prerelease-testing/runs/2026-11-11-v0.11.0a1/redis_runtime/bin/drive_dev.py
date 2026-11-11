"""#7616 + #7590 driver.
Usage: $SB/envs/driver/bin/python drive_dev.py BASE APP_DIR SERVER_LOG OUT_JSON [--setter-only]
Steps: load, bump twice (n=3, label V1:3), type into the auto-setter input, then (unless --setter-only) edit
CODE_VERSION V1->V2 in devapp.py, wait for the backend reload, reload the page with the same token and read
label/label2/child_label/n (expect V2:3, n kept)."""
import json, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

assert "/envs/driver/" in sys.executable, sys.executable
base, appdir, slog, out = sys.argv[1].rstrip("/"), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
src = appdir / "devapp" / "devapp.py"
R = {"checks": {}, "console": []}


def check(name, ok, **kw):
    R["checks"][name] = {"ok": bool(ok), **kw}
    print(("PASS " if ok else "FAIL ") + name, json.dumps(kw)[:500], flush=True)


def read(page):
    return {i: page.inner_text(f"#{i}") for i in ("label", "label2", "child_label", "n", "pid", "name_out")}


def wait_for(page, sel, pred, timeout=20):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        try:
            if pred(page.inner_text(sel)):
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.1)
    return False


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    page.on("console", lambda m: R["console"].append(f"{m.type}: {m.text[:300]}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: R["console"].append(f"PAGEERROR {str(e)[:300]}"))
    page.goto(base + "/", wait_until="networkidle", timeout=180000)
    wait_for(page, "#label", lambda v: v.startswith("V1:"), 60)
    time.sleep(1)
    page.click("#bump"); page.click("#bump")
    wait_for(page, "#n", lambda v: v == "3")
    before = read(page)
    check("bump", before["n"] == "3" and before["label"] == "V1:3", **before)
    page.fill("#name", "hello")
    ok = wait_for(page, "#name_out", lambda v: v == "hello", 8)
    log = slog.read_text(errors="replace")
    check("auto_setter_set_name", ok, name_out=page.inner_text("#name_out"),
          server_errors=[l for l in log.splitlines() if re.search(r"set_name|has no attribute|Traceback|Error", l)][-5:])
    if "--setter-only" not in sys.argv:
        tok = page.evaluate("() => sessionStorage.getItem('token')")
        n_lines = len(log.splitlines())
        src.write_text(src.read_text().replace('CODE_VERSION = "V1"', 'CODE_VERSION = "V2"'))
        t0 = time.monotonic()
        # wait for the backend to reload: poll the page reload until the hydrate delivers V2 or 60 s pass
        got = None
        for i in range(30):
            time.sleep(2)
            try:
                page.reload(wait_until="networkidle", timeout=60000)
            except Exception:  # noqa: BLE001
                continue
            wait_for(page, "#n", lambda v: v.isdigit(), 10)
            time.sleep(1)
            cur = read(page)
            if cur["label"].startswith("V2") or ("V2" in cur["child_label"]):
                got = cur; break
            if cur["pid"] != before["pid"] and i >= 2:
                # backend restarted (new pid) but cached values still from the old code
                time.sleep(2); page.reload(wait_until="networkidle"); time.sleep(2)
                got = read(page); break
            # child label changed but label not -> stale cached var
            got = cur
        dt = round(time.monotonic() - t0, 1)
        R["after_reload_log"] = slog.read_text(errors="replace").splitlines()[n_lines:][-30:]
        check("hot_reload_cached_recomputed", got and got["label"] == "V2:3" and got["label2"] == "L2[V2:3]" and got["child_label"] == "child-V2:3",
              after=got, waited_s=dt, token_same=page.evaluate("() => sessionStorage.getItem('token')") == tok)
        check("hot_reload_fields_kept", got and got["n"] == "3" and got["name_out"] == "hello", after=got)
        page.click("#bump")
        wait_for(page, "#n", lambda v: v == "4")
        check("after_reload_bump", page.inner_text("#label") == "V2:4", **read(page))
        src.write_text(src.read_text().replace('CODE_VERSION = "V2"', 'CODE_VERSION = "V1"'))
    b.close()
R["console"] = [c for c in R["console"] if "Hey developer" not in c]
out.write_text(json.dumps(R, indent=1))
print("console:", R["console"][:8])
