// The pages the sweep shows: every value of every prop of a Radix `Theme`.

import { themePropDefs } from "@radix-ui/themes/props";

/** @typedef {import("./page.js").Config} Config */

const { accentColor, grayColor, radius, scaling, panelBackground } =
  themePropDefs;

export const APPEARANCES = /** @type {const} */ (["light", "dark"]);
export const ACCENTS = accentColor.values;
export const GRAYS = grayColor.values;
export const RADII = radius.values;
export const SCALINGS = scaling.values;
export const PANELS = panelBackground.values;

/** @type {Config["theme"]} */
export const DEFAULT_THEME = {
  accentColor: accentColor.default,
  grayColor: grayColor.default,
  radius: radius.default,
  scaling: scaling.default,
  panelBackground: panelBackground.default,
  hasBackground: true,
};

/**
 * Every combination of the values of some props, the others at their default.
 *
 * @param {{ [Key in keyof Config["theme"]]?: readonly Config["theme"][Key][] }} props
 *   The values to combine.
 * @returns {Config[]} One page for each combination, in each appearance.
 */
export function combinations(props) {
  /** @type {Config[]} */
  let configs = APPEARANCES.map((appearance) => ({
    appearance,
    theme: DEFAULT_THEME,
  }));
  for (const [prop, values] of Object.entries(props)) {
    configs = configs.flatMap((config) =>
      values.map((value) => ({
        ...config,
        theme: { ...config.theme, [prop]: value },
      })),
    );
  }
  return configs;
}

/**
 * The whole sweep: the product of every accent, gray, appearance, radius and
 * scaling, then the panel and the background against every color.
 *
 * @returns {Config[]} 10,556 pages.
 */
export function fullSweep() {
  return [
    ...combinations({
      accentColor: ACCENTS,
      grayColor: GRAYS,
      radius: RADII,
      scaling: SCALINGS,
    }),
    ...combinations({
      accentColor: ACCENTS,
      grayColor: GRAYS,
      panelBackground: PANELS,
      hasBackground: [true, false],
    }),
  ];
}

/**
 * The part of the sweep `npm test` runs: every value of every prop, combined
 * only with the props its tokens depend on.
 *
 * @returns {Config[]} 470 pages.
 */
export function fastSweep() {
  return [
    ...combinations({ accentColor: ACCENTS, grayColor: GRAYS }),
    ...combinations({ radius: RADII, scaling: SCALINGS }),
    ...combinations({
      grayColor: GRAYS,
      panelBackground: PANELS,
      hasBackground: [true, false],
    }),
  ];
}
