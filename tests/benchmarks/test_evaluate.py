import pytest

from .fixtures import _complicated_page, _simple_page


@pytest.mark.benchmark
@pytest.mark.parametrize("page", [_simple_page, _complicated_page])
def test_evaluate_page(page):
    page()
