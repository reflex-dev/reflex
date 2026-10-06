"""Run the installed public CLI with only fixture configuration redirected."""

import sys
from pathlib import Path

from fixture_setup import configure_fixture

import reflex
from reflex.reflex import cli

assert Path(reflex.__file__).is_relative_to(Path(sys.prefix)), reflex.__file__
configure_fixture()

if __name__ == "__main__":
    cli()
