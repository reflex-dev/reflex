"""Drive the hosting CLI's deploy() with a canned export, against the fake control plane.

This is the exact function `reflex deploy` calls (reflex_cli.v2.deploy -> reflex_cli.v2.cli.deploy);
only the export step (compile + vite build, minutes per run) is replaced by copying archives that a
real `reflex deploy` produced earlier, so the control-plane retry logic can be exercised many times.

Usage: EXPECT_VENV=cloud_cli-new python -I deploy_driver.py <archive_dir> '<json kwargs for deploy()>'
Run from the app directory (deploy() reads rxconfig.py for the badge setting).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import reflex
import reflex_cli

expect = os.environ["EXPECT_VENV"]
assert f"/envs/{expect}/" in reflex_cli.__file__, reflex_cli.__file__
assert f"/envs/{expect}/" in reflex.__file__, reflex.__file__

import click  # noqa: E402
from reflex_base.utils import log as _rxlog  # noqa: E402
from reflex_cli.v2 import cli as hosting_cli  # noqa: E402

# The `reflex` entrypoint turns on managed logging (console handler on the "reflex" logger); without it the
# INFO/SUCCESS progress lines the deploy prints are dropped.
_rxlog.enable_managed_logging()

archives = Path(sys.argv[1])
kwargs = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}


def export_fn(zip_dest_dir, api_url, deploy_url, frontend, backend, upload_db, zipping):
    """Stand in for reflex.hosting.export_for_deploy: copy the captured archives."""
    print(
        f"[fake export] frontend={frontend} backend={backend} api_url={api_url} deploy_url={deploy_url}",
        file=sys.stderr,
    )
    for name, wanted in (("backend.zip", backend), ("frontend.zip", frontend)):
        if wanted:
            shutil.copy(archives / name, Path(zip_dest_dir) / name)


try:
    hosting_cli.deploy(export_fn=export_fn, **{"interactive": False, **kwargs})
except click.exceptions.Exit as ex:
    sys.exit(ex.exit_code)
except SystemExit:
    raise
except BaseException as ex:  # noqa: BLE001
    print(f"[driver] uncaught {type(ex).__name__}: {ex}", file=sys.stderr)
    sys.exit(70)
