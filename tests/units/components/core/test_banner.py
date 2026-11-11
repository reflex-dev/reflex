from reflex_components_core.core.banner import (
    ConnectionBanner,
    ConnectionModal,
    ConnectionPulser,
    ConnectionToaster,
    WebsocketTargetURL,
)
from reflex_components_radix.themes.typography.text import Text


def test_websocket_target_url():
    url = WebsocketTargetURL.create()
    var_data = url._get_all_var_data()
    assert var_data is not None
    assert sorted(key for key, _ in var_data.imports) == sorted((
        "$/utils/state",
        "$/env.json",
    ))


def test_connection_banner():
    banner = ConnectionBanner.create()
    imports = banner._get_all_imports(collapse=True)
    assert sorted(imports) == sorted((
        "react",
        "$/utils/context",
        "$/utils/state",
        "$/env.json",
    ))

    msg = "Connection error"
    custom_banner = ConnectionBanner.create(Text.create(msg))
    assert msg in str(custom_banner.render())


def test_connection_modal():
    modal = ConnectionModal.create()
    imports = modal._get_all_imports(collapse=True)
    assert sorted(imports) == sorted((
        "react",
        "$/utils/context",
        "$/utils/state",
        "$/env.json",
    ))

    msg = "Connection error"
    custom_modal = ConnectionModal.create(Text.create(msg))
    assert msg in str(custom_modal.render())


def test_connection_pulser():
    pulser = ConnectionPulser.create()
    _custom_code = pulser._get_all_custom_code()
    _imports = pulser._get_all_imports(collapse=True)


def test_connection_toaster_shows_hydration_errors_at_once():
    hooks = "\n".join(map(str, ConnectionToaster.create()._get_all_hooks()))
    hydration_check = hooks.index("error.code === 'hydration_payload_too_large'")

    # Checked before the two-error threshold, with an id no connection toast
    # dismisses, and kept open until the user closes it.
    assert hydration_check < hooks.index("(connectErrors.length >= 2)")
    assert 'id: "hydration-payload-error"' in hooks
    assert "duration: Infinity" in hooks
