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

/** The roots still mounted, unmounted after each test so none follows its id on. */
let roots;

beforeEach(() => {
  resizeObservers = [];
  intersectionObservers = [];
  roots = new Set();
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
  vi.stubGlobal("IntersectionObserver", FakeIntersectionObserver);
});

afterEach(() => {
  for (const root of roots) {
    act(() => root.unmount());
  }
  vi.unstubAllGlobals();
  document.body.replaceChildren();
});

/** The rect the stand-in layout gives the observed element. */
let rect;

/** Move or resize the observed element in the stand-in layout. */
const layOut = (changes) => {
  rect = { ...rect, ...changes };
};

/** Lay the element out in the stand-in layout. */
const measured = (element) => {
  element.getBoundingClientRect = () => rectOf(rect);
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
          measured(element);
        }
      },
    });
  };
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  roots.add(root);
  const render = (next) =>
    act(() => root.render(createElement(Observed, next)));
  render(props(log));
  return {
    log,
    render: (next) => render(next(log)),
    box: () => document.getElementById("box"),
    unmount: () => {
      roots.delete(root);
      act(() => root.unmount());
    },
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
