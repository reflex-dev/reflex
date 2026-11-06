/** Compare two arrays element-wise with Python list semantics.
 *
 * Elements are compared pairwise in order; the first unequal pair decides
 * the result. If every shared element is equal, the shorter array sorts
 * before the longer one. Nested arrays are compared recursively.
 *
 * Booleans compare as numbers (0 or 1), matching Python where bool is a
 * subclass of int, so [true] and [1] compare equal.
 *
 * Returns NaN when an element pair contains NaN (Python makes every
 * ordering comparison against float("nan") false) or when elements are
 * incomparable (mismatched or unsupported types, where Python raises
 * TypeError). Either way every ordering result is false instead of a
 * silent string comparison.
 */
export default function compareArrays(lhs, rhs) {
  const sharedLength = Math.min(lhs.length, rhs.length);
  for (let i = 0; i < sharedLength; i++) {
    const left = lhs[i];
    const right = rhs[i];
    if (left === right) {
      continue;
    }
    if (Array.isArray(left) && Array.isArray(right)) {
      const nested = compareArrays(left, right);
      if (nested !== 0) {
        return nested;
      }
      continue;
    }
    const leftIsNumeric = typeof left === "number" || typeof left === "boolean";
    const rightIsNumeric =
      typeof right === "number" || typeof right === "boolean";
    if (leftIsNumeric && rightIsNumeric) {
      const leftNumber = Number(left);
      const rightNumber = Number(right);
      if (Number.isNaN(leftNumber) || Number.isNaN(rightNumber)) {
        return Number.NaN;
      }
      if (leftNumber === rightNumber) {
        continue;
      }
      return leftNumber < rightNumber ? -1 : 1;
    }
    if (typeof left === "string" && typeof right === "string") {
      return left < right ? -1 : 1;
    }
    return Number.NaN;
  }
  return Math.sign(lhs.length - rhs.length);
}
