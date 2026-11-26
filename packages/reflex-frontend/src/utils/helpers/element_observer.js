import { useEffect, useLayoutEffect, useRef } from "react";

/**
 * @typedef {object} ElementObserverHandlers
 * @property {(width: number, height: number) => void} [onResize] Called with
 *   the element's size when observing starts and whenever its border box
 *   changes size; a change of its transform alone does not call it.
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
 * @typedef {object} Tracker
 * @property {Element} element The element measured.
 * @property {() => boolean} measure Measures the pair; true if it changed.
 * @property {() => void} report Reports the pair `measure` found changed.
 */

/**
 * Report a pair of measurements now, and again whenever `refresh` finds it changed.
 * @param {Element} element The element measured.
 * @param {() => [number, number]} measure Measures the pair.
 * @param {(first: number, second: number) => void} report Receives the pair.
 * @returns {Tracker} The tracker to refresh.
 */
const track = (element, measure, report) => {
  let last = measure();
  let next = last;
  report(...last);
  return {
    element,
    measure: () => {
      next = measure();
      return next[0] !== last[0] || next[1] !== last[1];
    },
    report: () => {
      last = next;
      report(...next);
    },
  };
};

/**
 * Measure all trackers before reporting any, so a report that writes to the
 * DOM cannot force a layout for the next measurement, and the reports land in
 * one task, which React renders once.
 * @param {Iterable<Tracker>} trackers The trackers to refresh.
 */
const refresh = (trackers) => {
  const changed = [];
  for (const tracker of trackers) {
    if (tracker.measure()) {
      changed.push(tracker);
    }
  }
  for (const tracker of changed) {
    tracker.report();
  }
};

// One ResizeObserver for every observed element, while any is observed: many
// observers cost more to run, and each calls back in its own task.
/** @type {Map<Element, Set<Tracker>>} */
const resizeTrackers = new Map();
/** @type {ResizeObserver | null} */
let resizeObserver = null;

/** @param {ResizeObserverEntry[]} entries The elements that resized. */
const onResized = (entries) => {
  /** @type {Set<Tracker>} */
  const due = new Set();
  for (const { target } of entries) {
    for (const tracker of resizeTrackers.get(target) ?? []) {
      due.add(tracker);
    }
  }
  refresh(due);
};

/**
 * Refresh `tracker` whenever its element's border box changes size.
 * @param {Tracker} tracker The tracker.
 * @returns {() => void} Stops refreshing it.
 */
const refreshOnResize = (tracker) => {
  const { element } = tracker;
  let trackers = resizeTrackers.get(element);
  if (trackers === undefined) {
    trackers = new Set();
    resizeTrackers.set(element, trackers);
    resizeObserver ??= new ResizeObserver(onResized);
    resizeObserver.observe(element, { box: "border-box" });
  }
  trackers.add(tracker);
  return () => {
    trackers.delete(tracker);
    if (trackers.size > 0) {
      return;
    }
    resizeTrackers.delete(element);
    resizeObserver?.unobserve(element);
    if (resizeTrackers.size === 0) {
      resizeObserver?.disconnect();
      resizeObserver = null;
    }
  };
};

// One scroll and one resize listener on the window for every tracked position.
/** @type {Set<Tracker>} */
const scrollTrackers = new Set();

/** @param {Event} event A scroll of the page or of any scroll container. */
const onScroll = (event) => {
  const scrolled = event.target;
  if (!(scrolled instanceof Element)) {
    refresh(scrollTrackers);
    return;
  }
  // A scroll container's scroll moves only what is inside it.
  const due = [];
  for (const tracker of scrollTrackers) {
    if (scrolled.contains(tracker.element)) {
      due.push(tracker);
    }
  }
  refresh(due);
};

const onWindowResize = () => refresh(scrollTrackers);

// Capturing on the window catches the scrolls of every scroll container, which
// do not bubble.
const LISTENER = { capture: true, passive: true };

/**
 * Refresh `tracker` after the page or a scroll container around its element
 * scrolled, or the window resized.
 * @param {Tracker} tracker The tracker.
 * @returns {() => void} Stops refreshing it.
 */
const refreshOnScroll = (tracker) => {
  if (scrollTrackers.size === 0) {
    window.addEventListener("scroll", onScroll, LISTENER);
    window.addEventListener("resize", onWindowResize, LISTENER);
  }
  scrollTrackers.add(tracker);
  return () => {
    scrollTrackers.delete(tracker);
    if (scrollTrackers.size === 0) {
      window.removeEventListener("scroll", onScroll, LISTENER);
      window.removeEventListener("resize", onWindowResize, LISTENER);
    }
  };
};

/** @typedef {(entry: IntersectionObserverEntry) => void} IntersectionCallback */

/**
 * @typedef {object} IntersectionTarget
 * @property {Set<IntersectionCallback>} callbacks The element's callbacks.
 * @property {IntersectionObserverEntry} [entry] The element's latest entry.
 */

/**
 * @typedef {object} SharedIntersectionObserver
 * @property {IntersectionObserver} observer The observer.
 * @property {Map<Element, IntersectionTarget>} targets The elements it observes.
 */

// One IntersectionObserver for every element observed with the same options.
/** @type {Map<string, SharedIntersectionObserver>} */
const intersectionObservers = new Map();

/**
 * Create the IntersectionObserver shared by the elements observed with the
 * given options.
 * @param {string | undefined} thresholds The threshold, as JSON.
 * @param {string | undefined} rootMargin The root margin.
 * @returns {SharedIntersectionObserver} The observer and its targets.
 */
const shareIntersectionObserver = (thresholds, rootMargin) => {
  /** @type {SharedIntersectionObserver["targets"]} */
  const targets = new Map();
  const observer = new IntersectionObserver(
    (entries) => {
      // An element that changed more than once since the last callback has
      // several entries, the latest last.
      /** @type {Map<IntersectionTarget, IntersectionObserverEntry>} */
      const latest = new Map();
      for (const entry of entries) {
        const target = targets.get(entry.target);
        if (target !== undefined) {
          target.entry = entry;
          latest.set(target, entry);
        }
      }
      for (const [{ callbacks }, entry] of latest) {
        for (const callback of callbacks) {
          callback(entry);
        }
      }
    },
    {
      threshold: thresholds === undefined ? undefined : JSON.parse(thresholds),
      rootMargin,
    },
  );
  return { observer, targets };
};

/**
 * Call `callback` with the element's intersection entry when observing starts
 * and whenever the fraction in view crosses a threshold.
 * @param {Element} element The element.
 * @param {IntersectionCallback} callback The callback.
 * @param {string | undefined} thresholds The threshold, as JSON.
 * @param {string | undefined} rootMargin The root margin.
 * @returns {() => void} Stops calling `callback`.
 */
const onIntersection = (element, callback, thresholds, rootMargin) => {
  const key = JSON.stringify([thresholds, rootMargin]);
  let shared = intersectionObservers.get(key);
  if (shared === undefined) {
    shared = shareIntersectionObserver(thresholds, rootMargin);
    intersectionObservers.set(key, shared);
  }
  const { observer, targets } = shared;
  let target = targets.get(element);
  if (target === undefined) {
    target = { callbacks: new Set() };
    targets.set(element, target);
    observer.observe(element);
  } else if (target.entry !== undefined) {
    // The observer reports an element once when observing starts, so a later
    // callback starts from the element's latest entry.
    callback(target.entry);
  }
  const { callbacks } = target;
  callbacks.add(callback);
  return () => {
    callbacks.delete(callback);
    if (callbacks.size > 0) {
      return;
    }
    targets.delete(element);
    observer.unobserve(element);
    if (targets.size === 0) {
      observer.disconnect();
      intersectionObservers.delete(key);
    }
  };
};

/** @type {Set<() => void>} */
const pageChangeListeners = new Set();
/** @type {MutationObserver | undefined} */
let pageObserver;

/**
 * Call `listener` after elements were added to or removed from the page, or an
 * element's id changed. One MutationObserver serves all listeners.
 * @param {() => void} listener The callback.
 * @returns {() => void} Stops calling it.
 */
const onPageChange = (listener) => {
  pageChangeListeners.add(listener);
  if (pageObserver === undefined) {
    pageObserver = new MutationObserver(() => {
      for (const callback of pageChangeListeners) {
        callback();
      }
    });
    pageObserver.observe(document, {
      childList: true,
      subtree: true,
      attributeFilter: ["id"],
    });
  }
  return () => {
    pageChangeListeners.delete(listener);
    if (pageChangeListeners.size === 0) {
      pageObserver?.disconnect();
      pageObserver = undefined;
    }
  };
};

/**
 * Observe whichever element has the given id: from when one is on the page,
 * moving to another element that takes the id over.
 * @param {string} id The element's id.
 * @param {(element: Element) => () => void} start Observes an
 *   element; returns the function that stops it.
 * @returns {() => void} Stops observing.
 */
const follow = (id, start) => {
  let element = document.getElementById(id);
  let stop = element === null ? undefined : start(element);
  const stopFollowing = onPageChange(() => {
    const next = document.getElementById(id);
    if (next !== element) {
      stop?.();
      element = next;
      stop = element === null ? undefined : start(element);
    }
  });
  return () => {
    stopFollowing();
    stop?.();
  };
};

/**
 * Observe the element for the handlers named in `watched`.
 * @param {Element} element The element.
 * @param {{current: ElementObserverHandlers}} handlers The handlers, read at
 *   call time so a re-rendered handler takes effect without observing again.
 * @param {string} watched The names of the handlers to observe for, joined by commas.
 * @param {string | undefined} thresholds The IntersectionObserver threshold, as JSON.
 * @param {string | undefined} rootMargin The IntersectionObserver root margin.
 * @returns {() => void} Stops observing.
 */
const observeElement = (element, handlers, watched, thresholds, rootMargin) => {
  const names = watched.split(",");
  /** @type {(() => void)[]} */
  const cleanups = [];

  if (names.includes("onResize")) {
    // The observer's first callback reports the size just measured, which
    // `refresh` drops as unchanged.
    const size = track(
      element,
      () => {
        const { width, height } = element.getBoundingClientRect();
        return [width, height];
      },
      (width, height) => handlers.current.onResize?.(width, height),
    );
    cleanups.push(refreshOnResize(size));
  }

  if (names.includes("onMove")) {
    const position = track(
      element,
      () => {
        const { left, top } = element.getBoundingClientRect();
        return [left, top];
      },
      (x, y) => handlers.current.onMove?.(x, y),
    );
    cleanups.push(refreshOnScroll(position), refreshOnResize(position));
  }

  if (names.includes("onIntersect")) {
    cleanups.push(
      onIntersection(
        element,
        ({ isIntersecting, intersectionRatio }) =>
          handlers.current.onIntersect?.(isIntersecting, intersectionRatio),
        thresholds,
        rootMargin,
      ),
    );
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
 * Observe whichever element has the given id for the handlers named in `watched`.
 * @param {string} id The element's id.
 * @param {{current: ElementObserverHandlers}} handlers The handlers.
 * @param {string} watched The names of the handlers to observe for, joined by commas.
 * @param {string | undefined} thresholds The IntersectionObserver threshold, as JSON.
 * @param {string | undefined} rootMargin The IntersectionObserver root margin.
 * @returns {() => void} Stops observing.
 */
const observe = (id, handlers, watched, thresholds, rootMargin) =>
  follow(id, (element) =>
    observeElement(element, handlers, watched, thresholds, rootMargin),
  );

/**
 * Report the size, position and visibility of the element with the given id,
 * and the ends of its CSS transitions.
 *
 * Observing starts once an element with the id is on the page and moves to
 * another element that takes the id over. It restarts when the id, an option
 * or the set of handlers changes, not when a handler is re-rendered.
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
