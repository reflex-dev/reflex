"""Tests for Dialog component parent-child validation."""

import pytest

from reflex.components.radix.primitives.dialog import (
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogOverlay,
    DialogPortal,
    DialogRoot,
    DialogTitle,
    DialogTrigger,
)
from reflex.components.radix.themes.components.dialog import (
    DialogClose as ThemeDialogClose,
)
from reflex.components.radix.themes.components.dialog import (
    DialogContent as ThemeDialogContent,
)
from reflex.components.radix.themes.components.dialog import (
    DialogDescription as ThemeDialogDescription,
)
from reflex.components.radix.themes.components.dialog import (
    DialogRoot as ThemeDialogRoot,
)
from reflex.components.radix.themes.components.dialog import (
    DialogTitle as ThemeDialogTitle,
)
from reflex.components.radix.themes.components.dialog import (
    DialogTrigger as ThemeDialogTrigger,
)
from reflex.components.radix.themes.layout.box import Box


class TestDialogPrimitivesValidation:
    """Test validation of Dialog primitives components."""

    def test_dialog_trigger_requires_dialog_root(self):
        """DialogTrigger must be used within DialogRoot."""
        with pytest.raises(ValueError) as err:
            Box.create(DialogTrigger.create())
        assert "DialogTrigger" in str(err.value)
        assert "DialogRoot" in str(err.value)

    def test_dialog_trigger_valid_with_dialog_root(self):
        """DialogTrigger is valid within DialogRoot."""
        DialogRoot.create(DialogTrigger.create())

    def test_dialog_portal_requires_dialog_root(self):
        """DialogPortal must be used within DialogRoot."""
        with pytest.raises(ValueError) as err:
            Box.create(DialogPortal.create())
        assert "DialogPortal" in str(err.value)
        assert "DialogRoot" in str(err.value)

    def test_dialog_overlay_requires_dialog_root_or_portal(self):
        """DialogOverlay must be used within DialogRoot or DialogPortal."""
        with pytest.raises(ValueError) as err:
            Box.create(DialogOverlay.create())
        assert "DialogOverlay" in str(err.value)

    def test_dialog_content_requires_dialog_root_or_portal(self):
        """DialogContent must be used within DialogRoot or DialogPortal."""
        with pytest.raises(ValueError) as err:
            Box.create(DialogContent.create())
        assert "DialogContent" in str(err.value)

    def test_dialog_title_requires_valid_parent(self):
        """DialogTitle must be used within DialogRoot, DialogPortal, or DialogContent."""
        with pytest.raises(ValueError) as err:
            Box.create(DialogTitle.create())
        assert "DialogTitle" in str(err.value)

    def test_dialog_description_requires_valid_parent(self):
        """DialogDescription must be used within DialogRoot, DialogPortal, or DialogContent."""
        with pytest.raises(ValueError) as err:
            Box.create(DialogDescription.create())
        assert "DialogDescription" in str(err.value)

    def test_dialog_close_requires_valid_parent(self):
        """DialogClose must be used within DialogRoot, DialogPortal, or DialogContent."""
        with pytest.raises(ValueError) as err:
            Box.create(DialogClose.create())
        assert "DialogClose" in str(err.value)


class TestDialogThemesValidation:
    """Test validation of Dialog themes components."""

    def test_theme_dialog_trigger_requires_dialog_root(self):
        """Theme DialogTrigger must be used within DialogRoot."""
        with pytest.raises(ValueError) as err:
            Box.create(ThemeDialogTrigger.create())
        assert "DialogTrigger" in str(err.value)
        assert "DialogRoot" in str(err.value)

    def test_theme_dialog_trigger_valid_with_dialog_root(self):
        """Theme DialogTrigger is valid within DialogRoot."""
        ThemeDialogRoot.create(ThemeDialogTrigger.create())

    def test_theme_dialog_content_requires_dialog_root(self):
        """Theme DialogContent must be used within DialogRoot."""
        with pytest.raises(ValueError) as err:
            Box.create(ThemeDialogContent.create())
        assert "DialogContent" in str(err.value)
        assert "DialogRoot" in str(err.value)

    def test_theme_dialog_title_requires_valid_parent(self):
        """Theme DialogTitle must be used within DialogRoot or DialogContent."""
        with pytest.raises(ValueError) as err:
            Box.create(ThemeDialogTitle.create())
        assert "DialogTitle" in str(err.value)

    def test_theme_dialog_description_requires_valid_parent(self):
        """Theme DialogDescription must be used within DialogRoot or DialogContent."""
        with pytest.raises(ValueError) as err:
            Box.create(ThemeDialogDescription.create())
        assert "DialogDescription" in str(err.value)

    def test_theme_dialog_close_requires_valid_parent(self):
        """Theme DialogClose must be used within DialogRoot or DialogContent."""
        with pytest.raises(ValueError) as err:
            Box.create(ThemeDialogClose.create())
        assert "DialogClose" in str(err.value)

    def test_valid_theme_dialog_structure(self):
        """Test a valid theme dialog structure."""
        ThemeDialogRoot.create(
            ThemeDialogTrigger.create("Open"),
            ThemeDialogContent.create(
                ThemeDialogTitle.create("Dialog Title"),
                ThemeDialogDescription.create("Dialog description"),
                ThemeDialogClose.create("Close"),
            ),
        )
