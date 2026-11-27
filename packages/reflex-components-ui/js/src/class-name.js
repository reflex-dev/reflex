// The class names of compiled StyleX styles: what `stylex.props(...).className`
// gives, without the rest of the StyleX runtime.
//
// StyleX folds that call into a string only when every argument is declared
// in the module that makes it. A theme is declared in a module of its own, so
// the element that carries one joins its classes when the page loads.

/**
 * A compiled style: a class name for each property it sets, and a marker.
 *
 * @typedef {Readonly<Record<string, unknown>>} CompiledStyle
 */

/**
 * Join the class names of compiled styles, a later style winning a property
 * that an earlier one also sets.
 *
 * @param {...(CompiledStyle | false | null | undefined)} styles The styles,
 *   and anything falsy for a style that does not apply.
 * @returns {string} The class names of what is left of each style.
 */
export function className(...styles) {
  /** @type {Record<string, unknown>} */
  const merged = {};
  for (const style of styles) {
    if (style) Object.assign(merged, style);
  }
  const names = [];
  for (const key in merged) {
    const name = merged[key];
    // The marker of a compiled style is no class, and neither is a property
    // a style unsets.
    if (key !== "$$css" && typeof name === "string") names.push(name);
  }
  return names.join(" ");
}
