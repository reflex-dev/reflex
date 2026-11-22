/* Print the call signatures of the exports of JavaScript modules, as JSON, for
 * the Python type stubs Reflex writes next to modules an app imports from
 * Python. Types come from TypeScript annotations or, in a .js file, JSDoc.
 *
 * Arguments reach the browser as JSON, so each parameter's type is classified
 * here into the JSON value Python can send for it ("any" for a type JSON has
 * no form of, such as a function, a `Map` or an `HTMLElement`):
 *
 *   type = "any" | "str" | "float" | "bool" | "None"
 *        | {kind: "literal", value: string | integer | boolean}
 *        | {kind: "list", item: type}
 *        | {kind: "mapping", value: type}      (string keys)
 *        | {kind: "union", members: type[]}    (two or more, sorted)
 *
 * Usage: node script-signatures.js <module>...
 * Run from the app's .web directory, where typescript is installed. Prints:
 *
 *   {
 *     "modules": {"<module>": {"<export>": [{"parameters": [
 *       {"name": string, "type": type, "optional": boolean, "rest": boolean}
 *     ]}, ...]}},                one signature per overload; none if it has
 *                                no known call signature
 *     "files": [file, ...]       the files the types were read from, other than
 *                                TypeScript's libraries and installed packages
 *   } */

import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(import.meta.url);
const ts = require("typescript");

const web = process.cwd();
const files = process.argv.slice(2);
const program = ts.createProgram(files, {
  allowJs: true,
  noEmit: true,
  skipLibCheck: true,
  // Keep `null` and `undefined` in the types, for `None` in Python.
  strictNullChecks: true,
  target: ts.ScriptTarget.ES2022,
  module: ts.ModuleKind.ESNext,
  moduleResolution: ts.ModuleResolutionKind.Bundler,
  // Resolve `$/...` and npm packages as the app's bundler does, so imported
  // types are known; a module outside .web finds no node_modules of its own.
  baseUrl: web,
  paths: {
    "$/*": [join(web, "*")],
    "*": [
      join(web, "node_modules", "@types", "*"),
      join(web, "node_modules", "*"),
    ],
  },
});
const checker = program.getTypeChecker();

/** @typedef {string | {kind: string, [key: string]: any}} JsonType */

const BOOLEAN_LITERALS = [true, false].map((value) =>
  JSON.stringify({ kind: "literal", value }),
);

/**
 * Combine types into their union, in an order that does not depend on the
 * order the checker happened to create them in.
 * @param {JsonType[]} types The types.
 * @returns {JsonType} The union; "any" if a member is, or if there is none.
 */
const union = (types) => {
  if (types.includes("any")) return "any";
  const members = new Map(types.map((type) => [JSON.stringify(type), type]));
  if (BOOLEAN_LITERALS.every((key) => members.has(key))) {
    for (const key of BOOLEAN_LITERALS) members.delete(key);
    members.set(JSON.stringify("bool"), "bool");
  }
  const sorted = [...members.keys()].sort().map((key) => members.get(key));
  if (sorted.length < 2) return sorted[0] ?? "any";
  return { kind: "union", members: sorted };
};

/**
 * Whether an object type has no JSON form: a function, a class instance, or an
 * interface TypeScript's libraries or an npm package declare, such as `Map`,
 * `Promise` or `HTMLElement`.
 * @param {any} type The type.
 * @returns {boolean} Whether it is.
 */
const isOpaque = (type) => {
  if (
    type.getCallSignatures().length > 0 ||
    type.getConstructSignatures().length > 0
  ) {
    return true;
  }
  // Every object type has a symbol: `__type` for a type literal.
  const symbol = type.getSymbol();
  if (symbol.flags & ts.SymbolFlags.Class) return true;
  return (
    Boolean(symbol.flags & ts.SymbolFlags.Interface) &&
    symbol.declarations.some((declaration) => {
      const file = declaration.getSourceFile();
      return (
        program.isSourceFileDefaultLibrary(file) ||
        program.isSourceFileFromExternalLibrary(file)
      );
    })
  );
};

// The object types being classified, outermost first. A type that contains
// itself, such as `interface Tree { [key: string]: Tree }`, has no finite JSON
// shape: its repeat is classified as any.
const classifying = new Set();

/**
 * Classify an object type: an array or tuple is a list, a string-keyed record
 * a mapping of its values, and another plain object a mapping.
 * @param {any} type The type.
 * @returns {JsonType} Its JSON type.
 */
const classifyObject = (type) => {
  if (classifying.has(type)) return "any";
  classifying.add(type);
  try {
    return classifyShape(type);
  } finally {
    classifying.delete(type);
  }
};

/**
 * Classify an object type that is not already being classified.
 * @param {any} type The type.
 * @returns {JsonType} Its JSON type.
 */
const classifyShape = (type) => {
  if (checker.isArrayType(type)) {
    return { kind: "list", item: classify(checker.getTypeArguments(type)[0]) };
  }
  if (checker.isTupleType(type)) {
    const items = checker.getTypeArguments(type).map(classify);
    return { kind: "list", item: union(items) };
  }
  const index = checker.getIndexInfoOfType(type, ts.IndexKind.String);
  if (index) return { kind: "mapping", value: classify(index.type) };
  return isOpaque(type) ? "any" : { kind: "mapping", value: "any" };
};

/**
 * Classify a type into the JSON value Python can send for it. An enum is the
 * union of its members' values.
 * @param {any} type The type.
 * @returns {JsonType} Its JSON type.
 */
const classify = (type) => {
  const flags = type.flags;
  if (type.isUnion()) return union(type.types.map(classify));
  if (type.isStringLiteral()) return { kind: "literal", value: type.value };
  if (type.isNumberLiteral()) {
    // Python's `Literal` takes integers, not other numbers.
    return Number.isSafeInteger(type.value)
      ? { kind: "literal", value: type.value }
      : "float";
  }
  if (flags & ts.TypeFlags.BooleanLiteral) {
    return { kind: "literal", value: type === checker.getTrueType() };
  }
  if (flags & ts.TypeFlags.StringLike) return "str";
  // `boolean` needs no case: it is the union `true | false`, which `union`
  // makes "bool".
  if (flags & ts.TypeFlags.NumberLike) return "float";
  if (
    flags &
    (ts.TypeFlags.Null | ts.TypeFlags.Undefined | ts.TypeFlags.Void)
  ) {
    return "None";
  }
  if (flags & ts.TypeFlags.Object) return classifyObject(type);
  // `any`, `unknown`, `object`, `bigint`, symbols, intersections, generics.
  return "any";
};

/**
 * Describe one parameter of a signature.
 * @param {any} parameter The parameter symbol.
 * @param {any} location The node to resolve its type at.
 * @returns {{name: string, type: JsonType, optional: boolean, rest: boolean}} The parameter.
 */
const describeParameter = (parameter, location) => {
  const declaration = parameter.valueDeclaration;
  const rest = Boolean(declaration?.dotDotDotToken);
  const optional = Boolean(
    declaration &&
      (declaration.questionToken ||
        declaration.initializer ||
        checker.isOptionalParameter(declaration)),
  );
  /** @type {any} */
  const type = checker.getTypeOfSymbolAtLocation(parameter, location);
  let described;
  if (rest) {
    // A rest parameter's element type; a tuple's elements have no single type.
    described = checker.isArrayType(type)
      ? classify(checker.getTypeArguments(type)[0])
      : "any";
  } else if (optional && type.isUnion()) {
    // The checker adds `undefined` to an optional parameter's type; Python
    // leaves the argument out instead.
    const defined = type.types.filter(
      (member) => !(member.flags & ts.TypeFlags.Undefined),
    );
    described = union(defined.map(classify));
  } else {
    described = classify(type);
  }
  return { name: parameter.getName(), type: described, optional, rest };
};

/** @type {Record<string, Record<string, any[]>>} */
const modules = {};
for (const file of files) {
  const source = program.getSourceFile(file);
  const moduleSymbol = checker.getSymbolAtLocation(source);
  modules[file] = Object.fromEntries(
    (moduleSymbol ? checker.getExportsOfModule(moduleSymbol) : []).map(
      (symbol) => [
        symbol.getName(),
        checker
          .getTypeOfSymbolAtLocation(symbol, source)
          .getCallSignatures()
          .map((signature) => ({
            parameters: signature
              .getParameters()
              .map((parameter) => describeParameter(parameter, source)),
          })),
      ],
    ),
  );
}
const read = program
  .getSourceFiles()
  .filter(
    (source) =>
      !program.isSourceFileDefaultLibrary(source) &&
      !source.fileName.includes("/node_modules/"),
  )
  .map((source) => source.fileName);
process.stdout.write(JSON.stringify({ modules, files: read }));
