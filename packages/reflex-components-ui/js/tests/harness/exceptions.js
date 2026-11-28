// Where a value read under the StyleX modules is allowed to differ from the
// one read under @radix-ui/themes, and why. Both pages put what they read
// through `normalize` before the two are compared, so an entry here has to say
// why the difference cannot be seen.

/**
 * @typedef {object} Exception
 * @property {RegExp} pattern The custom properties it applies to.
 * @property {string} reason Why the difference is not one.
 * @property {(value: string) => string} [normalize] Removes the difference
 *   from a computed value.
 * @property {true} [undefined] Neither page defines the custom property, which
 *   is otherwise a failure of the sweep.
 */

/** @type {Exception[]} */
export const EXCEPTIONS = [
  {
    pattern:
      /^--(code-font-weight|strong-font-style|em-font-weight|quote-font-weight)$/,
    reason:
      "Radix declares these as `inherit`. That is a CSS-wide keyword on a custom property too: the property inherits from the parent, which has none, so it is not defined and `var()` of it is invalid. The modules declare the same and get the same.",
    undefined: true,
  },
  {
    pattern: /^--shadow-\d$/,
    reason:
      "The light and dark shadows of Radix differ in geometry, and `light-dark()` only chooses between colors. A shadow here lists the layers of both appearances, and a layer the current appearance does not have is `transparent`: it paints nothing, but it is in the computed value.",
    normalize: (value) => {
      const layers = value
        .split(/, (?![^(]*\))/)
        .filter((layer) => !layer.startsWith("rgba(0, 0, 0, 0) "));
      return layers.join(", ") || "none";
    },
  },
];
