import { createElement, useEffect, useRef, useState } from "react";

/** Mount expensive previews once, as readers approach them. */
export function DeferredDemo({ children, style, ...props }) {
  const element = useRef(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (!("IntersectionObserver" in window)) {
      setReady(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setReady(true);
          observer.disconnect();
        }
      },
      { rootMargin: "200px" },
    );
    observer.observe(element.current);
    return () => observer.disconnect();
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
              color: "var(--secondary-11)",
              fontSize: "0.875rem",
            },
          },
          "Interactive preview loads as you scroll.",
        ),
  );
}
