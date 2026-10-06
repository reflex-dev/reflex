"""AppHarness integration test for the PUBLISHED reflex-local-auth (upstream repo has no tests/).

Runs the upstream local_auth_demo app (copied to a fresh dir) via reflex.testing.AppHarness, with the
backend/frontend ports pinned into the cluster's reserved range, and drives it with Playwright.

Run (from this directory, never from a checkout):
  TP_VENV=thirdparty-alpha TP_FP=3104 TP_BP=8104 $SB/envs/thirdparty-alpha/bin/python -m pytest -x -s test_local_auth_harness.py
"""

from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

import pytest

import reflex
import reflex.utils.processes
from reflex.testing import AppHarness

VENV = os.environ["TP_VENV"]
assert f"/scratchpad/envs/{VENV}/" in reflex.__file__, reflex.__file__
FP = int(os.environ["TP_FP"])
BP = int(os.environ["TP_BP"])
_HERE = Path(__file__).resolve().parent.parent
# scratch layout keeps app sources in src/, the committed artifact copy in apps/
SRC = next(p for p in (_HERE / "src" / "local_auth_demo", _HERE / "apps" / "local_auth_demo") if p.is_dir())
CHROMIUM = "/opt/pw-browsers/chromium"


class PinnedHarness(AppHarness):
    """AppHarness that binds inside the cluster's reserved ports instead of random ones."""

    def _start_backend(self, port: int = 0):
        return super()._start_backend(port=BP)

    def _start_frontend(self):
        orig = reflex.utils.processes.new_process

        def pinned(args, **kwargs):
            env = kwargs.get("env")
            if env is not None and env.get("PORT") == "0":
                env["PORT"] = str(FP)
            return orig(args, **kwargs)

        reflex.utils.processes.new_process = pinned
        try:
            super()._start_frontend()
        finally:
            reflex.utils.processes.new_process = orig


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    root = tmp_path_factory.mktemp(f"harness_{VENV}") / "local_auth_demo"
    shutil.copytree(SRC, root, ignore=shutil.ignore_patterns(".web", "reflex.db", "__pycache__", ".states", "reflex.lock"))
    os.environ["TP_EXTRA"] = "0"  # only the upstream demo pages
    with PinnedHarness.create(root=root) as h:
        yield h


@pytest.fixture(scope="module")
def page(harness):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        pg = browser.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
        pg.errors = errors  # type: ignore[attr-defined]
        yield pg
        browser.close()


def _wait_url(pg, pattern, timeout=20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if re.search(pattern, pg.url):
            return True
        pg.wait_for_timeout(200)
    return False


def test_ports_pinned(harness):
    assert harness.frontend_url is not None
    assert f":{FP}" in harness.frontend_url, harness.frontend_url
    assert harness.backend is not None and harness.backend.config.port == BP


def test_register_login_logout(harness, page):
    base = harness.frontend_url.rstrip("/")
    user = f"harness{int(time.time()) % 100000}"
    pw = "pw-123456"
    page.goto(base + "/need2login")
    assert _wait_url(page, r"/login$"), page.url
    page.get_by_role("link", name="Register").click()
    assert _wait_url(page, r"/register$"), page.url
    page.fill("input#username", user)
    page.fill("input#password", pw)
    page.fill("input#confirm_password", pw)
    page.get_by_role("button", name="Sign up").click()
    page.wait_for_selector("text=Registration successful!")
    assert _wait_url(page, r"/login$"), page.url
    page.fill("input#username", user)
    page.fill("input#password", pw)
    page.get_by_role("button", name="Sign in").click()
    # redirect_to was set by the need2login visit
    assert _wait_url(page, r"/need2login$"), page.url
    page.wait_for_selector("text=Accessing this page will redirect")
    page.goto(base + "/protected")
    page.wait_for_selector(f"text=This is truly private data for {user}")

    # Reload keeps the session (auth_token lives in localStorage).
    page.reload()
    page.wait_for_selector(f"text=This is truly private data for {user}")
    page.goto(base + "/user-info")
    page.wait_for_selector(f"text=Username: {user}")

    page.goto(base + "/need2login")
    page.wait_for_selector("text=Accessing this page will redirect")
    page.get_by_role("link", name="Logout").first.click()
    page.wait_for_timeout(3000)
    print(f"URL_AFTER_LOGOUT={page.url}", flush=True)
    # The Logout link has href="/" while the protected page's require_login
    # wrapper redirects to /login once is_authenticated flips; either is a logout.
    assert re.search(r"/(login)?$", page.url), page.url
    page.goto(base + "/protected")
    assert _wait_url(page, r"/login$"), page.url
    assert not [e for e in page.errors if "favicon" not in e], page.errors
