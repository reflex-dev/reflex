from reflex.components.core.responsive import (
    desktop_only,
    mobile_and_tablet,
    mobile_only,
    tablet_and_desktop,
    tablet_only,
)
from reflex.components.radix.themes.layout.box import Box


def test_mobile_only():
    """Test the mobile_only responsive component."""
    component = mobile_only("Content")
    assert isinstance(component, Box)


def test_tablet_only():
    """Test the tablet_only responsive component."""
    component = tablet_only("Content")
    assert isinstance(component, Box)


def test_desktop_only():
    """Test the desktop_only responsive component."""
    component = desktop_only("Content")
    assert isinstance(component, Box)


def test_tablet_and_desktop():
    """Test the tablet_and_desktop responsive component."""
    component = tablet_and_desktop("Content")
    assert isinstance(component, Box)


def test_mobile_and_tablet():
    """Test the mobile_and_tablet responsive component."""
    component = mobile_and_tablet("Content")
    assert isinstance(component, Box)
