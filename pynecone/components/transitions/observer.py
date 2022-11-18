"""Container to observer element."""

from pynecone.components.component import Component


class Observer(Component):
    """A component that wraps a react-visibility-sensor component."""

    library = "react-visibility-sensor"


class VisibilitySensor(Observer):
    """Display a square box."""

    tag = "VisibilitySensor"
