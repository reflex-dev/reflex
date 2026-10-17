from reflex_components_core.core.banner import (
    ConnectionBanner,
    ConnectionModal,
    ConnectionPulser,
    WebsocketTargetURL,
    connection_error,
    has_connection_errors,
    has_fatal_connection_error,
    has_too_many_connection_errors,
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


def test_connection_error_vars_avoid_unpolyfilled_runtime_apis():
    """The generated JS must not depend on `Array.prototype.at` (ES2022).

    It is a runtime method, so the bundler's build target does not downlevel
    it and older browsers throw while rendering the connection UI.
    """
    for var in (
        connection_error,
        has_connection_errors,
        has_fatal_connection_error,
        has_too_many_connection_errors,
    ):
        assert ".at(" not in str(var)


def test_has_fatal_connection_error_is_length_guarded():
    assert str(has_fatal_connection_error) == (
        "((connectErrors.length > 0)"
        " && connectErrors[connectErrors.length - 1].fatal === true)"
    )


def test_has_too_many_connection_errors_composes_the_fatal_check():
    assert str(has_too_many_connection_errors) == (
        "(connectErrors.length >= 2 || ((connectErrors.length > 0)"
        " && connectErrors[connectErrors.length - 1].fatal === true))"
    )
