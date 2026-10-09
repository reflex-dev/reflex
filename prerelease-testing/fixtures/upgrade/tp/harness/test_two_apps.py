"""Two different AppHarness apps that BOTH import reflex-local-auth, started one after the other in ONE pytest process.

#7359 ("AppHarness forgets the states of all app modules") must not break the package-level states
(`reflex_local_auth.LocalAuthState`, ...) that app B re-uses after app A has been torn down.

Run (from this directory, never from a checkout):
  TP_VENV=thirdparty_a2-a2 TP_FP=3464 TP_BP=8464 $SB/envs/thirdparty_a2-a2/bin/python -m pytest -x -s -p no:cacheprovider test_two_apps.py
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pytest

from test_local_auth_harness import CHROMIUM, SRC, PinnedHarness, _wait_url  # noqa: F401  (also validates TP_VENV/ports)

MIN_SRC = SRC.parent / "local_auth_min"


def _flow_demo(base: str, pg) -> None:
    user = f"twoA{int(time.time()) % 100000}"
    pg.goto(base + "/need2login")
    assert _wait_url(pg, r"/login$"), pg.url
    pg.goto(base + "/register")
    pg.wait_for_selector("input#username")
    pg.fill("input#username", user)
    pg.fill("input#password", "pw-123456")
    pg.fill("input#confirm_password", "pw-123456")
    pg.get_by_role("button", name="Sign up").click()
    pg.wait_for_selector("text=Registration successful!")
    assert _wait_url(pg, r"/login$"), pg.url
    pg.fill("input#username", user)
    pg.fill("input#password", "pw-123456")
    pg.get_by_role("button", name="Sign in").click()
    assert _wait_url(pg, r"/need2login$"), pg.url
    pg.goto(base + "/protected")
    pg.wait_for_selector(f"text=This is truly private data for {user}")


def _flow_min(base: str, pg) -> None:
    user = f"twoB{int(time.time()) % 100000}"
    pg.goto(base + "/gated")
    assert _wait_url(pg, r"/login$"), pg.url
    pg.goto(base + "/register")
    pg.wait_for_selector("input#username")
    pg.fill("input#username", user)
    pg.fill("input#password", "pw-123456")
    pg.fill("input#confirm_password", "pw-123456")
    pg.get_by_role("button", name="Sign up").click()
    pg.wait_for_selector("text=Registration successful!")
    assert _wait_url(pg, r"/login$"), pg.url
    pg.fill("input#username", user)
    pg.fill("input#password", "pw-123456")
    pg.get_by_role("button", name="Sign in").click()
    assert _wait_url(pg, r"/gated$"), pg.url
    pg.wait_for_selector(f"text=min-secret for {user}")


def _run(tmp_path_factory, src: Path, name: str, flow) -> None:
    from playwright.sync_api import sync_playwright

    root = tmp_path_factory.mktemp(name) / src.name
    shutil.copytree(src, root, ignore=shutil.ignore_patterns(".web", "reflex.db", "reflex_min.db", "__pycache__", ".states", "reflex.lock"))
    os.environ["TP_EXTRA"] = "0"
    with PinnedHarness.create(root=root) as h:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM)
            pg = browser.new_page()
            errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            flow(h.frontend_url.rstrip("/"), pg)
            browser.close()
        assert not errors, errors


def test_two_apps_sharing_a_package_in_one_process(tmp_path_factory):
    """TWO_ORDER=ab (default): demo then min; ba: min then demo; aa: the demo twice (restart of the same app)."""
    order = os.environ.get("TWO_ORDER", "ab")
    apps = {"a": (SRC, "two_a", _flow_demo), "b": (MIN_SRC, "two_b", _flow_min)}
    for i, key in enumerate(order):
        src, name, flow = apps[key]
        _run(tmp_path_factory, src, f"{name}_{i}", flow)
