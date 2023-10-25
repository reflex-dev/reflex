"""Building the app and initializing all prerequisites."""

from __future__ import annotations

import json
import os
import subprocess
import zipfile
from pathlib import Path

from rich.progress import MofNCompleteColumn, Progress, TimeElapsedColumn

from reflex import constants
from reflex.config import get_config
from reflex.utils import console, path_ops, prerequisites, processes

def generate_requirements():
    # Run the command and get the output
    result = subprocess.run(
        "pipdeptree --warn silence | grep -E '^\w+'", 
        shell=True, capture_output=True, text=True
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
        response = console.ask(
            f"Could not find requirements.txt. Do you want to generate it?",
            choices=["y", "n"],
        )

        if response == "y":
            generate_requirements()