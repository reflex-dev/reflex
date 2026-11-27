// Runs in both pages of the sweep: reads what every custom property resolves to
// on an element, through a property of the type the value has. The computed
// value of the custom property itself would not do: here it is the
// `light-dark()` pair, in Radix the color of one appearance.

import { EXCEPTIONS } from "./exceptions.js";

// The property each custom property is read through. The first match wins, and
// a custom property with no match fails the sweep.
const PROBES = /** @type {const} */ ([
  [/^--shadow-/, "box-shadow"],
  [/^--cursor-/, "cursor"],
  [/^--backdrop-filter-/, "backdrop-filter"],
  [/-font-family$/, "font-family"],
  [/-font-style$/, "font-style"],
  [/^--font-weight-|-font-weight$/, "font-weight"],
  [/^--default-line-height$/, "line-height"],
  [/^--scaling$|^--radius-factor$|-font-size-adjust$/, "flex-grow"],
  [
    /^--(space|radius|font-size|line-height|heading-line-height|letter-spacing)-|^--default-font-size$|-(letter|word)-spacing$|-leading-trim-(start|end)$|^--code-padding-/,
    "margin-left",
  ],
  [/^--color-|^--[a-z]+-(a?\d+|contrast|surface|indicator|track)$/, "color"],
]);

// What Radix sets on a theme element itself.
const ELEMENT = [
  "color",
  "background-color",
  "font-family",
  "font-size",
  "font-weight",
  "font-style",
  "line-height",
  "letter-spacing",
  "overflow-wrap",
  "text-size-adjust",
  "-webkit-font-smoothing",
];

/**
 * The names of the values `read` returns.
 *
 * @param {string[]} names The custom properties.
 * @returns {string[]} Them, then the properties of the theme element.
 */
export function labels(names) {
  return [...names, ...ELEMENT.map((property) => `(element) ${property}`)];
}

/**
 * Add an element for each custom property, styled with it.
 *
 * @param {Element} container Where the elements go.
 * @param {string[]} names The custom properties.
 * @returns {{ name: string, property: string, style: CSSStyleDeclaration, exception?: import("./exceptions.js").Exception }[]}
 *   What to read each one from.
 */
export function mount(container, names) {
  return names.map((name) => {
    const property = PROBES.find(([pattern]) => pattern.test(name))?.[1];
    if (!property) throw new Error(`No probe for ${name}`);
    const element = document.createElement("i");
    element.style.setProperty(property, `var(${name})`);
    container.append(element);
    const exception = EXCEPTIONS.find(({ pattern }) => pattern.test(name));
    return { name, property, style: getComputedStyle(element), exception };
  });
}

/**
 * What every custom property resolves to, and the theme element's own styles.
 *
 * @param {ReturnType<typeof mount>} probes What `mount` returned.
 * @param {Element} theme The theme element the probes are in.
 * @returns {string[]} A value for each of `labels`. A custom property that is
 *   not defined, or whose value is not one its probe takes, reads as `INVALID`
 *   and what it holds, as both pages would otherwise agree on the fallback.
 */
export function read(probes, theme) {
  const inherited = getComputedStyle(theme);
  const values = probes.map(({ name, property, style, exception }) => {
    const raw = style.getPropertyValue(name);
    if (raw === "" && exception?.undefined) return "undefined";
    if (raw === "" || !CSS.supports(property, raw)) return `INVALID ${raw}`;
    const value = style.getPropertyValue(property);
    return exception?.normalize ? exception.normalize(value) : value;
  });
  for (const property of ELEMENT) {
    values.push(inherited.getPropertyValue(property));
  }
  return values;
}

/**
 * A short digest of the values, to compare a combination without moving them
 * all out of the page.
 *
 * @param {string[]} values What `read` returned.
 * @returns {{ hash: number, invalid: number }} An FNV-1a hash, and how many of
 *   the values are invalid.
 */
export function digest(values) {
  let hash = 0x811c9dc5;
  let invalid = 0;
  for (const value of values) {
    if (value.startsWith("INVALID")) invalid++;
    for (let index = 0; index < value.length; index++) {
      hash = Math.imul(hash ^ value.charCodeAt(index), 0x01000193);
    }
    hash = Math.imul(hash ^ 0xff, 0x01000193);
  }
  return { hash: hash >>> 0, invalid };
}
