/* Print the call signatures of the functions JavaScript modules export, as
 * JSON, for the Python type stubs Reflex writes next to modules an app imports
 * from Python. Types come from TypeScript annotations or, in a .js file, JSDoc.
 *
 * Usage: node script-signatures.js <module>...
 * Run from the app's .web directory, which installs typescript when an app
 * imports a module. */

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
  // Keep `null` and `undefined` in the types, for `| None` in Python.
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

/**
 * Describe one parameter of a signature.
 * @param {any} parameter The parameter symbol.
 * @param {any} location The node to resolve its type at.
 * @returns {{name: string, type: string, optional: boolean, rest: boolean}} The parameter.
 */
const describeParameter = (parameter, location) => {
  const declaration = parameter.valueDeclaration;
  const rest = Boolean(declaration?.dotDotDotToken);
  const type = checker.getTypeOfSymbolAtLocation(parameter, location);
  let typeName = checker.typeToString(type);
  if (rest) {
    // A rest parameter's element type; a tuple's elements have no single type.
    typeName = checker.isArrayType(type)
      ? checker.typeToString(
          checker.getTypeArguments(/** @type {any} */ (type))[0],
        )
      : "any";
  }
  return {
    name: parameter.getName(),
    type: typeName,
    optional: Boolean(
      declaration &&
        (declaration.questionToken ||
          declaration.initializer ||
          checker.isOptionalParameter(declaration)),
    ),
    rest,
  };
};

/** @type {Record<string, {name: string, signatures: any[], untyped: boolean}[]>} */
const result = {};
for (const file of files) {
  const source = program.getSourceFile(file);
  const moduleSymbol = source && checker.getSymbolAtLocation(source);
  result[file] = (moduleSymbol ? checker.getExportsOfModule(moduleSymbol) : [])
    .filter((symbol) => symbol.getName() !== "default")
    .map((symbol) => {
      const type = checker.getTypeOfSymbolAtLocation(symbol, source);
      return {
        name: symbol.getName(),
        signatures: type.getCallSignatures().map((signature) => ({
          parameters: signature
            .getParameters()
            .map((parameter) => describeParameter(parameter, source)),
        })),
        // An export of unknown type, such as one from a package without
        // declarations, may still be a function.
        untyped: Boolean(
          type.flags & (ts.TypeFlags.Any | ts.TypeFlags.Unknown),
        ),
      };
    });
}
process.stdout.write(JSON.stringify(result));
