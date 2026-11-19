const isNumeric = (value) =>
  typeof value === "number" || typeof value === "boolean";

const isPlainObject = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);

/** Order two strings by code point like Python.
 *
 * JS `<` orders UTF-16 code units, so a character above U+FFFF (stored as a
 * surrogate pair from 0xD800) sorts before U+E000..U+FFFF. Comparing the code
 * points at the first differing unit fixes that without decoding the rest.
 */
function compareStrings(lhs, rhs) {
  const sharedLength = Math.min(lhs.length, rhs.length);
  for (let i = 0; i < sharedLength; i++) {
    if (lhs.charCodeAt(i) !== rhs.charCodeAt(i)) {
      return lhs.codePointAt(i) < rhs.codePointAt(i) ? -1 : 1;
    }
  }
  return Math.sign(lhs.length - rhs.length);
}

/** Order two numbers, booleans (as 0 or 1) or strings like Python.
 *
 * NaN for a pair Python cannot order: a NaN operand or mismatched types.
 */
function compareScalars(lhs, rhs) {
  if (isNumeric(lhs) && isNumeric(rhs)) {
    const left = Number(lhs);
    const right = Number(rhs);
    return left < right ? -1 : left > right ? 1 : left === right ? 0 : NaN;
  }
  if (typeof lhs === "string" && typeof rhs === "string") {
    return compareStrings(lhs, rhs);
  }
  return NaN;
}

/** Check two serialized dicts for equality like Python `==`. */
function dictsEqual(lhs, rhs) {
  const keys = Object.keys(lhs);
  return (
    keys.length === Object.keys(rhs).length &&
    keys.every(
      (key) => Object.hasOwn(rhs, key) && valuesEqual(lhs[key], rhs[key]),
    )
  );
}

/** Check two serialized values for equality like Python `==`. */
function valuesEqual(lhs, rhs) {
  if (Object.is(lhs, rhs)) {
    return true;
  }
  if (Array.isArray(lhs) && Array.isArray(rhs)) {
    return compareArrays(lhs, rhs) === 0;
  }
  if (isPlainObject(lhs) && isPlainObject(rhs)) {
    return dictsEqual(lhs, rhs);
  }
  return isNumeric(lhs) && isNumeric(rhs) && Number(lhs) === Number(rhs);
}

/** Compare two arrays element-wise with Python list semantics.
 *
 * The first unequal pair of items decides the result; when every shared item
 * is equal, the shorter array sorts first. Like Python, which checks identity
 * before `==`, a NaN item equals NaN: serialized state cannot tell the same NaN
 * object from another one, so it takes the identical case. Nested arrays compare recursively.
 * Dicts only take part through equality, as in Python: equal dicts move on to
 * the next pair, unequal ones cannot be ordered.
 *
 * Returns -1, 0 or 1, or NaN when Python would raise TypeError or a NaN item
 * meets a number, so every ordering operator gives false. That covers a
 * non-array operand (an optional list holding None) and mismatched items.
 *
 * @param compareItem orders two items that are not arrays or dicts; the
 *   compiler passes compareDatetime for lists of dates, which arrive as
 *   strings.
 */
export default function compareArrays(lhs, rhs, compareItem = compareScalars) {
  if (!Array.isArray(lhs) || !Array.isArray(rhs)) {
    return NaN;
  }
  const sharedLength = Math.min(lhs.length, rhs.length);
  for (let i = 0; i < sharedLength; i++) {
    const left = lhs[i];
    const right = rhs[i];
    if (Object.is(left, right)) {
      continue;
    }
    const order =
      Array.isArray(left) && Array.isArray(right)
        ? compareArrays(left, right, compareItem)
        : isPlainObject(left) && isPlainObject(right)
          ? dictsEqual(left, right)
            ? 0
            : NaN
          : compareItem(left, right);
    if (order !== 0) {
      return order;
    }
  }
  return Math.sign(lhs.length - rhs.length);
}
