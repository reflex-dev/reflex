A component that only sets a client state var, such as `on_click=cs.set(1)`, no longer subscribes to its value, so it does not re-render when the var changes.
