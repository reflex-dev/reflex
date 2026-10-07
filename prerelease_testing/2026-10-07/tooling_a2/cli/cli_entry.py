"""Run the public installed CLI after redirecting credentials and network access."""

import os
import sys
from pathlib import Path

from guard import install

install()
from reflex_cli import constants

constants.Hosting.HOSTING_JSON = Path(os.environ["TEST_HOSTING_CONFIG"])
constants.Hosting.HOSTING_JSON_V0 = constants.Hosting.HOSTING_JSON.with_name(
    "legacy.json"
)
assert constants.Hosting.HOSTING_JSON.is_relative_to(
    Path(os.environ["TOOLING_FIXTURE_ROOT"])
)

import reflex
import reflex_cli
from reflex.reflex import cli

for module in (reflex, reflex_cli):
    assert Path(module.__file__).is_relative_to(Path(sys.prefix)), module.__file__
assert sys.prefix == os.environ["TOOLING_EXPECT_ENV"], sys.prefix
cli()
