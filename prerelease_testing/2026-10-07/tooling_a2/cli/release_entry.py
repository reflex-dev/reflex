"""Invoke installed release commands with the fixture network boundary active."""

import os
import sys
from pathlib import Path

from guard import install

install()
import reflex_release
from reflex_release.cli import main

assert sys.prefix == os.environ["TOOLING_EXPECT_ENV"]
assert Path(reflex_release.__file__).is_relative_to(Path(sys.prefix))
raise SystemExit(main())
