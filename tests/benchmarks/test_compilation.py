import pytest

from reflex.compiler.compiler import _compile_page, _compile_stateful_components


@pytest.mark.benchmark
def test_compile_page(evaluated_page):
    _compile_page(evaluated_page, None)


@pytest.mark.benchmark
def test_compile_stateful(evaluated_page):
    _compile_stateful_components([evaluated_page])


@pytest.mark.benchmark
def test_get_all_imports(evaluated_page):
    evaluated_page._get_all_imports()
