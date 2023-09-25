import pytest

try:
    import numpy as np
except ImportError:
    pytest.skip("numpy is not installed", allow_module_level=True)

try:
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
except ImportError:
    pytest.skip("matplotlib is not installed", allow_module_level=True)

from reflex.utils.serializers import serialize


@pytest.fixture
def matplotlib_fig() -> Figure:
    """Get a matplotlib figure.

    Returns:
        A random matplotlib figure.
    """
    # Generate random data.
    np.random.seed(19680801)
    fig, ax = plt.subplots()
    for color in ["tab:blue", "tab:orange", "tab:green"]:
        n = 10
        x, y = np.random.rand(2, n)
        scale = 200.0 * np.random.rand(n)
        ax.scatter(x, y, c=color, s=scale, label=color, alpha=0.3, edgecolors="none")
    ax.legend()
    ax.grid(True)

    # Create a fig.
    return fig


def test_serialize_matplotlib(matplotlib_fig: Figure):
    """Test that serializing a matplotlib figure works.

    Args:
        matplotlib_fig: The figure to serialize.
    """
    value = serialize(matplotlib_fig)
    assert isinstance(value, str)
