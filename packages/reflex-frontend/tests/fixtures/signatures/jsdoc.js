/**
 * @param {number} count
 * @param {string} elementId
 * @param {boolean} [loud]
 */
export function celebrate(count, elementId, loud = false) {
  return [count, elementId, loud];
}

/** @param {...string} names */
export function many(...names) {
  return names;
}

export const untyped = (a, b) => a + b;

export const notAFunction = 3;

export default function () {}

/** @type {any} */
export const anything = globalThis.somethingUntyped;

/** @param {import("./shapes").Shape} shape */
export function draw(shape) {
  return shape;
}
