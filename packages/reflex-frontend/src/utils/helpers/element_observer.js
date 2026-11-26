import { useEffect, useLayoutEffect, useRef } from "react";

/**
 * @typedef {object} ElementObserverHandlers
 * @property {(width: number, height: number) => void} [onResize] Called with
 *   the element's size when observing starts and whenever it changes.
 * @property {(x: number, y: number) => void} [onMove] Called with the
 *   element's position in the viewport when observing starts and whenever it
 *   changes after a scroll, a window resize or a resize of the element.
 * @property {(isIntersecting: boolean, ratio: number) => void} [onIntersect]
 *   Called when observing starts and whenever the fraction of the element in
 *   the viewport crosses a threshold.
 * @property {(propertyName: string) => void} [onTransitionEnd] Called when a
 *   CSS transition of the element itself ends.
 */

/**
 * @typedef {object} ElementObserverOptions
 * @property {boolean} [layout] Observe from a layout effect, so the first
 *   size and position are reported in the commit that starts observing.
 * @property {boolean} [disabled] Do not observe.
 * @property {number | number[]} [threshold] The IntersectionObserver threshold.
 * @property {string} [rootMargin] The IntersectionObserver root margin.
 */

/**
 * Report a pair of measurements now, and again whenever it changes.
 * @param {() => [number, number]} measure Measures the pair.
 * @param {(first: number, second: number) => void} report Receives the pair.
 * @param {(update: () => void) => () => void} subscribe Calls `update` when
 *   the pair may have changed; returns the unsubscribe function.
 * @returns {() => void} Stops reporting.
 */
const track = (measure, report, subscribe) => {
  let last = measure();
  report(...last);
  return subscribe(() => {
    const next = measure();
    if (next[0] !== last[0] || next[1] !== last[1]) {
      last = next;
      report(...next);
    }
  });
};

/**
 * Call `update` whenever the element's border box changes size.
 * @param {Element} element The element.
 * @param {() => void} update The callback.
 * @returns {() => void} Stops observing.
 */
const onResized = (element, update) => {
  const observer = new ResizeObserver(update);
  observer.observe(element, { box: "border-box" });
  return () => observer.disconnect();
};

/**
 * Observe the element with the given id for the handlers named in `watched`.
 * @param {string} id The element's id.
 * @param {{current: ElementObserverHandlers}} handlers The handlers, read at
 *   call time so a re-rendered handler takes effect without observing again.
 * @param {string} watched The names of the handlers to observe for, joined by commas.
 * @param {string | undefined} thresholds The IntersectionObserver threshold, as JSON.
 * @param {string | undefined} rootMargin The IntersectionObserver root margin.
 * @returns {(() => void) | undefined} Stops observing.
 */
const observe = (id, handlers, watched, thresholds, rootMargin) => {
  const element = document.getElementById(id);
  if (element === null) {
    return undefined;
  }
  const names = watched.split(",");
  /** @type {(() => void)[]} */
  const cleanups = [];

  if (names.includes("onResize")) {
    // The observer's first callback reports the size just measured, which
    // `track` drops as unchanged.
    cleanups.push(
      track(
        () => {
          const { width, height } = element.getBoundingClientRect();
          return [width, height];
        },
        (width, height) => handlers.current.onResize?.(width, height),
        (update) => onResized(element, update),
      ),
    );
  }

  if (names.includes("onMove")) {
    cleanups.push(
      track(
        () => {
          const { left, top } = element.getBoundingClientRect();
          return [left, top];
        },
        (x, y) => handlers.current.onMove?.(x, y),
        (update) => {
          // Capturing on the window catches the scrolls of every scroll
          // container, which do not bubble.
          const listener = { capture: true, passive: true };
          window.addEventListener("scroll", update, listener);
          window.addEventListener("resize", update, listener);
          const stopObserving = onResized(element, update);
          return () => {
            window.removeEventListener("scroll", update, listener);
            window.removeEventListener("resize", update, listener);
            stopObserving();
          };
        },
      ),
    );
  }

  if (names.includes("onIntersect")) {
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[entries.length - 1];
        handlers.current.onIntersect?.(
          entry.isIntersecting,
          entry.intersectionRatio,
        );
      },
      {
        threshold:
          thresholds === undefined ? undefined : JSON.parse(thresholds),
        rootMargin,
      },
    );
    observer.observe(element);
    cleanups.push(() => observer.disconnect());
  }

  if (names.includes("onTransitionEnd")) {
    /** @param {TransitionEvent} event */
    const ended = (event) => {
      if (event.target === element) {
        handlers.current.onTransitionEnd?.(event.propertyName);
      }
    };
    element.addEventListener("transitionend", ended);
    cleanups.push(() => element.removeEventListener("transitionend", ended));
  }

  return () => {
    for (const cleanup of cleanups) {
      cleanup();
    }
  };
};

/**
 * Report the size, position and visibility of the element with the given id,
 * and the ends of its CSS transitions.
 *
 * Observing restarts when the id, an option or the set of handlers changes,
 * not when a handler is re-rendered.
 * @param {string} id The element's id.
 * @param {ElementObserverHandlers} handlers The handlers to report to.
 * @param {ElementObserverOptions} options The options.
 */
export default function useElementObserver(id, handlers, options) {
  const handlersRef = useRef(handlers);
  // Declared before the effects that observe, so they read these handlers.
  useLayoutEffect(() => {
    handlersRef.current = handlers;
  });
  const { layout = false, disabled = false, threshold, rootMargin } = options;
  // Strings, so a new object or array with the same content observes nothing anew.
  const watched = Object.keys(handlers)
    .filter((name) => handlers[name])
    .join(",");
  const thresholds = JSON.stringify(threshold);
  // Both effects always run, so `layout` may change without breaking the
  // order of hooks; only the one it selects observes.
  useLayoutEffect(
    () =>
      layout && !disabled
        ? observe(id, handlersRef, watched, thresholds, rootMargin)
        : undefined,
    [id, layout, disabled, watched, thresholds, rootMargin],
  );
  useEffect(
    () =>
      !layout && !disabled
        ? observe(id, handlersRef, watched, thresholds, rootMargin)
        : undefined,
    [id, layout, disabled, watched, thresholds, rootMargin],
  );
}
