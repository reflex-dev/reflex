// Set operations over the JSON array that a Python set or frozenset
// serializes to. The array stays the wire value and the state value;
// these helpers only give it Python set semantics.

/**
 * Key a set element by value, so structured elements (tuples, dataclasses)
 * compare the way Python compares them rather than by object identity.
 * Numbers and null are their own key, booleans are keyed as the numbers
 * they equal in Python (True == 1, False == 0), and strings and objects get
 * distinct prefixes so a string can never share a key with an object's JSON.
 * @param {*} x The set element.
 * @returns {*} The key of the element.
 */
export const pySetKey = (x) => {
  if (typeof x === "string") return "s" + x;
  if (typeof x === "boolean") return +x;
  if (x !== null && typeof x === "object") return "o" + JSON.stringify(x);
  return x;
};

/**
 * Check whether a set (as an array) contains an element.
 * @param {Array} arr The set.
 * @param {*} x The element to look for.
 * @returns {boolean} Whether the set contains the element.
 */
export const pySetHas = (arr, x) => {
  const key = pySetKey(x);
  // SameValueZero, as Set.has uses: NaN matches NaN, without copying arr.
  const isNaNKey = key !== key;
  return arr.some((y) => {
    const other = pySetKey(y);
    return other === key || (isNaNKey && other !== other);
  });
};

/**
 * The elements of either set, keeping the order of a then b.
 * @param {Array} a The first set.
 * @param {Array} b The second set.
 * @returns {Array} The union.
 */
export const pySetUnion = (a, b) => {
  const seen = new Set(a.map(pySetKey));
  const result = [...a];
  for (const x of b) {
    const key = pySetKey(x);
    if (!seen.has(key)) {
      seen.add(key);
      result.push(x);
    }
  }
  return result;
};

/**
 * The elements of a that are also in b.
 * @param {Array} a The first set.
 * @param {Array} b The second set.
 * @returns {Array} The intersection.
 */
export const pySetIntersection = (a, b) => {
  const keys = new Set(b.map(pySetKey));
  return a.filter((x) => keys.has(pySetKey(x)));
};

/**
 * The elements of a that are not in b.
 * @param {Array} a The first set.
 * @param {Array} b The second set.
 * @returns {Array} The difference.
 */
export const pySetDifference = (a, b) => {
  const keys = new Set(b.map(pySetKey));
  return a.filter((x) => !keys.has(pySetKey(x)));
};

/**
 * The elements in exactly one of a and b, without duplicates even when an
 * operand is a plain array that holds some.
 * @param {Array} a The first set.
 * @param {Array} b The second set.
 * @returns {Array} The symmetric difference.
 */
export const pySetSymmetricDifference = (a, b) =>
  pySetUnion(pySetDifference(a, b), pySetDifference(b, a));

/**
 * Whether every element of a is in b.
 * @param {Array} a The first set.
 * @param {Array} b The second set.
 * @returns {boolean} Whether a is a subset of b.
 */
export const pySetIsSubset = (a, b) => {
  const keys = new Set(b.map(pySetKey));
  return a.every((x) => keys.has(pySetKey(x)));
};

/**
 * Whether a and b have no element in common.
 * @param {Array} a The first set.
 * @param {Array} b The second set.
 * @returns {boolean} Whether the sets are disjoint.
 */
export const pySetIsDisjoint = (a, b) => {
  const keys = new Set(b.map(pySetKey));
  return !a.some((x) => keys.has(pySetKey(x)));
};
