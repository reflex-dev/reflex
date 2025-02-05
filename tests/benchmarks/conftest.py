import warnings

from .fixtures import complicated_page

warnings.filterwarnings(
    "ignore", message="fields may not start with an underscore", category=RuntimeWarning
)

__all__ = ["complicated_page"]
