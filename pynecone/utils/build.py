"""Building the app and initializing all prerequisites."""

from __future__ import annotations

import json
import os
import random
import subprocess
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Optional,
)

from pynecone import constants
from pynecone.config import get_config
from pynecone.utils import path_ops, prerequisites

if TYPE_CHECKING:
    from pynecone.app import App


def set_pynecone_project_hash():
    """Write the hash of the Pynecone project to a PCVERSION_APP_FILE."""
    with open(constants.PCVERSION_APP_FILE) as f:  # type: ignore
        pynecone_json = json.load(f)
        pynecone_json["project_hash"] = random.getrandbits(128)
    with open(constants.PCVERSION_APP_FILE, "w") as f:
        json.dump(pynecone_json, f, ensure_ascii=False)


def generate_sitemap(deploy_url: str):
    """Generate the sitemap config file.

    Args:
        deploy_url: The URL of the deployed app.
    """
    # Import here to avoid circular imports.
    from pynecone.compiler import templates

    config = json.dumps(
        {
            "siteUrl": deploy_url,
            "generateRobotsTxt": True,
        }
    )

    with open(constants.SITEMAP_CONFIG_FILE, "w") as f:
        f.write(templates.SITEMAP_CONFIG(config=config))


def export_app(
    app: App,
    backend: bool = True,
    frontend: bool = True,
    zip: bool = False,
    deploy_url: Optional[str] = None,
):
    """Zip up the app for deployment.

    Args:
        app: The app.
        backend: Whether to zip up the backend app.
        frontend: Whether to zip up the frontend app.
        zip: Whether to zip the app.
        deploy_url: The URL of the deployed app.
    """
    # Force compile the app.
    app.compile(force_compile=True)

    # Remove the static folder.
    path_ops.rm(constants.WEB_STATIC_DIR)

    # Generate the sitemap file.
    if deploy_url is not None:
        generate_sitemap(deploy_url)

    # Export the Next app.
    subprocess.run(
        [prerequisites.get_package_manager(), "run", "export"], cwd=constants.WEB_DIR
    )

    # Zip up the app.
    if zip:
        if os.name == "posix":
            posix_export(backend, frontend)
        if os.name == "nt":
            nt_export(backend, frontend)


def nt_export(backend: bool = True, frontend: bool = True):
    """Export for nt (Windows) systems.

    Args:
        backend: Whether to zip up the backend app.
        frontend: Whether to zip up the frontend app.
    """
    cmd = r""
    if frontend:
        cmd = r'''powershell -Command "Set-Location .web/_static; Compress-Archive -Path .\* -DestinationPath ..\..\frontend.zip -Force"'''
        os.system(cmd)
    if backend:
        cmd = r'''powershell -Command "Get-ChildItem -File | Where-Object { $_.Name -notin @('.web', 'assets', 'frontend.zip', 'backend.zip') } | Compress-Archive -DestinationPath backend.zip -Update"'''
        os.system(cmd)


def posix_export(backend: bool = True, frontend: bool = True):
    """Export for posix (Linux, OSX) systems.

    Args:
        backend: Whether to zip up the backend app.
        frontend: Whether to zip up the frontend app.
    """
    cmd = r""
    if frontend:
        cmd = r"cd .web/_static && zip -r ../../frontend.zip ./*"
        os.system(cmd)
    if backend:
        cmd = r"zip -r backend.zip ./* -x .web/\* ./assets\* ./frontend.zip\* ./backend.zip\*"
        os.system(cmd)


def setup_frontend(root: Path):
    """Set up the frontend.

    Args:
        root: root path of the project.
    """
    # Initialize the web directory if it doesn't exist.
    web_dir = prerequisites.create_web_directory(root)

    # Install frontend packages
    prerequisites.install_frontend_packages(web_dir)

    # copy asset files to public folder
    path_ops.mkdir(str(root / constants.WEB_ASSETS_DIR))
    path_ops.cp(
        src=str(root / constants.APP_ASSETS_DIR),
        dest=str(root / constants.WEB_ASSETS_DIR),
    )


def setup_backend():
    """Set up backend.

    Specifically ensures backend database is updated when running --no-frontend.
    """
    # Import here to avoid circular imports.
    from pynecone.model import Model

    config = get_config()
    if config.db_url is not None:
        Model.create_all()
