import pytest
from reflex_components_radix.themes.components.radio_cards import radio_cards


@pytest.mark.parametrize(
    "component",
    [
        lambda: radio_cards.root(radio_cards.item("One", value="one"), as_child=True),
        lambda: radio_cards.item("One", value="one", as_child=True),
    ],
    ids=["root", "item"],
)
def test_radio_cards_does_not_forward_as_child(component):
    """Radix Themes omits asChild from RadioCards, so it is never rendered as a prop.

    Args:
        component: Builds the radio cards component under test.
    """
    assert not any(
        prop.startswith("asChild:") for prop in component().render()["props"]
    )
