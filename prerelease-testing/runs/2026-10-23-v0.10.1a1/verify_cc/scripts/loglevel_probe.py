"""Reproduce, without a build, the log-level state `reflex deploy` is in after the export step.

Mirrors the real call chain:
  reflex group callback -> log.enable_managed_logging()
  deploy --loglevel X   -> reflex_cli.utils.console.set_log_level(X)   (eager click callback)
  hosting_cli.deploy()  -> console.set_log_level(prep.loglevel == get_config().loglevel)
  export_for_deploy()   -> export(loglevel=get_config().loglevel.subprocess_level()) -> console.set_log_level(...)
then logs one record per level through a reflex_cli logger, exactly like the hosting CLI does.

Usage: EXPECT_VENV=cloud_cli-new python -I loglevel_probe.py [<--loglevel value>|-]
Run with cwd = a directory holding the app's rxconfig.py.
"""

from __future__ import annotations

import logging
import os
import sys

import reflex
import reflex_cli

expect = os.environ["EXPECT_VENV"]
assert f"/envs/{expect}/" in reflex_cli.__file__, reflex_cli.__file__
assert f"/envs/{expect}/" in reflex.__file__, reflex.__file__

from reflex_base.config import get_config  # noqa: E402
from reflex_base.utils import console, log  # noqa: E402
from reflex_cli.utils import console as cli_console  # noqa: E402

flag = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "-" else None
print(f"[probe] argv loglevel={flag!r} env REFLEX_LOGLEVEL(before)={os.environ.get('REFLEX_LOGLEVEL')!r}")
print(f"[probe] initial log.get_log_level()={log.get_log_level()!r}")

log.enable_managed_logging()  # the `reflex` group callback
cli_console.set_log_level(flag)  # the deploy command's eager --loglevel callback
print(f"[probe] after --loglevel callback: log level={log.get_log_level()!r} env REFLEX_LOGLEVEL={os.environ.get('REFLEX_LOGLEVEL')!r}")

config = get_config()
print(f"[probe] get_config().loglevel={config.loglevel!r} .subprocess_level()={config.loglevel.subprocess_level()!r}")

cli_console.set_log_level(config.loglevel)  # hosting_cli.deploy(loglevel=prep.loglevel)
print(f"[probe] after deploy() set_log_level(prep.loglevel): log level={log.get_log_level()!r}")

console.set_log_level(config.loglevel.subprocess_level())  # reflex.utils.export.export()
print(f"[probe] after export(): log level={log.get_log_level()!r}  <- level every later hosting-CLI record is filtered at")

logger = logging.getLogger("reflex_cli.probe")
logger.debug("DEBUG record after export")
logger.info("INFO record after export (e.g. 'App is being scaled; waiting 15 seconds...')")
logger.log(log.SUCCESS, "SUCCESS record after export (e.g. 'deployment completed successfully')")
logger.warning("WARNING record after export")
logger.error("ERROR record after export")
