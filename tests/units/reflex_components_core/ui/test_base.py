import pytest
from reflex_base.vars.base import Var
from reflex_components_core.ui.components.skeleton import SKELETON_CLASS_NAME, Skeleton


def test_default_class_name_stays_a_literal() -> None:
    """Without a user class name, the default is a plain scannable string."""
    skeleton = Skeleton.create()

    assert skeleton.class_name == SKELETON_CLASS_NAME
    assert f'className:"{SKELETON_CLASS_NAME}"' in str(skeleton)


def test_user_class_name_merges_client_side() -> None:
    """User classes are merged with twMerge so they win conflicts."""
    skeleton = Skeleton.create(class_name="rounded-full")

    rendered = str(skeleton)
    assert "twMerge" in rendered
    assert f'"{SKELETON_CLASS_NAME}"' in rendered
    assert '"rounded-full"' in rendered


def test_var_class_name_merges_client_side() -> None:
    """Var class names also merge through twMerge."""
    rendered = str(Skeleton.create(class_name=Var("state.cls").to(str)))

    assert "twMerge" in rendered
    assert "state.cls" in rendered


def test_unstyled_drops_default_classes() -> None:
    """unstyled=True keeps only the user-provided class name."""
    skeleton = Skeleton.create(class_name="custom", unstyled=True)

    assert skeleton.class_name == "custom"
    assert SKELETON_CLASS_NAME not in str(skeleton)


def test_unstyled_must_be_static() -> None:
    """A Var unstyled prop raises early with a clear message."""
    with pytest.raises(TypeError, match="unstyled"):
        Skeleton.create(unstyled=Var("state.unstyled").to(bool))


def test_data_slot_attribute_is_set() -> None:
    """Components identify themselves with a data-slot attribute."""
    assert '"data-slot":"skeleton"' in str(Skeleton.create())


def test_data_slot_can_be_overridden() -> None:
    """A user-provided data-slot wins over the component default."""
    assert '"data-slot":"custom"' in str(Skeleton.create(data_slot="custom"))
