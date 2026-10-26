import { createElement, useEffect, useRef, useState } from "react";

/** Mount expensive previews when visible and the browser has idle time. */
export function DeferredDemo({ children, style, ...props }) {
  const element = useRef(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
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
      setReady(true);
    };
    const schedule = () => {
      scheduled ??= useIdleCallback
        ? window.requestIdleCallback(load, { timeout: 2000 })
        : window.setTimeout(load, 0);
    };
    if ("IntersectionObserver" in window) {
      observer = new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting)) schedule();
        else cancel();
      });
      observer.observe(element.current);
    } else {
      schedule();
    }
    return () => {
      observer?.disconnect();
      cancel();
    };
  }, []);
  return createElement(
    "div",
    {
      ...props,
      ref: element,
      style: { width: "100%", minHeight: "450px", ...style },
    },
    ready
      ? children
      : createElement(
          "p",
          {
            style: {
              minHeight: "450px",
              display: "grid",
              placeItems: "center",
              color: "var(--muted-foreground)",
              fontSize: "0.875rem",
            },
          },
          "Interactive preview loads as you scroll.",
        ),
  );
}
