/**
 * The document's scripts: what a prerendered page gets in place of
 * react-router's module preloads, and when the inline script that replaces
 * them starts the modules.
 */
import { createElement } from "react";
import { renderToString } from "react-dom/server";
import {
  createStaticHandler,
  Scripts as RouterScripts,
  ServerRouter,
} from "react-router";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import {
  FIRST_PAINT_TIMEOUT_MS,
  START_AFTER_FIRST_PAINT,
  Scripts,
} from "$/utils/scripts";

const ROOT_MODULE = "/assets/root-4.js";

/**
 * The hrefs react-router preloads for the document rendered below.
 * @param {string} rootModule The href of the root route's module.
 * @returns {string[]} The hrefs, in the order it renders them.
 */
const preloads = (rootModule = ROOT_MODULE) => [
  "/assets/manifest-1.js",
  "/assets/entry.client-2.js",
  "/assets/chunk-3.js",
  rootModule,
];

/**
 * The module script react-router renders for the document rendered below.
 * @param {string} rootModule The href of the root route's module.
 * @returns {string} Its source.
 */
const moduleSource = (rootModule = ROOT_MODULE) =>
  [
    'import "/assets/manifest-1.js";',
    `import * as route0 from ${JSON.stringify(rootModule)};`,
    "  ",
    '  window.__reactRouterRouteModules = {"root":route0};',
    "",
    'import("/assets/entry.client-2.js");',
  ].join("\n");

const CONTEXT_SCRIPT =
  "<script>window.__reactRouterContext = {};window.__reactRouterContext.stream = new ReadableStream({start(controller){window.__reactRouterContext.streamController = controller;}}).pipeThrough(new TextEncoderStream());</script>";

/**
 * Render a document whose body ends in the given scripts component, the way a
 * build renders a page to HTML.
 * @param {object} options What to render.
 * @param {(props: object) => import("react").ReactNode} options.scripts The scripts component.
 * @param {boolean} options.isSpaMode False for a prerendered page, true for one rendered in the browser.
 * @param {string} [options.rootModule] The href of the root route's module.
 * @returns {Promise<string>} The document's HTML.
 */
const renderDocument = async ({
  scripts,
  isSpaMode,
  rootModule = ROOT_MODULE,
}) => {
  const Layout = ({ children }) =>
    createElement(
      "html",
      null,
      createElement("head"),
      createElement("body", null, children, createElement(scripts)),
    );
  const staticHandlerContext = await createStaticHandler([
    { id: "root", path: "/" },
  ]).query(new Request("http://localhost/"));
  return renderToString(
    createElement(ServerRouter, {
      url: "http://localhost/",
      context: /** @type {any} */ ({
        manifest: {
          url: "/assets/manifest-1.js",
          version: "1",
          entry: {
            module: "/assets/entry.client-2.js",
            imports: ["/assets/chunk-3.js"],
          },
          routes: {
            root: {
              id: "root",
              path: "/",
              module: rootModule,
              imports: ["/assets/chunk-3.js"],
            },
          },
        },
        routeModules: {
          root: {
            Layout,
            default: () => createElement("p", null, "page"),
            HydrateFallback: () => createElement("p", null, "loading"),
          },
        },
        staticHandlerContext,
        serverHandoffString: "{}",
        future: {},
        ssr: false,
        isSpaMode,
        routeDiscovery: { mode: "initial" },
      }),
    }),
  );
};

describe("Scripts", () => {
  test("a prerendered page preloads no script and starts its modules inline", async () => {
    expect(await renderDocument({ scripts: Scripts, isSpaMode: false })).toBe(
      `<html><head></head><body><p>page</p>${CONTEXT_SCRIPT}<script>(${START_AFTER_FIRST_PAINT})(${JSON.stringify(preloads())},${JSON.stringify(moduleSource())},${FIRST_PAINT_TIMEOUT_MS})</script></body></html>`,
    );
  });

  test("a page rendered in the browser gets react-router's scripts", async () => {
    const expected = `<html><head>${preloads()
      .map((href) => `<link rel="modulepreload" href="${href}"/>`)
      .join(
        "",
      )}</head><body><p>loading</p>${CONTEXT_SCRIPT}<script type="module" async="">${moduleSource()}</script></body></html>`;
    expect(await renderDocument({ scripts: Scripts, isSpaMode: true })).toBe(
      expected,
    );
    expect(
      await renderDocument({ scripts: RouterScripts, isSpaMode: true }),
    ).toBe(expected);
  });

  test("an href cannot close the inline script", async () => {
    const rootModule = "/assets/root-4.js?</script><script>alert(1)";
    const literal = (value) => JSON.stringify(value).replaceAll("<", "\\u003c");
    expect(literal(preloads(rootModule))).toBe(
      '["/assets/manifest-1.js","/assets/entry.client-2.js","/assets/chunk-3.js","/assets/root-4.js?\\u003c/script>\\u003cscript>alert(1)"]',
    );
    expect(
      await renderDocument({ scripts: Scripts, isSpaMode: false, rootModule }),
    ).toBe(
      `<html><head></head><body><p>page</p>${CONTEXT_SCRIPT}<script>(${START_AFTER_FIRST_PAINT})(${literal(preloads(rootModule))},${literal(moduleSource(rootModule))},${FIRST_PAINT_TIMEOUT_MS})</script></body></html>`,
    );
  });
});

const PRELOADS = preloads();
const MODULE_SOURCE = moduleSource();
const STARTED = `${PRELOADS.map((href) => `<link rel="modulepreload" href="${href}">`).join("")}<script type="module">${MODULE_SOURCE}</script>`;

describe("START_AFTER_FIRST_PAINT", () => {
  /** @type {{callback: () => void, options: object, disconnect: import("vitest").Mock}[]} */
  let observers;
  let visibilityState;

  /**
   * Run the inline script as the browser does when it parses the page.
   * @param {string} [nonce] The nonce of the inline script.
   */
  const run = (nonce = "") => {
    const current = document.createElement("script");
    current.nonce = nonce;
    vi.spyOn(document, "currentScript", "get").mockReturnValue(current);
    new Function(
      "preloads",
      "source",
      "timeout",
      `(${START_AFTER_FIRST_PAINT})(preloads,source,timeout)`,
    )(PRELOADS, MODULE_SOURCE, FIRST_PAINT_TIMEOUT_MS);
  };

  beforeEach(() => {
    vi.useFakeTimers();
    observers = [];
    visibilityState = "visible";
    vi.spyOn(document, "visibilityState", "get").mockImplementation(
      () => visibilityState,
    );
    vi.stubGlobal(
      "PerformanceObserver",
      class {
        static supportedEntryTypes = ["navigation", "paint", "resource"];
        constructor(callback) {
          this.callback = callback;
          this.disconnect = vi.fn();
          observers.push(this);
        }
        observe(options) {
          this.options = options;
        }
      },
    );
  });

  afterEach(() => {
    // Triggers every listener the script left on the document.
    document.dispatchEvent(new Event("visibilitychange"));
    document.dispatchEvent(new Event("pointerdown"));
    document.dispatchEvent(new Event("keydown"));
    document.removeEventListener("click", window.__reflex_early?.record, true);
    window.__reflex_early = undefined;
    document.head.innerHTML = "";
    document.body.innerHTML = "";
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  test("starts the modules once, when the page first paints", () => {
    run();
    expect(document.head.innerHTML).toBe("");
    expect(observers.map(({ options }) => options)).toEqual([
      { type: "paint", buffered: true },
    ]);
    vi.advanceTimersByTime(FIRST_PAINT_TIMEOUT_MS - 1);
    expect(document.head.innerHTML).toBe("");

    observers[0].callback();
    expect(document.head.innerHTML).toBe(STARTED);
    expect(observers[0].disconnect).toHaveBeenCalledTimes(1);

    // No later trigger starts them a second time.
    observers[0].callback();
    vi.advanceTimersByTime(FIRST_PAINT_TIMEOUT_MS);
    document.dispatchEvent(new Event("pointerdown"));
    document.dispatchEvent(new Event("keydown"));
    document.dispatchEvent(new Event("visibilitychange"));
    expect(document.head.innerHTML).toBe(STARTED);
  });

  test("starts the modules after the timeout on a page that paints nothing", () => {
    run();
    vi.advanceTimersByTime(FIRST_PAINT_TIMEOUT_MS - 1);
    expect(document.head.innerHTML).toBe("");
    vi.advanceTimersByTime(1);
    expect(document.head.innerHTML).toBe(STARTED);
    expect(observers[0].disconnect).toHaveBeenCalledTimes(1);
  });

  test.each([
    "pointerdown",
    "keydown",
  ])("starts the modules on a %s that comes before the paint", (type) => {
    run();
    // Dispatched below the document: the listener is a capturing one.
    document.body.dispatchEvent(new Event(type, { bubbles: true }));
    expect(document.head.innerHTML).toBe(STARTED);
  });

  test("starts the modules when the page is hidden before it paints", () => {
    run();
    visibilityState = "hidden";
    document.dispatchEvent(new Event("visibilitychange"));
    expect(document.head.innerHTML).toBe(STARTED);
  });

  test("starts the modules right away in a background tab", () => {
    visibilityState = "hidden";
    run();
    expect(document.head.innerHTML).toBe(STARTED);
    expect(observers).toEqual([]);
    expect(vi.getTimerCount()).toBe(0);
  });

  test("starts the modules right away without paint timing", () => {
    PerformanceObserver.supportedEntryTypes = ["navigation", "resource"];
    run();
    expect(document.head.innerHTML).toBe(STARTED);
    expect(observers).toEqual([]);
  });

  test("starts the modules right away without a performance observer", () => {
    vi.stubGlobal("PerformanceObserver", undefined);
    run();
    expect(document.head.innerHTML).toBe(STARTED);
  });

  test("gives the module script the nonce of the inline one", () => {
    visibilityState = "hidden";
    run("abc");
    expect(document.head.querySelector("script").nonce).toBe("abc");
  });

  describe("a click before the page is hydrated", () => {
    /**
     * Put an element on the page and collect the clicks that reach it.
     * @param {string} html Markup holding an element with the id `target`.
     * @returns {{target: HTMLElement, clicks: MouseEvent[]}} The element and its clicks.
     */
    const addToPage = (html) => {
      document.body.innerHTML = html;
      const target = document.getElementById("target");
      const clicks = [];
      target.addEventListener("click", (event) => clicks.push(event));
      return { target, clicks };
    };

    /**
     * Load the module as the page's scripts do, and mount the scripts
     * component, which is when a hydrated page runs its effects.
     */
    const hydrate = async () => {
      vi.resetModules();
      const { act, createElement } = await import("react");
      const { createRoot } = await import("react-dom/client");
      const { createRoutesStub } = await import("react-router");
      const { Scripts } = await import("$/utils/scripts");
      const Stub = createRoutesStub([
        { path: "/", Component: () => createElement(Scripts) },
      ]);
      const container = document.body.appendChild(
        document.createElement("div"),
      );
      act(() => createRoot(container).render(createElement(Stub)));
    };

    const click = (target, init = {}) =>
      target.dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true, ...init }),
      );

    test("is dispatched again once the page is hydrated", async () => {
      const { target, clicks } = addToPage(
        '<button id="target"><svg id="icon"></svg></button>',
      );
      run();
      click(document.getElementById("icon"), { clientX: 7, ctrlKey: true });
      expect(clicks.length).toBe(1);

      await hydrate();
      expect(
        clicks.map(({ target, clientX, ctrlKey, bubbles }) => ({
          target: target.id,
          clientX,
          ctrlKey,
          bubbles,
        })),
      ).toEqual([
        { target: "icon", clientX: 7, ctrlKey: true, bubbles: true },
        { target: "icon", clientX: 7, ctrlKey: true, bubbles: true },
      ]);
      expect(clicks[1]).not.toBe(clicks[0]);
      expect(window.__reflex_early).toBe(undefined);

      // The page handles its own clicks from here on.
      click(target);
      await hydrate();
      expect(clicks.length).toBe(3);
    });

    test("only the last one is dispatched again", async () => {
      const first = addToPage('<button id="target"></button>');
      run();
      click(first.target);
      const other = document.body.appendChild(document.createElement("button"));
      const otherClicks = [];
      other.addEventListener("click", (event) => otherClicks.push(event));
      click(other);
      click(other);

      await hydrate();
      expect(first.clicks.length).toBe(1);
      expect(otherClicks.length).toBe(3);
    });

    test.each([
      '<a href="/other" id="target">link</a>',
      '<a href="/other"><span id="target">link</span></a>',
      '<input type="checkbox" id="target">',
      '<label><span id="target">label</span><input type="checkbox"></label>',
      '<select id="target"><option>one</option></select>',
      '<textarea id="target"></textarea>',
      '<details><summary id="target">more</summary></details>',
      '<div contenteditable id="target"></div>',
    ])("is left alone where the browser acted on it: %s", async (html) => {
      const { target, clicks } = addToPage(html);
      target.addEventListener("click", (event) => event.preventDefault());
      run();
      click(target);
      await hydrate();
      expect(clicks.length).toBe(1);
    });

    test("is dropped when its target has left the page", async () => {
      const { target, clicks } = addToPage('<button id="target"></button>');
      run();
      click(target);
      target.remove();
      await hydrate();
      expect(clicks.length).toBe(1);
    });

    test("a click after the scripts loaded is not recorded", async () => {
      const { target, clicks } = addToPage('<button id="target"></button>');
      run();
      const { record } = window.__reflex_early;
      await hydrate();
      click(target);
      expect(clicks.length).toBe(1);
      record(clicks[0]);
      await hydrate();
      expect(clicks.length).toBe(1);
    });
  });
});
