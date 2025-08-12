"""A component that automatically scrolls to the bottom when new content is added."""

from __future__ import annotations

import dataclasses

from reflex.components.el.elements.typography import Div
from reflex.constants.compiler import MemoizationDisposition, MemoizationMode
from reflex.utils.imports import ImportDict
from reflex.vars.base import Var, get_unique_variable_name


class AutoScroll(Div):
    """A div that automatically scrolls to the bottom when new content is added."""

    _memoization_mode = MemoizationMode(
        disposition=MemoizationDisposition.ALWAYS, recursive=False
    )

    @classmethod
    def create(cls, *children, **props):
        """Create an AutoScroll component.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            An AutoScroll component.
        """
        props.setdefault("overflow", "auto")
        props.setdefault("id", get_unique_variable_name())
        component = super().create(*children, **props)
        if "key" in props:
            component._memoization_mode = dataclasses.replace(
                component._memoization_mode, recursive=True
            )
        return component

    def add_imports(self) -> ImportDict | list[ImportDict]:
        """Add imports required for the component.

        Returns:
            The imports required for the component.
        """
        return {"react": ["useEffect", "useRef"]}

    def add_hooks(self) -> list[str | Var]:
        """Add hooks required for the component.

        Returns:
            The hooks required for the component.
        """
        ref_name = self.get_ref()
        unique_id = ref_name
        return [
            f"const wasNearBottom_{unique_id} = useRef(false);",
            f"const hadScrollbar_{unique_id} = useRef(false);",
            f"""
const checkIfNearBottom_{unique_id} = () => {{
    if (!{ref_name}.current) return;

    const container = {ref_name}.current;
    const nearBottomThreshold = 50; // pixels from bottom to trigger auto-scroll

    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;

    wasNearBottom_{unique_id}.current = distanceFromBottom <= nearBottomThreshold;

    // Track if container had a scrollbar
    hadScrollbar_{unique_id}.current = container.scrollHeight > container.clientHeight;
}};
""",
            f"""
const scrollToBottomIfNeeded_{unique_id} = () => {{
    if (!{ref_name}.current) return;

    const container = {ref_name}.current;
    const hasScrollbarNow = container.scrollHeight > container.clientHeight;

    // Scroll if:
    // 1. User was near bottom, OR
    // 2. Container didn't have scrollbar before but does now
    if (wasNearBottom_{unique_id}.current || (!hadScrollbar_{unique_id}.current && hasScrollbarNow)) {{
      container.scrollTop = container.scrollHeight;
    }}

    // Update scrollbar state for next check
    hadScrollbar_{unique_id}.current = hasScrollbarNow;
}};
""",
            f"""
useEffect(() => {{
    const container = {ref_name}.current;
    if (!container) return;

    scrollToBottomIfNeeded_{unique_id}();

    // Create ResizeObserver to detect height changes
    const resizeObserver = new ResizeObserver(() => {{
        scrollToBottomIfNeeded_{unique_id}();
    }});

    // Track scroll position before height changes
    container.addEventListener('scroll', checkIfNearBottom_{unique_id});

    // Initial check
    checkIfNearBottom_{unique_id}();

    // Observe container for size changes
    resizeObserver.observe(container);

    return () => {{
        container.removeEventListener('scroll', checkIfNearBottom_{unique_id});
        resizeObserver.disconnect();
    }};
}});
""",
        ]


auto_scroll = AutoScroll.create
