"""Shared footer links should skip legacy migration redirects."""

from inspect import unwrap

import pytest
from reflex_site_shared.views.footer import footer_index
from reflex_site_shared.views.marketing_footer import marketing_footer


@pytest.mark.parametrize("footer", [unwrap(footer_index), marketing_footer])
def test_footer_comparisons_use_final_destinations(footer):
    """Both shared footer variants link directly to current comparison pages."""
    rendered = str(footer())
    assert "/migration/" not in rendered
    for path in [
        "/compare/no-code/",
        "/compare/frameworks/",
        "/compare/other-ai-tools/",
    ]:
        assert path in rendered
