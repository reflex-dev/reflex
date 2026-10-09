"""Dev hot reload of the file declaring the states (apps/cse2e copy; uses Field.set_default) while `reflex run` (dev) is up.
Usage: NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python hot_reload.py <app_dir> <server_log> <base> <out.json>
Each step edits the run copy, waits for the backend to reload, loads /misc in a fresh context and reads #limit/#hr;
records new log lines containing Traceback/TypeError/Error."""
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

assert f"/envs/{os.environ.get('DRIVER', 'driver')}/" in sys.executable, sys.executable  # playwright venv ($DRIVER)
app_dir, log, base, out = sys.argv[1:5]
SRC = f"{app_dir}/cse2e/cse2e.py"
STEPS = [
    ("add var hr + field default", [
        ("    log: list[str] = []\n", "    log: list[str] = []\n    hr: int = 5\n"),
        ('Svc.__fields__["_quota"].set_default(10)\n', 'Svc.__fields__["_quota"].set_default(10)\nSvc.__fields__["hr"].set_default(6)\n'),
        ('        rx.text(Svc.limit, id="limit"),\n', '        rx.text(Svc.limit, id="limit"),\n        rx.text(Svc.hr, id="hr"),\n'),
    ], {"limit": "10", "hr": "6"}),
    ("change field-configured default limit 10->12", [('Svc.__fields__["limit"].set_default(10)\n', 'Svc.__fields__["limit"].set_default(12)\n'), ('Svc.__fields__["items"].set_default(["cfg"])\n', 'Svc.__fields__["items"].set_default(["cfg2"])\n')], {"limit": "12", "hr": "6", "items": "cfg2"}),
    ("rename var hr->hr2", [("    hr: int = 5\n", "    hr2: int = 5\n"), ('Svc.__fields__["hr"]', 'Svc.__fields__["hr2"]'), ("rx.text(Svc.hr, ", "rx.text(Svc.hr2, ")], {"limit": "12", "hr": "6", "items": "cfg2"}),
    ("change declared default in class body (hr2 5->9, drop field config)", [("    hr2: int = 5\n", "    hr2: int = 9\n"), ('Svc.__fields__["hr2"].set_default(6)\n', "")], {"limit": "12", "hr": "9", "items": "cfg2"}),
    ("remove var hr2", [("    hr2: int = 9\n", ""), ('        rx.text(Svc.hr2, id="hr"),\n', '        rx.text("gone", id="hr"),\n')], {"limit": "12", "hr": "gone", "items": "cfg2"}),
    ("add a class assignment (user error) -> TypeError expected", [('Svc.CFG = 7  # ClassVar: assignable\n', 'Svc.CFG = 7  # ClassVar: assignable\nSvc.limit = 3  # USER ERROR\n')], None),
    ("fix it again", [('Svc.limit = 3  # USER ERROR\n', '')], {"limit": "12", "hr": "gone", "items": "cfg2"}),
]


def log_size():
    return len(open(log, errors="replace").read())


def new_log(since):
    return open(log, errors="replace").read()[since:]


res = []
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=os.environ.get("CHROMIUM", "/opt/pw-browsers/chromium"))
    for name, edits, want in STEPS:
        src = open(SRC).read()
        for old, new in edits:
            assert old in src, (name, old)
            src = src.replace(old, new)
        mark = log_size()
        open(SRC, "w").write(src)
        # wait for the reload to settle: "Reloading"/compile lines, then quiet for 4 s
        t0 = time.time()
        last = mark
        quiet_since = time.time()
        while time.time() - t0 < 120:
            time.sleep(1)
            sz = log_size()
            if sz != last:
                last, quiet_since = sz, time.time()
            elif sz > mark and time.time() - quiet_since > 5:
                break
        chunk = new_log(mark)
        errs = [ln for ln in chunk.splitlines() if re.search(r"Traceback|TypeError|Error|error", ln) and "[vite]" not in ln]
        got, console = None, []
        if want is not None:
            ctx = b.new_context()
            p = ctx.new_page()
            p.on("console", lambda m: console.append(f"{m.type}: {m.text[:200]}") if m.type in ("error", "warning") else None)
            p.on("pageerror", lambda e: console.append(f"PAGEERROR {str(e)[:200]}"))
            try:
                p.goto(base + "/misc", wait_until="networkidle", timeout=120000)
                p.wait_for_function("() => document.querySelector('#hyd')?.textContent === 'H:yes'", timeout=60000)
                time.sleep(1)
                got = {"limit": p.inner_text("#limit"), "hr": p.inner_text("#hr") if p.query_selector("#hr") else None}
                items = p.inner_text("#items")
                if items != "cfg":
                    got["items"] = items
            except Exception as e:  # noqa: BLE001
                got = f"EXC {type(e).__name__}: {str(e)[:200]}"
            ctx.close()
        r = {"step": name, "reload_s": round(time.time() - t0, 1), "want": want, "got": got, "pass": (got == want) if want else None,
             "log_errors": errs[:12], "console": console, "log_tail": chunk.splitlines()[-6:]}
        res.append(r)
        print(json.dumps({k: r[k] for k in ("step", "reload_s", "want", "got", "pass")}), "| log errors:", len(errs), errs[:3], "| console:", console[:3])
    b.close()
open(out, "w").write(json.dumps(res, indent=1))
