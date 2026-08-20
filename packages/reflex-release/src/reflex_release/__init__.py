"""Changelog-driven release automation for Python packages and monorepos.

The ``CHANGELOG.md`` files are the source of truth for publishing: a package is
published exactly when the newest version heading in its changelog has no
corresponding git tag. Tags are created only *after* a successful upload, so a
failed build or publish is retried by pushing a fix on top of the changelog
bump — no tag or release ever needs to be deleted.

The public entry point is the ``reflex-release`` command line interface; see
:mod:`reflex_release.cli` and the package README for the workflows it drives.
"""

from .config import Config, LockstepGroup, load_config

__all__ = ["Config", "LockstepGroup", "load_config"]
