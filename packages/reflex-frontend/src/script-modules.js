/* Read the JavaScript modules an app imports from Python, for the compiler.
 * The files are parsed by the parser of the app's bundler, rolldown's, so every
 * syntax the bundler reads (JavaScript, TypeScript, JSX) is read here too.
 *
 * Usage: node script-modules.js <module>...
 * Run from the app's .web directory, where vite is installed. Prints:
 *
 *   {
 *     "format": 1,                 the version of this shape, which the
 *                                  compiler checks: change it with the shape
 *     "modules": {"<module>": {
 *       "files": [file, ...],      the module and every local file it reaches
 *       "functions": [name, ...],  exports Python can call
 *       "values": [name, ...],     exports that are not functions
 *       "exportsAll": boolean      whether `export * from` adds unknown names
 *     }},
 *     "imports": {"<file>": [specifier, ...]},  per script, what it imports
 *                                               other than relative paths
 *     "errors": [{"file", "line", "column", "message"}]  the first syntax
 *                                                        error of each file
 *     "loops": [{"importer", "file", "link"}]  each import of a file that
 *                                              reaches itself again, one
 *                                              directory link deeper
 *   }
 *
 * Files are absolute paths: the module's real path, and each file it reaches
 * by the path its import names, so that the copy of a link is where the import
 * looks for it and the files the link imports are found beside it. A file
 * that Vite loads as it is, such as with `?raw`, is listed but not read. An
 * export the syntax alone cannot classify, such as
 * `export const f = make()` or one re-exported from another file, is listed as
 * a function, so that a valid call is never rejected. */

import { lstatSync, readFileSync, realpathSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, extname, join, relative, resolve, sep } from "node:path";
import { pathToFileURL } from "node:url";

// rolldown is a dependency of vite, which every app installs; resolved through
// vite so that it is found however the package manager lays out node_modules.
const vite = createRequire(join(process.cwd(), "package.json")).resolve("vite");
/** @type {typeof import("rolldown/utils")} */
const { parseSync, Visitor } = await import(
  pathToFileURL(createRequire(vite).resolve("rolldown/utils")).href
);

// Files that are parsed; other local files, such as images, are only copied.
const SCRIPT_EXTENSIONS = new Set([".js", ".jsx", ".ts", ".tsx", ".mjs"]);
// Tried in order for an import without an extension, as the bundler does.
const RESOLVE_EXTENSIONS = [".ts", ".tsx", ".js", ".jsx", ".mjs"];
// Initializers of a `const` that make it a value Python cannot call.
const VALUE_TYPES = new Set([
  "ArrayExpression",
  "ClassExpression",
  "Literal",
  "ObjectExpression",
  "TemplateLiteral",
]);
// Expressions that wrap an initializer without changing what it is.
const WRAPPER_TYPES = new Set([
  "ParenthesizedExpression",
  "TSAsExpression",
  "TSSatisfiesExpression",
]);
const CSS_COMMENT = /\/\*[\s\S]*?\*\//g;
// The path of an `@import` or a `url()`, quoted or bare, and each quoted path
// of an `image-set()`. A quoted path may hold spaces.
const CSS_REFERENCE =
  /(?:@import\s+(?:url\(\s*)?|url\(\s*|(?<=image-set\([^)]*))(?:"([^"]*)"|'([^']*)')|(?:@import\s+(?:url\(\s*)?|url\(\s*)([^"'\s);]+)/g;

/**
 * Remove the query and fragment of a path, as in Vite's `./logo.png?url`.
 * @param {string} path The path.
 * @returns {string} The file's path.
 */
const stripQuery = (path) => path.replace(/[?#].*/s, "");

const RAW_QUERY = /[?&]raw(?:&|$)/;
const URL_QUERY = /[?&]url(?:&|$)/;
const WORKER_QUERY = /[?&](?:shared)?worker(?:&|$)/;

/**
 * Whether Vite loads the file an import names as it is, so that it is copied
 * but not read: `?raw` loads its text, and `?url` the URL of a script that is
 * not a worker. A stylesheet loaded by URL is still bundled.
 * @param {string} specifier The import's specifier.
 * @returns {boolean} Whether the file is loaded as it is.
 */
const loadedAsIs = (specifier) => {
  const query = /\?[^#]*/.exec(specifier)?.[0] ?? "";
  return (
    RAW_QUERY.test(query) ||
    (URL_QUERY.test(query) &&
      !WORKER_QUERY.test(query) &&
      extname(stripQuery(specifier)) !== ".css")
  );
};

/**
 * @param {string} path A path.
 * @returns {boolean} Whether it is a file.
 */
const isFile = (path) =>
  Boolean(statSync(path, { throwIfNoEntry: false })?.isFile());

/**
 * Find the file a relative import names, as the bundler would.
 * @param {string} directory The importing file's directory.
 * @param {string} specifier The specifier, such as `./helpers` or `./x.js`.
 * @returns {string | undefined} The file, if there is one.
 */
const resolveImport = (directory, specifier) => {
  const target = resolve(directory, stripQuery(specifier));
  const candidates = [target, ...RESOLVE_EXTENSIONS.map((ext) => target + ext)];
  if (target.endsWith(".js")) {
    // TypeScript imports a .ts file by the .js name it compiles to.
    candidates.push(`${target.slice(0, -3)}.ts`);
  }
  candidates.push(
    ...RESOLVE_EXTENSIONS.map((ext) => join(target, `index${ext}`)),
  );
  return candidates.find(isFile);
};

/**
 * Find the specifiers of the modules a script loads at runtime: static
 * imports and re-exports that are not type-only, and dynamic imports of a
 * string.
 * @param {any} program The script's AST.
 * @param {any} module The script's imports and exports, as the parser lists them.
 * @returns {string[]} The specifiers, without duplicates.
 */
const readImports = (program, module) => {
  const specifiers = new Set();
  for (const { moduleRequest, entries } of module.staticImports) {
    if (entries.length === 0 || entries.some((entry) => !entry.isType)) {
      specifiers.add(moduleRequest.value);
    }
  }
  for (const { entries } of module.staticExports) {
    for (const { moduleRequest, isType } of entries) {
      if (moduleRequest && !isType) specifiers.add(moduleRequest.value);
    }
  }
  new Visitor({
    ImportExpression({ source }) {
      if (source.type === "Literal" && typeof source.value === "string") {
        specifiers.add(source.value);
      } else if (
        source.type === "TemplateLiteral" &&
        !source.expressions.length
      ) {
        specifiers.add(source.quasis[0].value.cooked);
      }
    },
  }).visit(program);
  return [...specifiers];
};

/**
 * Find the top-level bindings that are not functions: a class, an enum, or a
 * `const` initialized with a literal, an object, an array or a class.
 * @param {any} program The script's AST.
 * @returns {Set<string>} Their names.
 */
const valueBindings = (program) => {
  const values = new Set();
  for (const statement of program.body) {
    const declaration =
      statement.type === "ExportNamedDeclaration"
        ? statement.declaration
        : statement;
    if (
      declaration?.type === "ClassDeclaration" ||
      declaration?.type === "TSEnumDeclaration"
    ) {
      values.add(declaration.id.name);
    } else if (
      declaration?.type === "VariableDeclaration" &&
      declaration.kind === "const"
    ) {
      for (let { id, init } of declaration.declarations) {
        while (WRAPPER_TYPES.has(init?.type)) init = init.expression;
        if (VALUE_TYPES.has(init?.type)) values.add(id.name);
      }
    }
  }
  return values;
};

/**
 * Classify the named exports of a script, without types and the default export.
 * @param {any} program The script's AST.
 * @param {any} module The script's imports and exports, as the parser lists them.
 * @returns {{functions: string[], values: string[], exportsAll: boolean}} The exports.
 */
const readExports = (program, module) => {
  const bindings = valueBindings(program);
  const functions = new Set();
  const values = new Set();
  let exportsAll = false;
  for (const { entries } of module.staticExports) {
    for (const entry of entries) {
      const { exportName, moduleRequest } = entry;
      if (entry.isType || exportName.kind === "Default") continue;
      if (exportName.kind === "None") {
        exportsAll = true;
      } else if (
        moduleRequest
          ? entry.importName.kind === "All"
          : bindings.has(entry.localName.name)
      ) {
        values.add(exportName.name);
      } else {
        functions.add(exportName.name);
      }
    }
  }
  return { functions: [...functions], values: [...values], exportsAll };
};

/**
 * @typedef {{file: string, read: boolean}} Reference A local file a file
 * references, and whether it is read for its own references.
 */

/**
 * Parse a script.
 * @param {string} file The script.
 * @returns {any} Its local references, imports and exports, and its first
 * syntax error, if it has one.
 */
const readScript = (file) => {
  const source = readFileSync(file, "utf-8");
  const { program, module, errors } = parseSync(file, source);
  const specifiers = readImports(program, module);
  const script = {
    references: specifiers
      .filter((specifier) => specifier.startsWith("."))
      .flatMap((specifier) => {
        const reference = resolveImport(dirname(file), specifier);
        return reference
          ? [{ file: reference, read: !loadedAsIs(specifier) }]
          : [];
      }),
    imports: specifiers.filter((specifier) => !specifier.startsWith(".")),
    exports: readExports(program, module),
    error: undefined,
  };
  if (errors.length) {
    const lines = source.slice(0, errors[0].labels[0].start).split("\n");
    script.error = {
      file,
      line: lines.length,
      column: lines[lines.length - 1].length + 1,
      message: errors[0].message,
    };
  }
  return script;
};

/**
 * Find the local files a stylesheet references with `@import` and `url(...)`.
 * Absolute paths, URLs, data URIs and fragments are not local files.
 * @param {string} file The stylesheet.
 * @returns {{references: Reference[]}} The files.
 */
const readStylesheet = (file) => ({
  references: [
    ...readFileSync(file, "utf-8")
      .replace(CSS_COMMENT, "")
      .matchAll(CSS_REFERENCE),
  ]
    .map((match) => match[1] ?? match[2] ?? match[3])
    .filter((reference) => !/^(?:[/#]|data:)|:\/\//.test(reference))
    .map((reference) => resolve(dirname(file), stripQuery(reference)))
    .filter(isFile)
    .map((reference) => ({ file: reference, read: true })),
});

/**
 * Read a local file.
 * @param {string} file The file.
 * @returns {any} What it references, and for a script, what it imports and exports.
 */
const readFile = (file) => {
  const extension = extname(file);
  if (SCRIPT_EXTENSIONS.has(extension)) return readScript(file);
  if (extension === ".css") return readStylesheet(file);
  return { references: [] };
};

/** @type {Map<string, any>} Each file read, by path. */
const files = new Map();

/** @type {{importer: string, file: string, link: string}[]} */
const loops = [];

/**
 * Find the link a directory reaches another through.
 * @param {string} from The directory.
 * @param {string} to A directory below it, by a path through a link.
 * @returns {string} The first link on the path.
 */
const findLink = (from, to) => {
  let path = from;
  for (const part of relative(from, to).split(sep)) {
    path = join(path, part);
    if (lstatSync(path).isSymbolicLink()) break;
  }
  return path;
};

/**
 * @typedef {{file: string, real: string, importer?: Read}} Read A file read,
 * its real path, and the file whose import first reached it.
 */

/**
 * Find where the import chain of a file reached it before, from a directory
 * that its directory is below through a link. From there the chain repeats one
 * link deeper, without end.
 * @param {Read} importer The file that imports it.
 * @param {string} file The file, by the path its import names.
 * @param {string} real Its real path.
 * @returns {string | undefined} The earlier directory, if there is one.
 */
const findRepeat = (importer, file, real) => {
  const directory = dirname(file);
  for (let earlier = importer; earlier; earlier = earlier.importer) {
    const from = dirname(earlier.file);
    if (
      earlier.real === real &&
      directory.startsWith(from + sep) &&
      realpathSync(directory) === realpathSync(from)
    ) {
      return from;
    }
  }
};

/**
 * Find a module and every local file it reaches, reading each file once. A
 * file that reaches itself again through a directory link is added to `loops`
 * and not followed: the copies are files, so they cannot hold every repeat.
 * @param {string} module The module.
 * @returns {string[]} The files, the module first.
 */
const reach = (module) => {
  const first = realpathSync(module);
  /** @type {Map<string, Read>} */
  const read = new Map([[first, { file: first, real: first }]]);
  const reached = new Set([first]);
  for (const importer of read.values()) {
    const { file } = importer;
    if (!files.has(file)) files.set(file, readFile(file));
    for (const reference of files.get(file).references) {
      if (reference.read && !read.has(reference.file)) {
        const real = realpathSync(reference.file);
        const from = findRepeat(importer, reference.file, real);
        if (from) {
          const link = findLink(from, dirname(reference.file));
          loops.push({ importer: file, file: reference.file, link });
          continue;
        }
        read.set(reference.file, { file: reference.file, real, importer });
      }
      reached.add(reference.file);
    }
  }
  return [...reached];
};

const modules = {};
for (const module of process.argv.slice(2)) {
  const reached = reach(module);
  modules[module] = { files: reached, ...files.get(reached[0]).exports };
}
const imports = {};
const errors = [];
for (const [file, { imports: specifiers, error }] of files) {
  if (specifiers) imports[file] = specifiers;
  if (error) errors.push(error);
}
process.stdout.write(
  JSON.stringify({ format: 1, modules, imports, errors, loops }),
);
