import pytest

from reflex.compiler.compiler import _compile_page


@pytest.mark.benchmark
def test_compile_page(evaluated_page):
    _compile_page(evaluated_page, None)


@pytest.mark.benchmark
def test_get_all_imports(evaluated_page):
    evaluated_page._get_all_imports()
