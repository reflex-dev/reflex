/**
 * Unit tests for `utils/helpers/element_observer.js`: when the hook reports,
 * what it reports again and when it observes anew. jsdom has no layout and no
 * observers, so the element's rect and the observers are stand-ins the tests
 * drive by hand.
 */
import { act, createElement, useEffect } from "react";
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
  disconnect() {
    this.disconnected = true;
  }
}

class FakeIntersectionObserver {
  constructor(callback, options) {
    this.callback = callback;
    this.options = options;
    this.disconnected = false;
    intersectionObservers.push(this);
  }
  observe(element) {
    this.element = element;
  }
  disconnect() {
    this.disconnected = true;
  }
}

beforeEach(() => {
  resizeObservers = [];
  intersectionObservers = [];
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
  vi.stubGlobal("IntersectionObserver", FakeIntersectionObserver);
});

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.replaceChildren();
});

/** The rect the stand-in layout gives the observed element. */
let rect;

/** Move or resize the observed element in the stand-in layout. */
const layOut = (changes) => {
  rect = { ...rect, ...changes };
};

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

/**
 * Render a component observing `#box`, which it renders itself, in a fresh root.
 * @returns {{log: string[], render: (props: object) => void, box: () => HTMLElement, unmount: () => void}}
 */
const mount = (props) => {
  rect = { x: 0, y: 10, width: 100, height: 50 };
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
          element.getBoundingClientRect = () => rectOf(rect);
        }
      },
    });
  };
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const render = (next) =>
    act(() => root.render(createElement(Observed, next)));
  render(props(log));
  return {
    log,
    render: (next) => render(next(log)),
    box: () => document.getElementById("box"),
    unmount: () => act(() => root.unmount()),
  };
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
    observer.callback();
    layOut({ y: 30 });
    observer.callback();
    expect(sizes).toEqual([[100, 50]]);

    layOut({ height: 80 });
    observer.callback();
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
    resizeObservers[0].callback();
    layOut({ x: 8, width: 84 });
    resizeObservers[0].callback();
    expect(positions).toEqual([
      [0, 10],
      [0, -20],
      [0, -40],
      [0, 5],
      [8, 5],
    ]);
  });

  test("stops listening when unmounted", () => {
    const tops = [];
    const { unmount } = mount(() => ({
      handlers: { onMove: (_x, y) => tops.push(y) },
      options: {},
    }));
    unmount();
    layOut({ y: -20 });
    window.dispatchEvent(new Event("scroll"));
    expect(tops).toEqual([10]);
    expect(resizeObservers[0].disconnected).toBe(true);
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
    expect(observer.element).toBe(document.getElementById("box"));
    expect(observer.options).toEqual({
      threshold: [0, 1],
      rootMargin: "-10px",
    });

    observer.callback([
      { isIntersecting: false, intersectionRatio: 0 },
      { isIntersecting: true, intersectionRatio: 0.5 },
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
    resizeObservers[0].callback();

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
