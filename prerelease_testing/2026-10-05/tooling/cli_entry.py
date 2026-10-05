"""Run the installed CLI with its credential files redirected to a fixture."""

import os
import sys
from pathlib import Path

import reflex
from reflex.reflex import cli
from reflex_cli import constants

assert Path(reflex.__file__).is_relative_to(Path(sys.prefix)), reflex.__file__
constants.Hosting.HOSTING_JSON = Path(os.environ["TEST_HOSTING_CONFIG"])
constants.Hosting.HOSTING_JSON_V0 = constants.Hosting.HOSTING_JSON.with_name(
    "legacy.json"
)

cli()
