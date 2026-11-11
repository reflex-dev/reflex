"""hot_reload.py <venv> <appdir> <fp> <bp> <out.json> [--env KEY=VAL ...] [--label x]

Driver venv. Starts `reflex run` (dev) on a FRESH copy of hotapp, waits for the backend, then applies a
sequence of edits and checks each one through the browser and /ping timing:
  1. baseline: bump -> "v1 h1"
  2. edit the state handler (APP_VERSION v2)            -> reload, bump shows v2
  3. edit the helper module (HELPER_VERSION h2)          -> reload, bump shows h2
  4. add a state var + page (/about with AboutState)     -> /about renders the new state
  5. break the app module (SyntaxError) -> while broken: /ping refused fast or hangs? (CLI-16) -> fix -> recovers
  6. edit rxconfig.py (qa_marker attribute)              -> is it picked up?
  7. state continuity: count survives reloads?
Backend liveness is measured with raw TCP connects (refused vs accepted-but-unanswered vs 200).
Server log is scanned for tracebacks / "Unexpected exit".
"""

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

assert ("/envs/" + os.environ.get("DRIVER", "driver") + "/") in sys.executable, sys.executable
venv, appdir, fp, bp, out = sys.argv[1:6]
rest = sys.argv[6:]
extra_env = {}
label = "run"
i = 0
while i < len(rest):
    if rest[i] == "--env":
        k, v = rest[i + 1].split("=", 1)
        extra_env[k] = v
        i += 2
    elif rest[i] == "--label":
        label = rest[i + 1]
        i += 2
    else:
        i += 1
SB = os.environ["SB"]
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
checks = []
timeline = []
APP = os.path.join(appdir, "hotapp", "hotapp.py")
HELPER = os.path.join(appdir, "hotapp", "helper.py")
RXCONF = os.path.join(appdir, "rxconfig.py")


def check(name, ok, detail=""):
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(("PASS " if ok else "FAIL ") + name + (f": {detail}" if detail else ""), flush=True)


def ping(timeout=2.0):
    """Returns ('200', dt) | ('refused', dt) | ('timeout', dt) | ('err', dt)."""
    t0 = time.monotonic()
    try:
        with opener.open(f"http://127.0.0.1:{bp}/ping", timeout=timeout) as r:
            return str(r.status), time.monotonic() - t0
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        if isinstance(reason, ConnectionRefusedError) or "refused" in str(reason).lower():
            return "refused", time.monotonic() - t0
        if isinstance(reason, (socket.timeout, TimeoutError)) or "timed out" in str(reason).lower():
            return "timeout", time.monotonic() - t0
        return f"err:{reason}", time.monotonic() - t0
    except (socket.timeout, TimeoutError):
        return "timeout", time.monotonic() - t0
    except Exception as e:  # noqa: BLE001
        return f"err:{type(e).__name__}", time.monotonic() - t0


def tcp_connect():
    t0 = time.monotonic()
    s = socket.socket()
    s.settimeout(2)
    try:
        s.connect(("127.0.0.1", int(bp)))
        return "accepted", time.monotonic() - t0
    except ConnectionRefusedError:
        return "refused", time.monotonic() - t0
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}", time.monotonic() - t0
    finally:
        s.close()


def wait_ping(want="200", secs=60):
    t0 = time.monotonic()
    while time.monotonic() - t0 < secs:
        st, _ = ping()
        if st == want:
            return time.monotonic() - t0
        time.sleep(0.2)
    return None


def edit(path, old, new):
    s = open(path).read()
    assert old in s, (path, old)
    open(path, "w").write(s.replace(old, new))
    timeline.append((round(time.monotonic() - T0, 2), f"edit {os.path.basename(path)}: {old[:30]!r} -> {new[:30]!r}"))


def text(page, sel):
    return page.locator(sel).inner_text()


def wait_text(page, sel, pred, timeout=20.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        try:
            t = text(page, sel)
            if pred(t):
                return t
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.15)
    try:
        return text(page, sel)
    except Exception as e:  # noqa: BLE001
        return f"<{type(e).__name__}>"


def wait_reload(prev_pid, secs=40):
    """Wait until a new worker serves /ping (worker pid changes) and return (new_pid, seconds)."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < secs:
        try:
            with opener.open(f"http://127.0.0.1:{bp}/api/pid", timeout=2) as r:
                pid = json.load(r)["pid"]
                if pid != prev_pid:
                    return pid, round(time.monotonic() - t0, 2)
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.2)
    return None, None


T0 = time.monotonic()
# fresh copy of the app
src = os.path.join(SB, "apps", "process_model", "hotapp")
if os.path.abspath(appdir) != os.path.abspath(src):
    shutil.rmtree(appdir, ignore_errors=True)
    shutil.copytree(src, appdir, ignore=shutil.ignore_patterns(".web", "__pycache__", ".states"))
# add a /api/pid route so the driver can see the worker pid without a browser
edit(APP, "app = rx.App()\n", "from starlette.applications import Starlette\nfrom starlette.responses import JSONResponse\nfrom starlette.routing import Route\n\nasync def _pid(request):\n    return JSONResponse({'pid': os.getpid(), 'app_version': APP_VERSION})\n\napp = rx.App(api_transformer=Starlette(routes=[Route('/api/pid', _pid)]))\n")
env = {k: v for k, v in os.environ.items() if k.lower() not in ("no_proxy",)}
env.update(REFLEX_TELEMETRY_ENABLED="false", EXPECT_VENV=venv, HOT_MARKER="m1")
env.update(extra_env)
logf = open(out + ".server.log", "wb")
T0 = time.monotonic()
proc = subprocess.Popen([f"{SB}/envs/{venv}/bin/reflex", "run", "--frontend-port", fp, "--backend-port", bp, "--loglevel", "debug"],
                        cwd=appdir, stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, start_new_session=True)
try:
    up = wait_ping("200", 420)
    check("backend_up", up is not None, f"{up and round(up, 1)}s")
    fe_t0 = time.monotonic()
    while time.monotonic() - fe_t0 < 420:
        try:
            if opener.open(f"http://127.0.0.1:{fp}/", timeout=3).status == 200:
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)
    check("frontend_up", True, f"{round(time.monotonic() - fe_t0, 1)}s")
    with opener.open(f"http://127.0.0.1:{bp}/api/pid", timeout=5) as r:
        pid0 = json.load(r)["pid"]
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = browser.new_context()
        page = ctx.new_page()
        console = []
        page.on("console", lambda m: console.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda ex: console.append(f"pageerror: {ex}"))
        page.goto(f"http://127.0.0.1:{fp}/", wait_until="load")
        wait_text(page, "#label", lambda s: "h1" in s, 60)
        page.click("#bump")
        t = wait_text(page, "#label", lambda s: "v1 h1" in s)
        check("1_baseline_bump", "v1 h1" in t and "env=m1" in t, t)

        # 2. edit the state handler / module constant
        edit(APP, 'APP_VERSION = "v1"', 'APP_VERSION = "v2"')
        pid1, dt = wait_reload(pid0)
        check("2_reload_after_handler_edit", pid1 is not None, f"new worker {pid1} after {dt}s")
        page.click("#bump")
        t = wait_text(page, "#label", lambda s: "v2" in s)
        check("2_handler_edit_visible", "v2 h1" in t, t)
        cnt = text(page, "#count")
        check("2_count_after_reload", True, f"{cnt} (dev: state survives reload? count was 1 before edit)")

        # 3. edit the helper module
        edit(HELPER, 'HELPER_VERSION = "h1"', 'HELPER_VERSION = "h2"')
        pid2, dt = wait_reload(pid1)
        check("3_reload_after_helper_edit", pid2 is not None, f"new worker {pid2} after {dt}s")
        time.sleep(2)  # let the frontend rebuild / page reload (on_load) settle before clicking
        page.click("#bump")
        t = wait_text(page, "#label", lambda s: "v2 h2" in s)
        if "v2 h2" not in t:
            page.click("#bump")
            t = wait_text(page, "#label", lambda s: "v2 h2" in s)
        check("3_helper_edit_visible", "v2 h2" in t, t)

        # 4. add a state var + a new page with a new state
        edit(APP, "# MARKER: new pages / states get added below this line by the driver\n",
             "class AboutState(rx.State):\n    msg: str = 'about-default'\n    extra: int = 7\n\n    @rx.event\n    def hello(self):\n        self.msg = f'hello {self.extra} pid={os.getpid()}'\n\n\ndef about() -> rx.Component:\n    return rx.container(rx.heading('about', id='title'), rx.text('msg: ', AboutState.msg, id='msg'), rx.button('hello', on_click=AboutState.hello, id='hello'))\n\n\napp.add_page(about, route='/about')\n")
        edit(APP, "    pid: int = 0\n", "    pid: int = 0\n    added: str = 'added-default'\n")
        edit(APP, 'rx.text("pid: ", State.pid, id="pid"),', 'rx.text("pid: ", State.pid, id="pid"),\n            rx.text("added: ", State.added, id="added"),')
        pid3, dt = wait_reload(pid2)
        check("4_reload_after_add_page_state", pid3 is not None, f"new worker {pid3} after {dt}s")
        time.sleep(3)  # frontend recompile
        page.goto(f"http://127.0.0.1:{fp}/", wait_until="load")
        t = wait_text(page, "#added", lambda s: "added-default" in s, 40)
        check("4_new_var_renders", "added-default" in t, t)
        page.goto(f"http://127.0.0.1:{fp}/about", wait_until="load")
        t = wait_text(page, "#msg", lambda s: "about-default" in s, 40)
        check("4_new_page_renders", "about-default" in t, t)
        page.click("#hello")
        t = wait_text(page, "#msg", lambda s: "hello 7" in s, 20)
        check("4_new_state_handler_works", "hello 7" in t, t)

        # 5. break the module, probe the port while broken, fix
        edit(APP, 'APP_VERSION = "v2"', 'APP_VERSION = "v3"\nthis is a syntax error\n')
        # wait for the worker to go away / restart
        t_break = time.monotonic()
        time.sleep(2.5)
        probes = []
        for _ in range(6):
            st, dt = ping(timeout=3.0)
            tc, dtc = tcp_connect()
            probes.append({"t": round(time.monotonic() - t_break, 2), "ping": st, "ping_s": round(dt, 2), "tcp": tc})
            time.sleep(0.5)
        statuses = {pr["ping"] for pr in probes}
        slow = [pr for pr in probes if pr["ping"] == "timeout"]
        check("5_broken_backend_refuses_fast", "timeout" not in statuses, json.dumps(probes))
        log = open(out + ".server.log", "rb").read().decode(errors="replace")
        check("5_syntax_error_logged", "SyntaxError" in log, f"SyntaxError in server log: {'SyntaxError' in log}")
        edit(APP, 'APP_VERSION = "v3"\nthis is a syntax error\n', 'APP_VERSION = "v3"\n')
        rec = wait_ping("200", 60)
        check("5_recovers_after_fix", rec is not None, f"200 after {rec and round(rec, 1)}s")
        with opener.open(f"http://127.0.0.1:{bp}/api/pid", timeout=5) as r:
            d = json.load(r)
        check("5_new_code_served", d["app_version"] == "v3", d)
        page.goto(f"http://127.0.0.1:{fp}/", wait_until="load")
        wait_text(page, "#label", lambda s: "h2" in s or "pid" in s, 40)
        page.click("#bump")
        t = wait_text(page, "#label", lambda s: "v3" in s)
        check("5_browser_sees_v3", "v3 h2" in t, t)

        # 6. rxconfig edit
        edit(RXCONF, "    app_name=\"hotapp\",\n", "    app_name=\"hotapp\",\n    qa_marker=\"cfg2\",\n")
        pid4, dt = wait_reload(d["pid"], 30)
        page.click("#bump")
        t = wait_text(page, "#label", lambda s: "cfg2" in s, 15)
        check("6_rxconfig_edit_picked_up", "cfg2" in t, f"reload={pid4 is not None} ({dt}s) label={t!r}")

        # 7. one more handler edit to confirm reload still works after everything
        edit(APP, 'APP_VERSION = "v3"', 'APP_VERSION = "v4"')
        with opener.open(f"http://127.0.0.1:{bp}/api/pid", timeout=5) as r:
            cur = json.load(r)["pid"]
        pid5, dt = wait_reload(cur, 40)
        page.click("#bump")
        t = wait_text(page, "#label", lambda s: "v4" in s)
        check("7_final_handler_edit", "v4" in t, f"{t!r} reload {dt}s")
        bad = [c for c in console if not re.search(r"Hey developer|HydrateFallback|\[vite\]|React DevTools|favicon|Failed to load resource.*404", c)]
        check("console_clean", not bad, " | ".join(bad)[:500])
        browser.close()
finally:
    t_stop = time.monotonic()
    proc.send_signal(signal.SIGTERM)
    try:
        rc = proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        rc = "TIMEOUT"
    stop_s = round(time.monotonic() - t_stop, 2)
    time.sleep(1)
    left = subprocess.run(["bash", "-c", f"ps -o pid=,cmd= -s {proc.pid} 2>/dev/null | cut -c1-120"], capture_output=True, text=True).stdout.strip()
    if left:
        os.killpg(proc.pid, signal.SIGKILL)
    st_after, _ = ping(1.0)
    logf.close()
    log = open(out + ".server.log", "rb").read().decode(errors="replace")
    summary = {
        "label": label, "venv": venv, "extra_env": extra_env, "checks": checks, "timeline": timeline,
        "pass": sum(c["ok"] for c in checks), "fail": sum(not c["ok"] for c in checks),
        "stop": {"rc": rc, "seconds": stop_s, "leftovers": left, "ping_after": st_after},
        "log": {"unexpected_exit": log.count("Unexpected exit"), "tracebacks": log.count("Traceback (most recent"),
                "spawning_worker": log.count("Spawning worker"), "errors": [l for l in log.splitlines() if "[ERROR]" in l or "Error:" in l][:10]},
    }
    json.dump(summary, open(out, "w"), indent=1)
    print(f"== {label}: pass={summary['pass']} fail={summary['fail']} stop={summary['stop']} log={summary['log']}")
