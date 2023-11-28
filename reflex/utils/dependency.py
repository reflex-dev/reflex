"""Building the app and initializing all prerequisites."""
from __future__ import annotations

import re
from pathlib import Path

from reflex import constants
from reflex.utils import console


def initialize_requirements_txt():
    """Initialize the requirements.txt file.
    If absent, generate one for the user.
    If the requirements.txt does not have reflex as dependency,
    generate a requirement pinning current version and append to
    the requirements.txt file.
    """
    fp = Path(constants.RequirementsTxt.FILE)
    fp.touch(exist_ok=True)

    try:
        with open(fp, "r") as f:
            for req in f.readlines():
                # Check if we have a package name that is reflex
                if re.match(r"^reflex[^a-zA-Z0-9]", req):
                    console.debug(f"{fp} already has reflex as dependency.")
                    return
        with open(fp, "a") as f:
            f.write(
                f"\n{constants.RequirementsTxt.DEFAULTS_STUB}{constants.Reflex.VERSION}\n"
            )
    except Exception:
        console.info(f"Unable to check {fp} for reflex dependency.")
