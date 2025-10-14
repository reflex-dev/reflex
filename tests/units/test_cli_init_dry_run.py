"""Tests for the Reflex CLI `init --dry-run` command."""

import os
from click.testing import CliRunner
from reflex.reflex import cli

def test_init_dry_run(tmp_path):
    """Ensure that --dry-run prints steps and does not create files."""
    runner = CliRunner()
    test_app_name = "test_dry_app"

    # Run the command with --dry-run
    result = runner.invoke(cli, ["init", "--name", test_app_name, "--dry-run"])

    # ✅ 1. Command should succeed
    assert result.exit_code == 0, f"Command failed: {result.output}"

    # ✅ 2. Output should contain dry-run lines
    assert "[DRY-RUN]" in result.output
    assert "Would initialize app" in result.output
    assert "No files were created" in result.output

    # ✅ 3. The directory shouldn't actually exist
    app_dir = tmp_path / test_app_name
    assert not app_dir.exists(), "Dry-run should not create any folders"
