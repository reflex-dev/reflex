import { Component, createElement, useEffect, useRef, useState } from "react";

// Demos already shown in this session remount at once, e.g. after a tab switch.
const loadedDemos = new Set();

const placeholderStyle = {
  minHeight: "450px",
  display: "grid",
  placeItems: "center",
  color: "var(--muted-foreground)",
  fontSize: "0.875rem",
};

/** Replace a preview that throws, e.g. without WebGL, instead of the whole page. */
class PreviewErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error) {
    console.error("Docs preview failed to render:", error);
  }

  render() {
    return this.state.failed
      ? createElement(
          "p",
          { style: placeholderStyle },
          "This preview could not load in this browser.",
        )
      : this.props.children;
  }
}

/** Mount expensive previews near the viewport once the browser has idle time. */
export function DeferredDemo({ children, style, demoId, ...props }) {
  const element = useRef(null);
  const [ready, setReady] = useState(() => loadedDemos.has(demoId));
  useEffect(() => {
    if (ready) return;
    let observer;
    let scheduled = null;
    const useIdleCallback = "requestIdleCallback" in window;
    const cancel = () => {
      if (scheduled === null) return;
      if (useIdleCallback) window.cancelIdleCallback(scheduled);
      else window.clearTimeout(scheduled);
      scheduled = null;
    };
    const load = () => {
      scheduled = null;
      observer?.disconnect();
      loadedDemos.add(demoId);
      setReady(true);
    };
    const schedule = () => {
      scheduled ??= useIdleCallback
        ? window.requestIdleCallback(load, { timeout: 2000 })
        : window.setTimeout(load, 0);
    };
    if ("IntersectionObserver" in window) {
      observer = new IntersectionObserver(
        (entries) => {
          if (entries.some((entry) => entry.isIntersecting)) schedule();
          else cancel();
        },
        { rootMargin: "200px" },
      );
      observer.observe(element.current);
    } else {
      schedule();
    }
    return () => {
      observer?.disconnect();
      cancel();
    };
  }, [ready, demoId]);
  return createElement(
    "div",
    {
      ...props,
      ref: element,
      style: { width: "100%", minHeight: "450px", ...style },
    },
    ready
      ? createElement(PreviewErrorBoundary, null, children)
      : createElement(
          "p",
          { style: placeholderStyle },
          "Interactive preview loads as you scroll.",
        ),
  );
}
