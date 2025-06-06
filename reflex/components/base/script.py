"""Wrapper for the script element. Uses the Helmet component to manage the head."""

from __future__ import annotations

from reflex.components import el as elements
from reflex.components.core.helmet import helmet
from reflex.utils import console


class Script(elements.Script):
    """Wrapper for the script element."""

    @classmethod
    def create(
        cls,
        *children,
        **props,
    ):
        """Display the script element.

        Args:
            *children: The children of the element.
            **props: The properties of the element.

        Returns:
            The script element.

        Raises:
            ValueError: If neither children nor src is specified.
        """
        async_ = props.pop("async_", None)
        char_set = props.pop("char_set", None)
        cross_origin = props.pop("cross_origin", None)
        defer = props.pop("defer", None)
        integrity = props.pop("integrity", None)
        referrer_policy = props.pop("referrer_policy", None)
        src = props.pop("src", None)
        type = props.pop("type", None)
        key = props.pop("key", None)
        id = props.pop("id", None)
        class_name = props.pop("class_name", None)
        autofocus = props.pop("autofocus", None)
        custom_attrs = props.pop("custom_attrs", None)
        on_mount = props.pop("on_mount", None)
        on_unmount = props.pop("on_unmount", None)

        if props:
            console.warn(
                f"rx.script does not support the following properties: {list(props.keys())}"
            )

        if not children and not src:
            msg = "You must specify either children or src for the script element."
            raise ValueError(msg)

        return helmet(
            elements.Script.create(
                *children,
                async_=async_,
                char_set=char_set,
                cross_origin=cross_origin,
                defer=defer,
                integrity=integrity,
                referrer_policy=referrer_policy,
                src=src,
                type=type,
                key=key,
                id=id,
                class_name=class_name,
                autofocus=autofocus,
                custom_attrs=custom_attrs,
                on_mount=on_mount,
                on_unmount=on_unmount,
            )
        )


script = Script.create
