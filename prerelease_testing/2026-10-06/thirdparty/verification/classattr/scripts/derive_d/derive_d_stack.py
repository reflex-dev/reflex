"""Claim D: print the frame chain at the rx.Model subclass deprecation, and which frames the walker treats as framework.

Usage: <venv>/bin/python derive_d_stack.py <expected-venv-name>
"""

import sys
import traceback

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
from reflex_base.utils import log  # noqa: E402

orig = log.deprecate


def spy(**kw):
    if kw.get("feature_name") == "reflex.Model":
        for fs in traceback.extract_stack()[:-1]:
            short = fs.filename.split("site-packages/")[-1]
            print(f"  framework={log._is_framework_filename(fs.filename)!s:5}  {short}:{fs.lineno} in {fs.name}")
    return orig(**kw)


log.deprecate = spy


class UserModel(rx.Model, table=True):
    x: int = 0
