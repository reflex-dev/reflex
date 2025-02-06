import pytest


@pytest.mark.benchmark
def test_evaluate_page(unevaluated_page):
    unevaluated_page()
