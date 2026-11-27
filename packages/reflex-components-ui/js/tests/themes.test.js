// @vitest-environment node
//
// The tokens and themes in a browser: a page built with the StyleX modules next
// to one built with @radix-ui/themes, in headless Chromium. `npm run sweep`
// compares the whole product of the theme props the same way.

import { afterAll, beforeAll, beforeEach, expect, test } from "vitest";

import { openHarness } from "./harness/browser.js";
import { APPEARANCES, DEFAULT_THEME, fastSweep } from "./harness/configs.js";
import { EXCEPTIONS } from "./harness/exceptions.js";

/** @typedef {import("./harness/page.js").Config} Config */

const GAMUTS = /** @type {const} */ (["srgb", "p3"]);

/** @type {Awaited<ReturnType<typeof openHarness>>} */
let harness;

beforeAll(async () => {
  harness = await openHarness();
}, 120_000);

beforeEach(async () => {
  await harness.setGamut("srgb");
});

afterAll(async () => {
  await harness.close();
});

/**
 * Compare pages under both modules and Radix, on both kinds of screen.
 *
 * @param {Config[]} configs The pages.
 * @returns {Promise<import("./harness/browser.js").Difference[]>} Every value
 *   the two disagree on.
 */
async function differences(configs) {
  const found = [];
  for (const gamut of GAMUTS) {
    found.push(...(await harness.compare(configs, gamut)).differences);
  }
  return found;
}

/**
 * The declared value of custom properties on the root theme element and on a
 * theme nested in it.
 *
 * @param {Config} config The page to show.
 * @param {string[]} names The custom properties.
 * @returns {Promise<{ root: Record<string, string>, nested: Record<string, string> }>}
 *   The values, before `light-dark()` is resolved.
 */
async function declared(config, names) {
  await harness.read(harness.ours, config);
  return harness.ours.evaluate((properties) => {
    const root = /** @type {Element} */ (document.body.firstElementChild);
    const [rootStyle, nestedStyle] = [root, root.firstElementChild].map(
      (element) => getComputedStyle(/** @type {Element} */ (element)),
    );
    /** @type {(style: CSSStyleDeclaration) => Record<string, string>} */
    const values = (style) =>
      Object.fromEntries(
        properties.map((name) => [name, style.getPropertyValue(name)]),
      );
    return { root: values(rootStyle), nested: values(nestedStyle) };
  }, names);
}

test("the sweep reads every custom property of the Radix token stylesheet", () => {
  expect(harness.names.length).toBe(1068);
  expect(
    EXCEPTIONS.map(({ pattern }) =>
      harness.names.filter((name) => pattern.test(name)),
    ),
  ).toEqual([
    [
      "--code-font-weight",
      "--strong-font-style",
      "--em-font-weight",
      "--quote-font-weight",
    ],
    [
      "--shadow-1",
      "--shadow-2",
      "--shadow-3",
      "--shadow-4",
      "--shadow-5",
      "--shadow-6",
    ],
  ]);
});

test.each(
  GAMUTS,
)("every custom property has the value Radix gives it, for each value of each theme prop (%s)", async (gamut) => {
  const result = await harness.compare(fastSweep(), gamut);
  expect(result).toEqual({ differences: [], distinct: 396 });
}, 60_000);

test("the class of html decides the appearance of every scale", async () => {
  const [light, dark] = await Promise.all(
    APPEARANCES.map(async (appearance) =>
      harness.read(harness.ours, { appearance, theme: DEFAULT_THEME }),
    ),
  );
  const scales = harness.names.flatMap((name) => {
    const scale = /^--([a-z]+)-a1$/.exec(name)?.[1];
    return scale ? [scale] : [];
  });
  const steps = [...Array(12).keys()].flatMap((step) => [
    `${step + 1}`,
    `a${step + 1}`,
  ]);
  const flipped = scales.filter((scale) =>
    steps.some((step) => {
      const name = `--${scale}-${step}`;
      return name in light && light[name] !== dark[name];
    }),
  );
  expect(scales.length).toBe(35);
  // The two overlay scales are the same in both appearances.
  expect(flipped).toEqual(
    scales.filter((scale) => scale !== "black" && scale !== "white"),
  );
});

test("a nested theme overrides accent, gray, radius and scaling for its subtree only", async () => {
  /** @type {Config} */
  const config = {
    appearance: "light",
    theme: DEFAULT_THEME,
    nested: {
      accentColor: "red",
      grayColor: "sand",
      radius: "full",
      scaling: "110%",
      hasBackground: false,
    },
  };
  expect(
    await declared(config, [
      "--accent-9",
      "--gray-9",
      "--radius-factor",
      "--radius-full",
      "--scaling",
      "--space-4",
      "--radius-4",
      "--font-size-3",
    ]),
  ).toEqual({
    root: {
      "--accent-9": "#3e63dd",
      "--gray-9": "light-dark(#8b8d98,#696e77)",
      "--radius-factor": "1",
      "--radius-full": "0px",
      "--scaling": "1",
      "--space-4": "calc(16px * 1)",
      "--radius-4": "calc(8px * 1 * 1)",
      "--font-size-3": "calc(16px * 1)",
    },
    nested: {
      "--accent-9": "#e5484d",
      "--gray-9": "light-dark(#8d8d86,#6f6d66)",
      "--radius-factor": "1.5",
      "--radius-full": "9999px",
      "--scaling": "1.1",
      "--space-4": "calc(16px * 1.1)",
      "--radius-4": "calc(8px * 1.1 * 1.5)",
      "--font-size-3": "calc(16px * 1.1)",
    },
  });
  expect(await differences([config])).toEqual([]);
});

// A nested Radix `Theme` inherits the props it is not given from the theme
// around it. Here a nested theme is the classes of what it sets, and the rest
// is inherited by the cascade.
test.each(
  /** @type {[string, Partial<Config["theme"]>, import("./harness/page.js").ThemeProps][]} */ ([
    ["a scaling", {}, { scaling: "90%" }],
    ["a radius", {}, { radius: "none" }],
    ["an accent", {}, { accentColor: "crimson" }],
    ["the gray accent", {}, { accentColor: "gray" }],
    ["a gray", {}, { grayColor: "olive" }],
    [
      "a gray under a solid panel",
      { panelBackground: "solid" },
      { grayColor: "olive" },
    ],
    ["a panel", {}, { panelBackground: "solid" }],
    ["a background", {}, { hasBackground: true }],
    ["the other appearance", {}, { appearance: "dark", hasBackground: true }],
    ["the light appearance", {}, { appearance: "light", hasBackground: true }],
    [
      "an appearance and an accent, under a gray accent",
      { accentColor: "gray" },
      { appearance: "dark", accentColor: "jade", hasBackground: false },
    ],
  ]),
)("a nested theme that only sets %s matches Radix, in the page and in the top layer", async (_, theme, nested) => {
  const configs = APPEARANCES.flatMap((appearance) =>
    [false, true].map((popover) => ({
      appearance,
      theme: { ...DEFAULT_THEME, ...theme },
      nested,
      popover,
    })),
  );
  expect(await differences(configs)).toEqual([]);
});

test("a dark theme inside a light page is one property on its element", async () => {
  /** @type {Config} */
  const config = {
    appearance: "light",
    theme: DEFAULT_THEME,
    nested: { appearance: "dark", hasBackground: true },
  };
  const light = await harness.read(harness.ours, {
    appearance: "light",
    theme: DEFAULT_THEME,
  });
  const dark = await harness.read(harness.ours, {
    appearance: "dark",
    theme: DEFAULT_THEME,
  });
  const nested = await harness.read(harness.ours, config);
  expect(nested).toEqual(dark);
  expect(nested).not.toEqual(light);
  expect(
    await harness.ours.evaluate(() => {
      const root = /** @type {Element} */ (document.body.firstElementChild);
      return [document.documentElement, root, root.firstElementChild].map(
        (element) =>
          getComputedStyle(/** @type {Element} */ (element)).colorScheme,
      );
    }),
  ).toEqual(["light", "light", "dark"]);
});

test("a native popover declared in a nested theme has that theme's values", async () => {
  /** @type {Config} */
  const config = {
    appearance: "light",
    theme: DEFAULT_THEME,
    nested: {
      appearance: "dark",
      accentColor: "red",
      grayColor: "sand",
      radius: "full",
      scaling: "110%",
      panelBackground: "solid",
      hasBackground: true,
    },
  };
  const inPage = await harness.read(harness.ours, config);
  const inPopover = await harness.read(harness.ours, {
    ...config,
    popover: true,
  });
  expect(
    await harness.ours.evaluate(() => {
      const popover = /** @type {Element} */ (
        document.querySelector("[popover]")
      );
      return [
        popover.matches(":popover-open"),
        popover.children.length,
        getComputedStyle(popover).colorScheme,
      ];
    }),
  ).toEqual([true, 1068, "dark"]);
  expect(inPopover).toEqual(inPage);
  expect({
    accent: inPopover["--accent-9"],
    gray: inPopover["--gray-12"],
    radius: inPopover["--radius-4"],
    space: inPopover["--space-4"],
    panel: inPopover["--color-panel"],
  }).toEqual({
    accent: "rgb(229, 72, 77)",
    gray: "rgb(238, 238, 236)",
    radius: "13.2px",
    space: "17.6px",
    panel: "rgb(25, 25, 24)",
  });
});

// The one thing a nested Radix `Theme` does that the cascade cannot: it knows
// that the accent it inherits is the gray, and follows a gray of its own. Here
// the nested theme has to name the gray accent again.
test("a nested gray under an inherited gray accent leaves the accent as it was", async () => {
  /** @type {Config} */
  const config = {
    appearance: "light",
    theme: { ...DEFAULT_THEME, accentColor: "gray" },
    nested: { grayColor: "olive" },
  };
  const { differences: stale } = await harness.compare([config], "srgb");
  expect([
    ...new Set(stale.map(({ label }) => label.replace(/-[a-z]*\d*$/, ""))),
  ]).toEqual(["--focus", "--accent"]);
  expect(
    await differences([
      { ...config, nested: { grayColor: "olive", accentColor: "gray" } },
    ]),
  ).toEqual([]);
});
