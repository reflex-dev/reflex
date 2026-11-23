// Set operations over the JSON array that a Python set or frozenset
// serializes to. The array stays the wire value and the state value;
// these helpers only give it Python set semantics. A null or undefined operand
// (a `set | None` var holding None, or a set field of a missing object) is an
// empty set.

/**
 * The JSON value a structured element is keyed by: strings get a prefix,
 * booleans become the numbers they equal in Python, non-finite numbers are
 * spelled out (JSON writes them as null), and objects are tagged so they never
 * equal an array.
 * @param {*} x A structured element or one of its parts.
 * @returns {*} The JSON value of x.
 */
const pySetKeyValue = (x) => {
  if (typeof x === "string") return "s" + x;
  if (typeof x === "boolean") return +x;
  if (typeof x === "number" && !Number.isFinite(x)) return "n" + x;
  if (Array.isArray(x)) return x.map(pySetKeyValue);
  if (x !== null && typeof x === "object") {
    return ["o", Object.entries(x).map(([k, v]) => [k, pySetKeyValue(v)])];
  }
  return x;
};

/**
 * Key a set element by value, so structured elements (tuples, dataclasses)
 * compare the way Python compares them rather than by object identity.
 * Numbers and null are their own key, booleans are keyed as the numbers
 * they equal in Python (True == 1, False == 0), also inside structured
 * elements, and strings and structured elements get distinct prefixes so a
 * string can never share a key with an element's JSON.
 * @param {*} x The set element.
 * @returns {*} The key of the element.
 */
export const pySetKey = (x) => {
  if (typeof x === "string") return "s" + x;
  if (typeof x === "boolean") return +x;
  if (x !== null && typeof x === "object") {
    return "o" + JSON.stringify(pySetKeyValue(x));
  }
  return x;
};

/**
 * Check whether a set (as an array) contains an element.
 * @param {Array|null|undefined} arr The set.
 * @param {*} x The element to look for.
 * @returns {boolean} Whether the set contains the element.
 */
export const pySetHas = (arr, x) => {
  if (arr == null) return false;
  const key = pySetKey(x);
  // SameValueZero, as Set.has uses: NaN matches NaN, without copying arr.
  const isNaNKey = Number.isNaN(key);
  return arr.some((y) => {
    const other = pySetKey(y);
    return other === key || (isNaNKey && Number.isNaN(other));
  });
};

/**
 * The elements of either set, keeping the order of a then b.
 * @param {Array|null|undefined} a The first set.
 * @param {Array|null|undefined} b The second set.
 * @returns {Array} The union.
 */
export const pySetUnion = (a, b) => {
  const result = a == null ? [] : [...a];
  const seen = new Set(result.map(pySetKey));
  for (const x of b ?? []) {
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
 * @param {Array|null|undefined} a The first set.
 * @param {Array|null|undefined} b The second set.
 * @returns {Array} The intersection.
 */
export const pySetIntersection = (a, b) => {
  if (a == null || b == null) return [];
  const keys = new Set(b.map(pySetKey));
  return a.filter((x) => keys.has(pySetKey(x)));
};

/**
 * The elements of a that are not in b.
 * @param {Array|null|undefined} a The first set.
 * @param {Array|null|undefined} b The second set.
 * @returns {Array} The difference.
 */
export const pySetDifference = (a, b) => {
  if (a == null) return [];
  if (b == null) return [...a];
  const keys = new Set(b.map(pySetKey));
  return a.filter((x) => !keys.has(pySetKey(x)));
};

/**
 * The elements in exactly one of a and b, without duplicates even when an
 * operand is a plain array that holds some.
 * @param {Array|null|undefined} a The first set.
 * @param {Array|null|undefined} b The second set.
 * @returns {Array} The symmetric difference.
 */
export const pySetSymmetricDifference = (a, b) =>
  pySetUnion(pySetDifference(a, b), pySetDifference(b, a));

/**
 * Whether every element of a is in b.
 * @param {Array|null|undefined} a The first set.
 * @param {Array|null|undefined} b The second set.
 * @returns {boolean} Whether a is a subset of b.
 */
export const pySetIsSubset = (a, b) => {
  if (a == null) return true;
  if (b == null) return a.length === 0;
  const keys = new Set(b.map(pySetKey));
  return a.every((x) => keys.has(pySetKey(x)));
};

/**
 * Whether a and b have no element in common.
 * @param {Array|null|undefined} a The first set.
 * @param {Array|null|undefined} b The second set.
 * @returns {boolean} Whether the sets are disjoint.
 */
export const pySetIsDisjoint = (a, b) => {
  if (a == null || b == null) return true;
  const keys = new Set(b.map(pySetKey));
  return !a.some((x) => keys.has(pySetKey(x)));
};

/**
 * The match subject in the form of the first set case it equals, so the
 * `JSON.stringify` comparison of `rx.match` treats a set case as Python's `==`
 * does, whatever order the subject's elements arrive in. Any other subject,
 * including an array with repeated elements, is returned as is.
 * @param {*} x The match subject.
 * @param {Array} cases The set cases, each an array or null.
 * @returns {*} The set case equal to x, or x.
 */
export const pySetMatch = (x, cases) => {
  if (!Array.isArray(x)) return x;
  const keys = new Set(x.map(pySetKey));
  if (keys.size !== x.length) return x;
  return (
    cases.find((c) => {
      if (c == null) return false;
      const other = new Set(c.map(pySetKey));
      return other.size === keys.size && [...other].every((k) => keys.has(k));
    }) ?? x
  );
};
