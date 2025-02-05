import pytest

from .fixtures import _complicated_page


@pytest.mark.benchmark
def test_component_init():
    _complicated_page()
