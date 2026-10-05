"""CLI entry point for pyi_generator regression tests.

Usage:
    uv run python packages/reflex-base/tests/reflex_base_tests/utils/pyi_generator/test_regression.py --update
    uv run python packages/reflex-base/tests/reflex_base_tests/utils/pyi_generator/test_regression.py --check
"""

from reflex_base_tests.utils.pyi_generator.test_regression import main

main()
