"""Independent verifier repro for the registration_context behavior-break claim.

Run with each venv's python FROM A NEUTRAL CWD (NOT /home/user/reflex — the
checkout's reflex/ package shadows site-packages via sys.path[0] and corrupts
the result):

    REFLEX_TELEMETRY_ENABLED=false <venv>/bin/python verify_repro.py

Expected:
  0.9.8   -> double-App OK, DECORATED_PAGES is a defaultdict
  0.9.9a1 -> double-App raises ReflexRuntimeError (fork() guidance),
             DECORATED_PAGES import raises the confusing
             "cannot import name ... from 'PageNamespace' (unknown location)"
"""

import importlib.metadata

print("reflex version:", importlib.metadata.version("reflex"))

import reflex as rx

print("reflex from:", rx.__file__)

try:
    a = rx.App()
    b = rx.App()
    print("double-App: OK (two distinct instances: %s)" % (a is not b))
except Exception as e:
    print(f"double-App: {type(e).__name__}: {e}")

try:
    from reflex.page import DECORATED_PAGES

    print("DECORATED_PAGES:", type(DECORATED_PAGES).__name__)
except Exception as e:
    print(f"DECORATED_PAGES: {type(e).__name__}: {e}")
