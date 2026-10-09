"""verify_ent_auth driver (own build, written from the A3-09 / A3-10 repro text only).

Usage: vea_drv.py <scenario> <base_url> <label> [reps]
  storx   A3-10: sign in, fill protected client storage, then client-side navigations / reloads
  xsync   A3-10 extension: two tabs of one browser, sync=True LocalStorage, no navigation at all
  stale   A3-09: tab leaves the app, cookies cleared + token hash "" written, tab returns to /vault
  away    A3-09: tab1 leaves the app, tab2 logs out cleanly, tab1 goes Back
  live    A3-09 control: tab1 stays open on /vault while tab2 logs out (live storage event)
Output: ../out/<label>-<scenario>.json (+ screenshots ../shots/<label>-<scenario>-<rep>-<step>.jpg)
"""

import json
import os
import sys
import time

import playwright

assert ("/envs/" + __import__("os").environ.get("DRV_VENV", "driver") + "/") in playwright.__file__, playwright.__file__

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
SHOTS = os.path.join(HERE, "..", "shots")
IDP = "http://localhost:8638"
FIELDS = ["title", "who", "secret", "draft", "plain", "ck", "ss", "echo", "clicks", "pdraft", "pck", "hyd"]
LS_KEYS = ["vea_draft", "vea_plain", "vea_pub_draft"]


_PAGES = []
DOM_LOG_JS = """
window.__veaLog = [];
const __veaRec = () => { const g = (id) => { const e = document.getElementById(id); return e ? e.textContent : null; };
  const cur = [location.pathname, g('who'), g('secret'), g('draft')].join('|');
  if (window.__veaLast !== cur) { window.__veaLast = cur; window.__veaLog.push([Date.now(), cur]); } };
new MutationObserver(__veaRec).observe(document, {subtree: true, childList: true, characterData: true});
"""


def _nap(s):
    """Sleep while letting Playwright dispatch events (so frame timestamps stay real-time)."""
    for pg in reversed(_PAGES):
        try:
            if not pg.is_closed():
                pg.wait_for_timeout(s * 1000)
                return
        except Exception:  # noqa: BLE001
            continue
    time.sleep(s)


def dom_log(page):
    try:
        return page.evaluate("window.__veaLog || []")
    except Exception:  # noqa: BLE001
        return []


class Rec:
    """Per-page recorder: console, failed requests, websocket frames."""

    def __init__(self, name, page, t0):
        self.name, self.t0 = name, t0
        _PAGES.append(page)
        self.console, self.failed, self.frames = [], [], []
        page.on("console", lambda m: self.console.append([self.t(), m.type, m.text[:300]]))
        page.on("pageerror", lambda e: self.console.append([self.t(), "pageerror", str(e)[:300]]))
        page.on("requestfailed", lambda r: self.failed.append([self.t(), r.method, r.url, r.failure]))
        page.on("response", lambda r: r.status >= 400 and self.failed.append([self.t(), r.request.method, r.url, r.status]))
        page.on("websocket", self._ws)

    def t(self):
        return round(time.time() - self.t0, 3)

    def _ws(self, ws):
        ws.on("framesent", lambda p: self.frames.append([self.t(), "sent", _short(p)]))
        ws.on("framereceived", lambda p: self.frames.append([self.t(), "recv", _short(p)]))

    def dump(self):
        return {"console": self.console, "failed": self.failed, "frames": self.frames}


def _short(p):
    s = p if isinstance(p, str) else repr(p)
    return s[:1500]


def ui(page):
    out = {"url": page.url.split("?")[0]}
    for f in FIELDS:
        try:
            el = page.query_selector(f"#{f}")
            out[f] = el.inner_text() if el else None
        except Exception as e:  # noqa: BLE001
            out[f] = f"<err {type(e).__name__}>"
    return out


def storage(page, ctx):
    st = {}
    try:
        st = page.evaluate(
            """(keys) => { const o = {}; for (const k of keys) o[k] = localStorage.getItem(k);
               o.vea_ss = sessionStorage.getItem('vea_ss');
               o.hash = null; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i);
               if (k.includes('latest_access_token_hash_ls')) o.hash = (localStorage.getItem(k) || '').slice(0, 12); }
               return o; }""",
            LS_KEYS,
        )
    except Exception as e:  # noqa: BLE001
        st = {"err": str(e)[:200]}
    ck = {c["name"]: c["value"] for c in ctx.cookies()}
    st["cookie_vea_ck"] = ck.get("vea_ck")
    st["cookie_vea_pub_ck"] = ck.get("vea_pub_ck")
    st["token_cookies"] = sorted(n for n in ck if "token" in n.lower() or "scopes" in n.lower())
    return st


def snap(page, ctx, step, rows, label, scen, rep, shot=False):
    row = {"step": step, "ui": ui(page), "storage": storage(page, ctx), "t": round(time.time(), 3)}
    rows.append(row)
    print(f"  [{step}] ui={row['ui']} storage={row['storage']}", flush=True)
    if shot:
        page.screenshot(path=os.path.join(SHOTS, f"{label}-{scen}-{rep}-{step}.jpg"), type="jpeg", quality=55)
    return row


def wait_text(page, sel, value, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        el = page.query_selector(sel)
        if el and el.inner_text() == value:
            return True
        time.sleep(0.1)
    return False


def wait_hydrated(page, timeout=20):
    return wait_text(page, "#hyd", "yes", timeout)


def login(page, base, sub="alice", start="/vault"):
    page.goto(base + start)
    page.wait_for_url("**/login**", timeout=30000)
    page.get_by_role("button", name="Login with").click()
    page.wait_for_url(IDP + "/**", timeout=30000)
    page.get_by_role("button", name=f"Authorize as {sub}").click()
    page.wait_for_url(base + start + "**", timeout=30000)
    ok = wait_text(page, "#who", sub, 20)
    wait_hydrated(page)
    return ok


def logout(page, base):
    page.goto(base + "/logout")
    page.wait_for_url(IDP + "/**", timeout=30000)
    page.get_by_role("button", name="End session").click()
    page.wait_for_url(base + "/**", timeout=30000)
    _nap(2)


def clicknav(page, sel, title):
    page.click(sel)
    ok = wait_text(page, "#title", title, 15)
    wait_hydrated(page)
    _nap(2.0)
    return ok


def fill(page):
    page.click("#fill")
    return wait_text(page, "#draft", "draft-of-alice", 10)


def show(page):
    before = (page.query_selector("#clicks") or page).inner_text() if page.query_selector("#clicks") else None
    page.click("#show")
    end = time.time() + 8
    while time.time() < end:
        el = page.query_selector("#clicks")
        if el is None or el.inner_text() != before:
            break
        time.sleep(0.1)
    _nap(0.5)


def poll(page, ctx, secs, rows, step):
    """Record (url, who, secret, draft) changes for `secs` seconds."""
    seq, last, end = [], None, time.time() + secs
    t0 = time.time()
    while time.time() < end:
        try:
            u = ui(page)
            cur = (u["url"], u["who"], u["secret"], u["draft"], u["hyd"])
        except Exception as e:  # noqa: BLE001
            cur = ("<nav>", str(e)[:60])
        if cur != last:
            seq.append([round(time.time() - t0, 2), *cur])
            last = cur
        time.sleep(0.1)
    rows.append({"step": step, "seq": seq})
    print(f"  [{step}] seq={seq}", flush=True)
    return seq


def scen_storx(b, base, label, rep, res):
    ctx = b.new_context()
    ctx.add_init_script(DOM_LOG_JS)
    page = ctx.new_page()
    rec = Rec("tab1", page, time.time())
    res["t0"] = rec.t0
    rows = []
    res["login"] = login(page, base)
    page.click("#pfill")
    wait_text(page, "#pdraft", "pub-draft", 10)
    res["fill0"] = fill(page)
    _nap(1)
    snap(page, ctx, "S0_after_fill", rows, label, "storx", rep)
    clicknav(page, "#to_vault2", "vault2")
    snap(page, ctx, "S1_nav_vault_to_vault2", rows, label, "storx", rep, shot=True)
    show(page)
    snap(page, ctx, "S1b_show_server", rows, label, "storx", rep)
    fill(page)
    _nap(1)
    clicknav(page, "#to_vault", "vault")
    snap(page, ctx, "S2_nav_vault2_to_vault", rows, label, "storx", rep)
    fill(page)
    _nap(1)
    clicknav(page, "#to_home", "home (public)")
    snap(page, ctx, "S3_nav_vault_to_home", rows, label, "storx", rep)
    page.reload()
    wait_hydrated(page)
    _nap(2)
    snap(page, ctx, "S4_reload_home_after_wipe", rows, label, "storx", rep)
    clicknav(page, "#to_vault", "vault")
    show(page)
    snap(page, ctx, "S4b_vault_show_server_after_reload", rows, label, "storx", rep, shot=True)
    # control: fill + full reload (no client nav)
    fill(page)
    _nap(1)
    page.reload()
    wait_hydrated(page)
    _nap(2)
    snap(page, ctx, "S5_fill_then_reload_vault", rows, label, "storx", rep)
    res["rows"] = rows
    res["tab1"] = rec.dump()
    ctx.close()


def scen_xsync(b, base, label, rep, res):
    ctx = b.new_context()
    a = ctx.new_page()
    rec_a = Rec("tabA", a, time.time())
    rows = []
    res["login"] = login(a, base)
    bb = ctx.new_page()
    rec_b = Rec("tabB", bb, rec_a.t0)
    bb.goto(base + "/vault")
    res["tabB_who"] = wait_text(bb, "#who", "alice", 20)
    wait_hydrated(bb)
    _nap(3)
    snap(a, ctx, "A0", rows, label, "xsync", rep)
    snap(bb, ctx, "B0", rows, label, "xsync", rep)
    a.bring_to_front()
    a.click("#fill")
    _nap(4)
    snap(a, ctx, "A1_after_fill_in_A", rows, label, "xsync", rep, shot=True)
    snap(bb, ctx, "B1_after_fill_in_A", rows, label, "xsync", rep)
    # public sync var control
    a.click("#pfill")
    _nap(3)
    snap(a, ctx, "A2_after_pfill", rows, label, "xsync", rep)
    snap(bb, ctx, "B2_after_pfill", rows, label, "xsync", rep)
    res["rows"] = rows
    res["tabA"] = rec_a.dump()
    res["tabB"] = rec_b.dump()
    ctx.close()


def _hash_key(page):
    return page.evaluate(
        "() => { for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i);"
        " if (k.includes('latest_access_token_hash_ls')) return k; } return null; }"
    )


def _after_return(page, ctx, rows, label, scen, rep, res):
    poll(page, ctx, 8, rows, "P_boot_seq")
    r = snap(page, ctx, "P_after_boot", rows, label, scen, rep, shot=True)
    res["after_boot"] = [r["ui"]["url"], r["ui"]["who"], r["ui"]["secret"], r["ui"]["draft"]]
    log = dom_log(page)
    res["dom_log"] = log
    mark_ms = (res["t0"] + res["mark_t"]) * 1000
    shown = [e for e in log if e[0] >= mark_ms - 50 and "secret-of-alice" in e[1]]
    res["flash"] = None
    if shown:
        after = [e for e in log if e[0] > shown[0][0] and "secret-of-alice" not in e[1]]
        res["flash"] = {"first_ms_after_return": round(shown[0][0] - mark_ms), "visible_ms": (round(after[0][0] - shown[0][0]) if after else "still")}
    print(f"  flash={res['flash']} dom_log_tail={log[-6:]}", flush=True)
    if "/vault" in r["ui"]["url"] and page.query_selector("#show"):
        t_click = time.time()
        page.click("#show")
        seq = poll(page, ctx, 6, rows, "P_click_seq")
        r2 = snap(page, ctx, "P_after_protected_click", rows, label, scen, rep)
        res["after_click"] = [r2["ui"]["url"], r2["ui"]["who"], r2["ui"]["clicks"], r2["ui"]["echo"]]
        res["click_seq"] = seq


def scen_stale(b, base, label, rep, res):
    ctx = b.new_context()
    ctx.add_init_script(DOM_LOG_JS)
    page = ctx.new_page()
    rec = Rec("tab1", page, time.time())
    res["t0"] = rec.t0
    rows = []
    res["login"] = login(page, base)
    fill(page)
    _nap(1)
    snap(page, ctx, "S0_signed_in", rows, label, "stale", rep)
    key = _hash_key(page)
    res["hash_key"] = key
    page.goto(base + "/blank.html")
    ctx.clear_cookies()
    page.evaluate("(k) => localStorage.setItem(k, '')", key)
    res["mark_t"] = rec.t()
    page.goto(base + "/vault")
    _after_return(page, ctx, rows, label, "stale", rep, res)
    res["rows"] = rows
    res["tab1"] = rec.dump()
    ctx.close()


def scen_away(b, base, label, rep, res):
    ctx = b.new_context()
    ctx.add_init_script(DOM_LOG_JS)
    page = ctx.new_page()
    rec = Rec("tab1", page, time.time())
    res["t0"] = rec.t0
    rows = []
    res["login"] = login(page, base)
    fill(page)
    _nap(1)
    page.goto(base + "/blank.html")
    t2 = ctx.new_page()
    rec2 = Rec("tab2", t2, rec.t0)
    t2.goto(base + "/")
    wait_hydrated(t2)
    _nap(1)
    logout(t2, base)
    snap(t2, ctx, "T2_after_logout", rows, label, "away", rep)
    t2.close()
    page.bring_to_front()
    res["mark_t"] = rec.t()
    page.go_back()
    _after_return(page, ctx, rows, label, "away", rep, res)
    res["rows"] = rows
    res["tab1"] = rec.dump()
    res["tab2"] = rec2.dump()
    ctx.close()


def scen_live(b, base, label, rep, res):
    ctx = b.new_context()
    ctx.add_init_script(DOM_LOG_JS)
    page = ctx.new_page()
    rec = Rec("tab1", page, time.time())
    res["t0"] = rec.t0
    rows = []
    res["login"] = login(page, base)
    fill(page)
    _nap(1)
    t2 = ctx.new_page()
    rec2 = Rec("tab2", t2, rec.t0)
    t2.goto(base + "/")
    wait_hydrated(t2)
    _nap(1)
    res["mark_t"] = rec.t()
    logout(t2, base)
    page.bring_to_front()
    _after_return(page, ctx, rows, label, "live", rep, res)
    res["rows"] = rows
    res["tab1"] = rec.dump()
    res["tab2"] = rec2.dump()
    ctx.close()


def scen_stalenav(b, base, label, rep, res):
    """stale, then in the blanked state: public event, then client-side nav to another protected page."""
    ctx = b.new_context()
    ctx.add_init_script(DOM_LOG_JS)
    page = ctx.new_page()
    rec = Rec("tab1", page, time.time())
    res["t0"] = rec.t0
    rows = []
    res["login"] = login(page, base)
    fill(page)
    _nap(1)
    key = _hash_key(page)
    page.goto(base + "/blank.html")
    ctx.clear_cookies()
    page.evaluate("(k) => localStorage.setItem(k, '')", key)
    res["mark_t"] = rec.t()
    page.goto(base + "/vault")
    poll(page, ctx, 5, rows, "P_boot_seq")
    r = snap(page, ctx, "P_after_boot", rows, label, "stalenav", rep)
    res["after_boot"] = [r["ui"]["url"], r["ui"]["who"], r["ui"]["secret"], r["ui"]["draft"]]
    if page.query_selector("#pfill"):
        page.click("#pfill")
        _nap(2)
        r = snap(page, ctx, "P_after_public_event", rows, label, "stalenav", rep)
        res["after_public"] = [r["ui"]["url"], r["ui"]["pdraft"]]
    if page.query_selector("#to_vault2"):
        page.click("#to_vault2")
        seq = poll(page, ctx, 5, rows, "P_nav_seq")
        res["after_nav"] = seq[-1][:3] if seq else None
    res["rows"] = rows
    res["tab1"] = rec.dump()
    ctx.close()


SCEN = {"stalenav": scen_stalenav, "storx": scen_storx, "xsync": scen_xsync, "stale": scen_stale, "away": scen_away, "live": scen_live}


def main():
    scen, base, label = sys.argv[1], sys.argv[2].rstrip("/"), sys.argv[3]
    reps = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(SHOTS, exist_ok=True)
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        for rep in range(reps):
            res = {"rep": rep, "scenario": scen, "label": label}
            print(f"== {label} {scen} rep {rep}", flush=True)
            try:
                SCEN[scen](b, base, label, rep, res)
            except Exception as e:  # noqa: BLE001
                res["error"] = f"{type(e).__name__}: {e}"[:500]
                print("  ERROR", res["error"], flush=True)
            results.append(res)
        b.close()
    path = os.path.join(OUT, f"{label}-{scen}.json")
    with open(path, "w") as f:
        json.dump(results, f, indent=1)
    print("WROTE", path)


if __name__ == "__main__":
    main()
