"""Building the app and initializing all prerequisites."""

from __future__ import annotations

<<<<<<< HEAD
<<<<<<< HEAD
import os
import re
import subprocess
import sys

from reflex import constants
from reflex.utils import console


def generate_requirements():
    """Generate a requirements.txt file based on the current environment."""
    # Run the command and get the output
    result = subprocess.run(
        [sys.executable, "-m", "pipdeptree", "--warn", "silence"],
        capture_output=True,
        text=True,
    )

    # Filter the output lines using a regular expression
    lines = result.stdout.split("\n")
    filtered_lines = [line for line in lines if re.match(r"^\w+", line)]
=======
import json
=======
>>>>>>> feb38ade (Lint)
import os
import subprocess

from reflex import constants
from reflex.utils import console


def generate_requirements():
    """Generate the requirements.txt file."""
    result = subprocess.run(
<<<<<<< HEAD
        "poetry run pipdeptree --warn silence | grep -E '^\w+'", 
        shell=True, capture_output=True, text=True
=======
        "pipdeptree --warn silence | grep -E '^\\w+'",
        shell=True,
        capture_output=True,
        text=True,
>>>>>>> feb38ade (Lint)
    )

    # Filter the output lines
    lines = result.stdout.split("\n")
    filtered_lines = [line for line in lines if line and not line.startswith(" ")]
>>>>>>> 20c95286 (Test to see if autogenerating dpeenencies is viable)

    # Write the filtered lines to requirements.txt
    with open("requirements.txt", "w") as f:
        for line in filtered_lines:
            f.write(line + "\n")

<<<<<<< HEAD
<<<<<<< HEAD

def check_requirements():
    """Check if the requirements are installed."""
    if not os.path.exists(constants.RequirementsTxt.FILE):
        console.warn("It seems like there's no requirements.txt in your project.")
        response = console.ask(
            "Would you like us to auto-generate one based on your current environment?",
=======
=======

>>>>>>> feb38ade (Lint)
def check_requirements():
    """Check if the requirements are installed."""
    if not os.path.exists(constants.RequirementsTxt.FILE):
        response = console.ask(
            f"Could not find requirements.txt. Do you want to generate it?",
>>>>>>> 20c95286 (Test to see if autogenerating dpeenencies is viable)
            choices=["y", "n"],
        )

        if response == "y":
<<<<<<< HEAD
<<<<<<< HEAD
            generate_requirements()
        else:
            console.error(
                "Please create a requirements.txt file in your project's root directory and try again."
            )
            exit()
=======
            generate_requirements()
>>>>>>> 20c95286 (Test to see if autogenerating dpeenencies is viable)
=======
            generate_requirements()
>>>>>>> feb38ade (Lint)
