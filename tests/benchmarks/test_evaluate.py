import pytest

from .fixtures import _complicated_page


@pytest.mark.benchmark
def test_evaluate_page():
    _complicated_page()
