import pytest

from reflex.compiler.compiler import _compile_page


@pytest.mark.benchmark
def test_compile_page(complicated_page):
    _compile_page(complicated_page, None)


@pytest.mark.benchmark
def test_get_all_imports(complicated_page):
    complicated_page._get_all_imports()
