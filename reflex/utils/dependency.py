"""Building the app and initializing all prerequisites."""

from __future__ import annotations

import os
import subprocess

from reflex import constants
from reflex.utils import console


def generate_requirements():
    """Generate the requirements.txt file."""
    result = subprocess.run(
        "pipdeptree --warn silence | grep -E '^\\w+'",
        shell=True,
        capture_output=True,
        text=True,
    )

    # Filter the output lines
    lines = result.stdout.split("\n")
    filtered_lines = [line for line in lines if line and not line.startswith(" ")]

    # Write the filtered lines to requirements.txt
    with open("requirements.txt", "w") as f:
        for line in filtered_lines:
            f.write(line + "\n")


def check_requirements():
    """Check if the requirements are installed."""
    if not os.path.exists(constants.RequirementsTxt.FILE):
        console.warn("It seems like there's no requirements.txt in your project.")
        response = console.ask(
            "Would you like us to auto-generate one based on your current environment?",
            choices=["y", "n"],
        )

        if response == "y":
            generate_requirements()
        else:
            console.error(
                "Please create a requirements.txt file in your project's root directory and try again."
            )
            exit()
