"""Rendering smoke tests across the simpler UI components."""

import pytest

import reflex as rx


def test_badge_variants() -> None:
    """Badges render their variant classes and slot."""
    rendered = str(rx.ui.badge("New", variant="secondary"))

    assert "bg-secondary" in rendered
    assert '"data-slot":"badge"' in rendered
    assert rendered.startswith('jsx("span"')


def test_card_parts() -> None:
    """Card parts render as divs with their slots and classes."""
    rendered = str(
        rx.ui.card(
            rx.ui.card.header(
                rx.ui.card.title("Title"),
                rx.ui.card.description("Desc"),
            ),
            rx.ui.card.content("Body"),
            rx.ui.card.footer("Footer"),
        )
    )

    for slot in (
        "card",
        "card-header",
        "card-title",
        "card-description",
        "card-content",
        "card-footer",
    ):
        assert f'"data-slot":"{slot}"' in rendered
    assert "bg-card" in rendered


def test_alert_destructive_variant() -> None:
    """Alerts render role=alert and variant classes."""
    rendered = str(
        rx.ui.alert(
            rx.ui.alert.title("Oh no"),
            rx.ui.alert.description("Something happened"),
            variant="destructive",
        )
    )

    assert 'role:"alert"' in rendered
    assert "text-destructive" in rendered
    assert '"data-slot":"alert-title"' in rendered


def test_input_renders_native_input() -> None:
    """The input styles the native input element."""
    rendered = str(rx.ui.input(placeholder="Email", type="email"))

    assert rendered.startswith('jsx("input"')
    assert 'placeholder:"Email"' in rendered
    assert "border-input" in rendered


def test_textarea_renders_native_textarea() -> None:
    """The textarea styles the native textarea element."""
    rendered = str(rx.ui.textarea(placeholder="Bio"))

    assert rendered.startswith('jsx("textarea"')
    assert "min-h-16" in rendered


def test_label_renders_native_label() -> None:
    """The label styles the native label element."""
    rendered = str(rx.ui.label("Name", html_for="name"))

    assert rendered.startswith('jsx("label"')
    assert 'htmlFor:"name"' in rendered


def test_checkbox_is_native_input() -> None:
    """The checkbox is a native checkbox input with the check glyph classes."""
    rendered = str(rx.ui.checkbox(default_checked=True))

    assert rendered.startswith('jsx("input"')
    assert 'type:"checkbox"' in rendered
    assert "appearance-none" in rendered
    assert "clip-path" in rendered


def test_switch_is_native_checkbox_with_switch_role() -> None:
    """The switch is a checkbox input with role=switch and thumb classes."""
    rendered = str(rx.ui.switch())

    assert 'type:"checkbox"' in rendered
    assert 'role:"switch"' in rendered
    assert "rounded-full" in rendered


def test_separator_orientations() -> None:
    """Separators render orientation-specific classes."""
    horizontal = str(rx.ui.separator())
    vertical = str(rx.ui.separator(orientation="vertical"))

    assert "h-px w-full" in horizontal
    assert "w-px self-stretch" in vertical
    with pytest.raises(ValueError, match="Invalid orientation"):
        rx.ui.separator(orientation="diagonal")  # pyright: ignore[reportArgumentType]


def test_skeleton_and_spinner() -> None:
    """Skeleton and spinner carry their signature classes."""
    assert "animate-pulse" in str(rx.ui.skeleton(class_name="h-4 w-32"))
    spinner = str(rx.ui.spinner())
    assert "animate-spin" in spinner
    assert 'role:"status"' in spinner


def test_progress_renders_indicator_with_translation() -> None:
    """Progress renders an aria progressbar with a translated indicator."""
    rendered = str(rx.ui.progress(value=25))

    assert 'role:"progressbar"' in rendered
    assert '"aria-valuenow":25' in rendered
    assert "translateX" in rendered
    assert '"data-slot":"progress-indicator"' in rendered


def test_avatar_static_source_shows_image() -> None:
    """A static src renders the image element."""
    rendered = str(rx.ui.avatar(src="/me.png", alt="Me", fallback="ME"))

    assert 'src:"/me.png"' in rendered
    assert "avatar-image" in rendered


def test_avatar_without_source_shows_fallback() -> None:
    """Without a src the fallback initials render."""
    rendered = str(rx.ui.avatar(fallback="ME"))

    assert "avatar-fallback" in rendered
    assert '"ME"' in rendered


def test_avatar_var_source_conditions_on_src() -> None:
    """A Var src renders a cond between image and fallback."""
    from reflex_base.vars.base import Var

    rendered = str(rx.ui.avatar(src=Var("state.src").to(str), fallback="ME"))

    assert "avatar-image" in rendered
    assert "avatar-fallback" in rendered


def test_select_wraps_native_select_with_items() -> None:
    """The select renders options, a placeholder, and the indicator icon."""
    rendered = str(
        rx.ui.select(items=["a", "b"], placeholder="Pick one", class_name="w-64")
    )

    assert 'jsx("select"' in rendered
    assert rendered.count('jsx("option"') == 3
    assert 'value:""' in rendered
    assert "appearance-none" in rendered
    assert 'jsx("svg"' in rendered
    assert '"w-64"' in rendered


def test_select_var_items_uses_foreach() -> None:
    """Var items render through a map over the values."""
    from reflex_base.vars.base import Var

    rendered = str(rx.ui.select(items=Var("state.opts").to(list[str])))

    assert "Array.prototype.map.call(state.opts" in rendered
    assert 'jsx("option"' in rendered


def test_radio_group_generates_labeled_items() -> None:
    """radio_group items render labeled native radios sharing a name."""
    rendered = str(rx.ui.radio_group(items=["x", "y"], default_value="x"))

    assert rendered.count('type:"radio"') == 2
    assert rendered.count('jsx("label"') == 2
    assert 'role:"radiogroup"' in rendered


def test_radio_group_controlled_checks_matching_item() -> None:
    """A controlled radio group checks the item matching the value."""
    from reflex_base.vars.base import Var

    rendered = str(rx.ui.radio_group(items=["x", "y"], value=Var("state.v").to(str)))

    assert "checked:" in rendered
