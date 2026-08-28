"""Independent verifier for: 'background-task on_load is cancelled on navigation'.

Usage: python drive_verify.py <base_url> <shots_dir>

Tests:
  A control : /slowbg bg on_load completes when the user stays on the page.
  B repro   : client-nav to /slowbg, wait for start, client-nav to /other,
              wait 6s -> did any further step land?
  C contrast: button-started bg task on /other, client-nav to /, wait 6s ->
              did it complete?
Prints RESULT lines and a final JSON blob.
"""

import json
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOTS = sys.argv[2]

import os

os.makedirs(SHOTS, exist_ok=True)

out = {}
console = []


def log_of(page):
    return page.locator("#bg-log").inner_text(timeout=5000)


def wait_hd(page, exp, timeout=15000):
    page.wait_for_function(
        "exp => document.querySelector('#hd') && document.querySelector('#hd').innerText === exp",
        arg=exp,
        timeout=timeout,
    )


def wait_log_contains(page, needle, timeout=10000):
    page.wait_for_function(
        "n => document.querySelector('#bg-log') && document.querySelector('#bg-log').innerText.includes(n)",
        arg=needle,
        timeout=timeout,
    )


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_context().new_page()
    page.on("console", lambda m: console.append((m.type, m.text)))
    page.on("pageerror", lambda e: console.append(("pageerror", str(e))))

    # A: control — stay on /slowbg, bg on_load must complete.
    page.goto(BASE + "/slowbg", wait_until="load", timeout=60000)
    wait_hd(page, "SLOWBG")
    wait_log_contains(page, "load1-start")
    page.wait_for_timeout(6000)
    a_log = log_of(page)
    out["A_control_stay"] = a_log
    page.screenshot(path=f"{SHOTS}/A_control.png")
    print("RESULT A (stayed on page):", a_log, flush=True)

    # reset state via /other's clear button (client-side nav)
    page.click("#lnk-other")
    wait_hd(page, "OTHER")
    page.click("#btn-clear")
    page.wait_for_timeout(500)

    # B: repro — client-nav to /slowbg, see start, client-nav away, wait 6s.
    page.click("#lnk-slowbg")
    wait_hd(page, "SLOWBG")
    wait_log_contains(page, "load1-start")  # runs was reset by clear
    at_nav = log_of(page)
    page.click("#lnk-other")
    wait_hd(page, "OTHER")
    t_nav = time.time()
    page.wait_for_timeout(6000)
    b_log = log_of(page)
    out["B_at_nav"] = at_nav
    out["B_after_6s"] = b_log
    page.screenshot(path=f"{SHOTS}/B_after_nav.png")
    print("RESULT B at-nav:", at_nav, flush=True)
    print("RESULT B after-6s:", b_log, flush=True)

    # C: contrast — button-started bg task then client-nav away.
    page.click("#btn-clear")
    page.wait_for_timeout(500)
    page.click("#btn-bg")
    wait_log_contains(page, "btn-start")
    page.click("#lnk-home")
    wait_hd(page, "HOME")
    page.wait_for_timeout(6000)
    c_log = log_of(page)
    out["C_button_after_nav"] = c_log
    page.screenshot(path=f"{SHOTS}/C_button.png")
    print("RESULT C button bg after nav:", c_log, flush=True)

    out["console"] = [f"{t}:{m}" for t, m in console]
    browser.close()

print("JSON:" + json.dumps(out))
