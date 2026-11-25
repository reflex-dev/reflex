from reflex_components_core.core.window_events import WindowEventListener

import reflex as rx


def test_window_event_listener_registers_the_handler_again_when_it_changes():
    """A handler is memoized on the state it reads, so registering only the first one keeps its values."""
    flag = rx.client_state(False, name="flag")
    listener = WindowEventListener.create(
        on_key_down=lambda key, meta: rx.call_function(flag.set(True))
    )
    handler = str(listener.event_triggers["on_key_down"])

    assert [str(hook) for hook in listener.add_hooks()] == [
        f"""
useEffect(() => {{
    if (typeof window === 'undefined') return;
    const fn = {handler};
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
}}, [{handler}]);
"""
    ]
