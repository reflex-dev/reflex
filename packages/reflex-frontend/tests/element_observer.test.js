/**
 * Unit tests for `utils/helpers/element_observer.js`: when the hook reports,
 * what it reports again and when it observes anew. jsdom has no layout, no
 * observers and no frames, so the element's rect, the observers and the
 * animation frames are stand-ins the tests drive by hand.
 */
import { act, createElement, Fragment, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import useElementObserver from "$/utils/helpers/element_observer";

// React 19 wants this set when driving roots manually.
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

/** Observers created since the test started, newest last. */
let resizeObservers;
let intersectionObservers;

class FakeResizeObserver {
  constructor(callback) {
    this.callback = callback;
    this.observed = [];
    this.disconnected = false;
    resizeObservers.push(this);
  }
  observe(element, options) {
    this.observed.push([element, options]);
  }
  unobserve(element) {
    this.observed = this.observed.filter(([observed]) => observed !== element);
  }
  disconnect() {
    this.observed = [];
    this.disconnected = true;
  }
  /** Call back for the given elements, by default every observed one. */
  resize(elements = this.observed.map(([element]) => element)) {
    this.callback(elements.map((target) => ({ target })));
  }
}

class FakeIntersectionObserver {
  constructor(callback, options) {
    this.callback = callback;
    this.options = options;
    this.thresholds = [options.threshold ?? 0].flat().sort((x, y) => x - y);
    this.observed = [];
    this.disconnected = false;
    intersectionObservers.push(this);
  }
  observe(element) {
    this.observed.push(element);
  }
  unobserve(element) {
    this.observed = this.observed.filter((observed) => observed !== element);
  }
  disconnect() {
    this.observed = [];
    this.disconnected = true;
  }
}

/** Animation frame callbacks waiting for the next frame. */
let frames;

/** Run the callbacks waiting for the next frame. */
const nextFrame = () => {
  const due = [...frames.values()];
  frames.clear();
  act(() => {
    for (const callback of due) {
      callback(0);
    }
  });
};

/** The roots still mounted, unmounted after each test so none follows its id on. */
let roots;

beforeEach(() => {
  resizeObservers = [];
  intersectionObservers = [];
  frames = new Map();
  roots = new Set();
  let handle = 0;
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
  vi.stubGlobal("IntersectionObserver", FakeIntersectionObserver);
  vi.stubGlobal("requestAnimationFrame", (callback) => {
    handle += 1;
    frames.set(handle, callback);
    return handle;
  });
  vi.stubGlobal("cancelAnimationFrame", (id) => frames.delete(id));
});

afterEach(() => {
  for (const root of roots) {
    act(() => root.unmount());
  }
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.body.replaceChildren();
});

/** The rect the stand-in layout gives an observed element. */
let rect;
/** The rects of the elements laid out apart from it, by id. */
let rects = {};

/** Move or resize an observed element in the stand-in layout. */
const layOut = (changes, id) => {
  if (id === undefined) {
    rect = { ...rect, ...changes };
  } else {
    rects[id] = { ...rects[id], ...changes };
  }
};

/** Lay the element out in the stand-in layout, logging its measurements to `log`. */
const measured = (element, log) => {
  element.getBoundingClientRect = () => {
    log?.push(`measure ${element.id}`);
    return rectOf(rects[element.id] ?? rect);
  };
};

/** Put an element with the id on the page, outside of React. */
const place = (id) => {
  const element = document.createElement("div");
  element.id = id;
  measured(element);
  return document.body.appendChild(element);
};

/** Let the page's MutationObservers see the changes made so far. */
const pageChanged = () => Promise.resolve();

const rectOf = ({ x, y, width, height }) => ({
  x,
  y,
  width,
  height,
  top: y,
  right: x + width,
  bottom: y + height,
  left: x,
});

/** Render `element` in a fresh root, unmounted after the test. */
const renderRoot = (element) => {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  roots.add(root);
  const render = (next) => act(() => root.render(next));
  render(element);
  return {
    render,
    unmount: () => {
      roots.delete(root);
      act(() => root.unmount());
    },
  };
};

/**
 * Render a component observing `#box`, which it renders itself, in a fresh root.
 * @returns {{log: string[], render: (props: object) => void, box: () => HTMLElement, unmount: () => void}}
 */
const mount = (props) => {
  rect = { x: 0, y: 10, width: 100, height: 50 };
  rects = {};
  const log = [];
  const Observed = ({ handlers, options, id = "box" }) => {
    useEffect(() => {
      log.push("effect");
    });
    useElementObserver(id, handlers, options);
    return createElement("div", {
      id: "box",
      ref: (element) => {
        if (element) {
          measured(element);
        }
      },
    });
  };
  const { render, unmount } = renderRoot(createElement(Observed, props(log)));
  return {
    log,
    render: (next) => render(createElement(Observed, next(log))),
    box: () => document.getElementById("box"),
    unmount,
  };
};

/**
 * Render elements `#a` and `#b`, each observed with the handlers and options
 * `observe` gives for its id.
 * @returns {{log: string[], unmount: () => void}}
 */
const mountTwo = (observe) => {
  rects = {
    a: { x: 0, y: 10, width: 100, height: 50 },
    b: { x: 0, y: 70, width: 100, height: 50 },
  };
  const log = [];
  const Observed = ({ id }) => {
    const [handlers, options] = observe(id, log);
    useElementObserver(id, handlers, options);
    return createElement("div", {
      id,
      ref: (element) => {
        if (element) {
          measured(element, log);
        }
      },
    });
  };
  const { unmount } = renderRoot(
    createElement(
      Fragment,
      null,
      createElement(Observed, { id: "a" }),
      createElement(Observed, { id: "b" }),
    ),
  );
  return { log, unmount };
};

/** Count the scroll listeners added to the window from now on. */
const countScrollListeners = () => {
  const added = vi.spyOn(window, "addEventListener");
  return () => added.mock.calls.filter(([type]) => type === "scroll").length;
};

describe("timing", () => {
  test("a layout observer reports in the commit's layout phase, before its effects", () => {
    const { log } = mount((log) => ({
      handlers: { onResize: () => log.push("resize") },
      options: { layout: true },
    }));
    expect(log).toEqual(["resize", "effect"]);
  });

  test("an observer without layout reports among the commit's effects", () => {
    const { log } = mount((log) => ({
      handlers: { onResize: () => log.push("resize") },
      options: {},
    }));
    expect(log).toEqual(["effect", "resize"]);
  });

  test("a resize is reported in the next frame, outside the observer's callback", () => {
    const widths = [];
    mount(() => ({
      handlers: { onResize: (width) => widths.push(width) },
      options: {},
    }));
    layOut({ width: 120 });
    resizeObservers[0].callback([{ target: document.getElementById("box") }]);
    expect(widths).toEqual([100]);

    nextFrame();
    expect(widths).toEqual([100, 120]);
  });
});

describe("on_resize", () => {
  test("reports the size when observing starts, then only its changes", () => {
    const sizes = [];
    mount(() => ({
      handlers: { onResize: (...size) => sizes.push(size) },
      options: {},
    }));
    const [observer] = resizeObservers;
    expect(observer.observed).toEqual([
      [document.getElementById("box"), { box: "border-box" }],
    ]);
    expect(sizes).toEqual([[100, 50]]);

    // The observer's first callback, and a move, keep the size.
    observer.resize();
    nextFrame();
    layOut({ y: 30 });
    observer.resize();
    nextFrame();
    expect(sizes).toEqual([[100, 50]]);

    layOut({ height: 80 });
    observer.resize();
    nextFrame();
    expect(sizes).toEqual([
      [100, 50],
      [100, 80],
    ]);
  });
});

describe("on_move", () => {
  test("reports the position after scrolls, window resizes and its own resizes", () => {
    const positions = [];
    mount(() => ({
      handlers: { onMove: (...position) => positions.push(position) },
      options: {},
    }));
    expect(positions).toEqual([[0, 10]]);

    layOut({ y: -20 });
    window.dispatchEvent(new Event("scroll"));
    // A scroll that moves nothing, such as one of an unrelated container.
    window.dispatchEvent(new Event("scroll"));
    layOut({ y: -40 });
    document.body.dispatchEvent(new Event("scroll"));
    layOut({ y: 5 });
    window.dispatchEvent(new Event("resize"));
    // A resize that keeps the position, then one that moves it, as centering does.
    layOut({ height: 70 });
    resizeObservers[0].resize();
    nextFrame();
    layOut({ x: 8, width: 84 });
    resizeObservers[0].resize();
    nextFrame();
    expect(positions).toEqual([
      [0, 10],
      [0, -20],
      [0, -40],
      [0, 5],
      [8, 5],
    ]);
  });

  test("a scroll container's scroll measures only the elements inside it", () => {
    const { box } = mount(() => ({
      handlers: { onMove: () => {} },
      options: {},
    }));
    const log = [];
    measured(box(), log);
    const elsewhere = document.body.appendChild(document.createElement("div"));
    elsewhere.dispatchEvent(new Event("scroll"));
    expect(log).toEqual([]);

    document.body.dispatchEvent(new Event("scroll"));
    expect(log).toEqual(["measure box"]);
  });

  test("stops listening when unmounted", () => {
    const tops = [];
    const { unmount } = mount(() => ({
      handlers: { onMove: (_x, y) => tops.push(y) },
      options: {},
    }));
    const removed = vi.spyOn(window, "removeEventListener");
    layOut({ height: 70 });
    resizeObservers[0].resize();
    unmount();
    layOut({ y: -20 });
    window.dispatchEvent(new Event("scroll"));
    expect(frames.size).toBe(0);
    expect(tops).toEqual([10]);
    expect(resizeObservers[0].disconnected).toBe(true);
    expect(removed.mock.calls.map(([type]) => type)).toEqual([
      "scroll",
      "resize",
    ]);
  });
});

describe("on_intersect", () => {
  test("reports the latest entry with the threshold and root margin given", () => {
    const reports = [];
    mount(() => ({
      handlers: { onIntersect: (...args) => reports.push(args) },
      options: { threshold: [0, 1], rootMargin: "-10px" },
    }));
    const [observer] = intersectionObservers;
    const box = document.getElementById("box");
    expect(observer.observed).toEqual([box]);
    expect(observer.options).toEqual({
      threshold: [0, 1],
      rootMargin: "-10px",
    });

    observer.callback([
      { target: box, isIntersecting: false, intersectionRatio: 0 },
      { target: box, isIntersecting: true, intersectionRatio: 0.5 },
    ]);
    expect(reports).toEqual([[true, 0.5]]);
  });
});

describe("on_transition_end", () => {
  test("reports transitions of the element itself, not of its descendants", () => {
    const names = [];
    const { box } = mount(() => ({
      handlers: { onTransitionEnd: (name) => names.push(name) },
      options: {},
    }));
    const child = box().appendChild(document.createElement("span"));
    const ended = (name) => {
      const event = new Event("transitionend", { bubbles: true });
      Object.defineProperty(event, "propertyName", { value: name });
      return event;
    };
    child.dispatchEvent(ended("opacity"));
    box().dispatchEvent(ended("height"));
    expect(names).toEqual(["height"]);
  });
});

describe("sharing", () => {
  test("elements share one ResizeObserver, one scroll listener and an IntersectionObserver per options", () => {
    const scrollListeners = countScrollListeners();
    mountTwo((id) => [
      { onResize: () => {}, onMove: () => {}, onIntersect: () => {} },
      { rootMargin: id === "a" ? "-10px" : "-20px" },
    ]);
    const [a, b] = ["a", "b"].map((id) => document.getElementById(id));

    expect(resizeObservers).toHaveLength(1);
    // Resize and move of one element share its observation.
    expect(resizeObservers[0].observed.map(([element]) => element)).toEqual([
      a,
      b,
    ]);
    expect(scrollListeners()).toBe(1);
    expect(intersectionObservers.map(({ observed }) => observed)).toEqual([
      [a],
      [b],
    ]);
  });

  test("elements observed with the same options share an IntersectionObserver", () => {
    const reports = [];
    mountTwo((id) => [
      { onIntersect: (visible) => reports.push([id, visible]) },
      { threshold: 0.5 },
    ]);
    const [a, b] = ["a", "b"].map((id) => document.getElementById(id));
    expect(intersectionObservers).toHaveLength(1);

    intersectionObservers[0].callback([
      { target: b, isIntersecting: true, intersectionRatio: 0.6 },
      { target: a, isIntersecting: false, intersectionRatio: 0 },
    ]);
    expect(reports).toEqual([
      ["b", true],
      ["a", false],
    ]);
  });

  test("a scroll measures every position before reporting any", () => {
    const { log } = mountTwo((id, log) => [
      { onMove: () => log.push(`report ${id}`) },
      {},
    ]);
    log.length = 0;
    layOut({ y: 0 }, "a");
    layOut({ y: 60 }, "b");
    window.dispatchEvent(new Event("scroll"));
    expect(log).toEqual(["measure a", "measure b", "report a", "report b"]);
  });

  test("the shared observers are released with their last element", () => {
    const scrollListeners = countScrollListeners();
    const { unmount } = mountTwo(() => [
      { onResize: () => {}, onMove: () => {}, onIntersect: () => {} },
      {},
    ]);
    unmount();
    expect(resizeObservers[0].disconnected).toBe(true);
    expect(intersectionObservers[0].disconnected).toBe(true);

    mountTwo(() => [{ onResize: () => {}, onMove: () => {} }, {}]);
    expect(resizeObservers).toHaveLength(2);
    expect(scrollListeners()).toBe(2);
  });
});

describe("observing anew", () => {
  test("a re-rendered handler is called without observing again", () => {
    const calls = [];
    const { render } = mount(() => ({
      handlers: { onResize: () => calls.push("first") },
      options: {},
    }));
    render(() => ({
      handlers: { onResize: () => calls.push("second") },
      options: {},
    }));
    layOut({ width: 120 });
    resizeObservers[0].resize();
    nextFrame();

    expect(resizeObservers).toHaveLength(1);
    expect(calls).toEqual(["first", "second"]);
  });

  test("disabled stops observing, and enabling observes with a first report", () => {
    const widths = [];
    const handlers = { onResize: (width) => widths.push(width) };
    const { render } = mount(() => ({ handlers, options: {} }));
    render(() => ({ handlers, options: { disabled: true } }));
    expect(resizeObservers[0].disconnected).toBe(true);

    layOut({ width: 120 });
    render(() => ({ handlers, options: {} }));
    expect(resizeObservers).toHaveLength(2);
    expect(widths).toEqual([100, 120]);
  });

  test("a second observer of an element gets a fresh first intersection entry", () => {
    const reports = [];
    mountTwo((id) => [
      { onIntersect: (...args) => reports.push([id, ...args]) },
      {},
    ]);
    const [observer] = intersectionObservers;
    const [a, b] = ["a", "b"].map((id) => document.getElementById(id));
    observer.callback([
      { target: a, isIntersecting: true, intersectionRatio: 1 },
    ]);

    const Second = () => {
      useElementObserver(
        "a",
        { onIntersect: (...args) => reports.push(["second", ...args]) },
        {},
      );
      return null;
    };
    renderRoot(createElement(Second));
    // Observed anew, so the browser measures it again.
    expect(intersectionObservers).toHaveLength(1);
    expect(observer.observed).toEqual([b, a]);
    expect(reports).toEqual([["a", true, 1]]);

    // Half in view by now, which crossed no threshold for the first observer.
    observer.callback([
      { target: a, isIntersecting: true, intersectionRatio: 0.5 },
    ]);
    observer.callback([
      { target: a, isIntersecting: false, intersectionRatio: 0 },
    ]);
    expect(reports).toEqual([
      ["a", true, 1],
      ["second", true, 0.5],
      ["a", false, 0],
      ["second", false, 0],
    ]);
  });

  test("an observer that joins and leaves before its fresh entry repeats nothing to the others", () => {
    const reports = [];
    mountTwo((id) => [
      { onIntersect: (...args) => reports.push([id, ...args]) },
      {},
    ]);
    const [observer] = intersectionObservers;
    const a = document.getElementById("a");
    observer.callback([
      { target: a, isIntersecting: true, intersectionRatio: 1 },
    ]);

    const Second = () => {
      useElementObserver(
        "a",
        { onIntersect: (...args) => reports.push(["second", ...args]) },
        {},
      );
      return null;
    };
    renderRoot(createElement(Second)).unmount();
    observer.callback([
      { target: a, isIntersecting: true, intersectionRatio: 1 },
    ]);
    observer.callback([
      { target: a, isIntersecting: false, intersectionRatio: 0 },
    ]);
    expect(reports).toEqual([
      ["a", true, 1],
      ["a", false, 0],
    ]);
  });

  test("an element that is not on the page is not observed", () => {
    const calls = [];
    mount(() => ({
      handlers: { onResize: () => calls.push("resize") },
      options: {},
      id: "missing",
    }));
    expect(calls).toEqual([]);
    expect(resizeObservers).toEqual([]);
  });
});

describe("following the id", () => {
  test("an element that comes onto the page later is observed from then on", async () => {
    const widths = [];
    mount(() => ({
      handlers: { onResize: (width) => widths.push(width) },
      options: {},
      id: "late",
    }));
    expect(resizeObservers).toEqual([]);

    layOut({ width: 70 });
    const late = place("late");
    await pageChanged();
    expect(resizeObservers).toHaveLength(1);
    expect(resizeObservers[0].observed).toEqual([
      [late, { box: "border-box" }],
    ]);
    expect(widths).toEqual([70]);
  });

  test("an element that takes the id over is observed instead", async () => {
    const widths = [];
    const first = place("target");
    mount(() => ({
      handlers: { onResize: (width) => widths.push(width) },
      options: {},
      id: "target",
    }));
    expect(resizeObservers[0].observed[0][0]).toBe(first);

    first.remove();
    await pageChanged();
    expect(resizeObservers[0].disconnected).toBe(true);
    expect(resizeObservers).toHaveLength(1);

    layOut({ width: 120 });
    const second = place("target");
    await pageChanged();
    expect(resizeObservers).toHaveLength(2);
    expect(resizeObservers[1].observed[0][0]).toBe(second);
    expect(widths).toEqual([100, 120]);
  });

  test("an element that gets the id is observed", async () => {
    const tops = [];
    mount(() => ({
      handlers: { onMove: (_x, y) => tops.push(y) },
      options: {},
      id: "renamed",
    }));
    const element = place("other");
    await pageChanged();
    expect(tops).toEqual([]);

    element.id = "renamed";
    await pageChanged();
    expect(tops).toEqual([10]);
  });

  test("stops following the id when unmounted", async () => {
    const widths = [];
    const { unmount } = mount(() => ({
      handlers: { onResize: (width) => widths.push(width) },
      options: {},
      id: "late",
    }));
    unmount();
    place("late");
    await pageChanged();
    expect(widths).toEqual([]);
    expect(resizeObservers).toEqual([]);
  });
});
