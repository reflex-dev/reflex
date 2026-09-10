import { useEffect, useRef, useState, createElement } from "react";

/** Render readable code during SSR and highlight only near the viewport. */
export function Code({
  code,
  theme,
  themes,
  language,
  transformers,
  decorations,
  ...divProps
}) {
  const container = useRef(null);
  const [highlighted, setHighlighted] = useState(null);

  useEffect(() => {
    let active = true;
    let observer;
    let idle;
    const highlight = () => {
      const run = async () => {
        try {
          const { codeToHtml } = await import("shiki");
          const html = await codeToHtml(code, {
            lang: language,
            ...(themes ? { themes } : { theme }),
            transformers,
            decorations,
          });
          if (active) setHighlighted({ code, html });
        } catch (error) {
          // Unsupported grammars or a failed download must leave code readable.
          console.warn("Unable to highlight code block", error);
        }
      };
      if ("requestIdleCallback" in window) {
        idle = window.requestIdleCallback(run, { timeout: 1000 });
      } else {
        idle = window.setTimeout(run, 0);
      }
    };
    if ("IntersectionObserver" in window) {
      observer = new IntersectionObserver(
        (entries) => {
          if (entries.some((entry) => entry.isIntersecting)) {
            observer.disconnect();
            highlight();
          }
        },
        { rootMargin: "200px" },
      );
      observer.observe(container.current);
    } else {
      highlight();
    }
    return () => {
      active = false;
      observer?.disconnect();
      if ("cancelIdleCallback" in window) window.cancelIdleCallback(idle);
      else window.clearTimeout(idle);
    };
  }, [code, language, theme, themes, transformers, decorations]);

  if (highlighted?.code === code) {
    return createElement("div", {
      ...divProps,
      ref: container,
      dangerouslySetInnerHTML: { __html: highlighted.html },
    });
  }
  return createElement(
    "div",
    { ...divProps, ref: container },
    createElement(
      "pre",
      { className: "shiki", tabIndex: 0 },
      createElement(
        "code",
        null,
        ...code
          .split("\n")
          .flatMap((line, index) => [
            index > 0 ? "\n" : null,
            createElement("span", { className: "line", key: index }, line),
          ]),
      ),
    ),
  );
}
