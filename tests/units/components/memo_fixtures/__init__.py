"""Real importable modules for cross-module ``@rx.memo`` collision tests.

Each submodule defines memos with names that intentionally clash across modules
so tests can exercise the full define -> register -> compile -> validate_imports
pipeline with genuine distinct ``fn.__module__`` values (not monkeypatched).
"""
