import importlib
import sys

from pytest_codspeed import BenchmarkFixture


def _wipe_reflex_modules():
    # Drop every reflex workspace module (and rich, which must stay lazy) so
    # each round measures a cold `import reflex`.
    for name in list(sys.modules):
        top = name.partition(".")[0]
        if top.startswith("reflex") or top == "rich":
            del sys.modules[name]


def test_import_reflex(benchmark: BenchmarkFixture):
    saved = sys.modules.copy()
    try:

        def cold_import():
            _wipe_reflex_modules()
            importlib.import_module("reflex")

        benchmark(cold_import)
    finally:
        sys.modules.clear()
        sys.modules.update(saved)
