"""A component that automatically scrolls to the bottom when new content is added."""

from __future__ import annotations

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
        return super().create(*children, **props)

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
        return [
            "const wasNearBottom = useRef(false);",
            "const hadScrollbar = useRef(false);",
            f"""
const checkIfNearBottom = () => {{
    if (!{ref_name}.current) return;

    const container = {ref_name}.current;
    const nearBottomThreshold = 50; // pixels from bottom to trigger auto-scroll

    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;

    wasNearBottom.current = distanceFromBottom <= nearBottomThreshold;

    // Track if container had a scrollbar
    hadScrollbar.current = container.scrollHeight > container.clientHeight;
}};
""",
            f"""
const scrollToBottomIfNeeded = () => {{
    if (!{ref_name}.current) return;

    const container = {ref_name}.current;
    const hasScrollbarNow = container.scrollHeight > container.clientHeight;

    // Scroll if:
    // 1. User was near bottom, OR
    // 2. Container didn't have scrollbar before but does now
    if (wasNearBottom.current || (!hadScrollbar.current && hasScrollbarNow)) {{
      container.scrollTop = container.scrollHeight;
    }}

    // Update scrollbar state for next check
    hadScrollbar.current = hasScrollbarNow;
}};
""",
            f"""
useEffect(() => {{
    const container = {ref_name}.current;
    if (!container) return;

    scrollToBottomIfNeeded();

    // Create ResizeObserver to detect height changes
    const resizeObserver = new ResizeObserver(() => {{
        scrollToBottomIfNeeded();
    }});

    // Track scroll position before height changes
    container.addEventListener('scroll', checkIfNearBottom);

    // Initial check
    checkIfNearBottom();

    // Observe container for size changes
    resizeObserver.observe(container);

    return () => {{
        container.removeEventListener('scroll', checkIfNearBottom);
        resizeObserver.disconnect();
    }};
}});
""",
        ]


auto_scroll = AutoScroll.create
