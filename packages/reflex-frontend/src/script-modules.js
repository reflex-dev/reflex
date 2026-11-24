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
 *     "imports": {"<file>": [specifier, ...]},  per script or stylesheet,
 *                                               what it imports other than
 *                                               local files
 *     "errors": [{"file", "line", "column", "message"}]  the first syntax
 *                                                        error of each file
 *   }
 *
 * Files are absolute paths, each by the path its import names, without
 * following links, as Vite resolves them with `resolve.preserveSymlinks`. A
 * file that Vite loads as it is, such as with `?raw`, is listed but not read. An
 * export the syntax alone cannot classify, such as
 * `export const f = make()` or one re-exported from another file, is listed as
 * a function, so that a valid call is never rejected. */

import { readFileSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, extname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

// rolldown is a dependency of vite, which every app installs; resolved through
// vite so that it is found however the package manager lays out node_modules.
const vite = createRequire(join(process.cwd(), "package.json")).resolve("vite");
/** @type {typeof import("rolldown/utils")} */
const { parseSync, Visitor } = await import(
  pathToFileURL(createRequire(vite).resolve("rolldown/utils")).href
);

// Files that are parsed; other local files, such as images, are only listed.
const SCRIPT_EXTENSIONS = new Set([
  ".js",
  ".jsx",
  ".ts",
  ".tsx",
  ".mjs",
  ".mts",
]);
// Tried in order for an import without an extension: Vite's default
// `resolve.extensions`, which the app's config keeps.
const RESOLVE_EXTENSIONS = [
  ".mjs",
  ".js",
  ".mts",
  ".ts",
  ".jsx",
  ".tsx",
  ".json",
];
// The TypeScript files an import may name by the JavaScript file each compiles
// to, by that file's extension, tried in order, as TypeScript and Vite do.
const TYPESCRIPT_SOURCES = {
  ".js": [".ts", ".tsx"],
  ".jsx": [".tsx"],
  ".mjs": [".mts"],
};
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
 * Whether Vite loads the file an import names as it is, so that it is listed
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
  const extension = extname(target);
  const base = target.slice(0, target.length - extension.length);
  return [
    target,
    ...(TYPESCRIPT_SOURCES[extension] ?? []).map((ext) => base + ext),
    ...RESOLVE_EXTENSIONS.map((ext) => target + ext),
    ...RESOLVE_EXTENSIONS.map((ext) => join(target, `index${ext}`)),
  ].find(isFile);
};

/**
 * @param {any} node An expression.
 * @returns {string | undefined} Its value, if it is a string written out.
 */
const stringValue = (node) => {
  if (node?.type === "Literal" && typeof node.value === "string") {
    return node.value;
  }
  if (node?.type === "TemplateLiteral" && !node.expressions.length) {
    return node.quasis[0].value.cooked;
  }
};

/**
 * Find the path of a `new URL(path, import.meta.url)`, which Vite resolves
 * from the module.
 * @param {any} node An expression.
 * @returns {string | undefined} The path, if it is such a URL.
 */
const moduleUrl = (node) => {
  if (
    node?.type !== "NewExpression" ||
    node.callee.type !== "Identifier" ||
    node.callee.name !== "URL"
  ) {
    return;
  }
  const [path, base] = node.arguments;
  if (
    base?.type === "MemberExpression" &&
    !base.computed &&
    base.property.name === "url" &&
    base.object.type === "MetaProperty" &&
    base.object.meta.name === "import"
  ) {
    return stringValue(path);
  }
};

const WORKERS = new Set(["Worker", "SharedWorker"]);

/**
 * Find the specifiers of the modules a script loads at runtime, and the paths
 * it names by URL. The modules are those of static imports and re-exports that
 * are not type-only, and of dynamic imports of a string. A path named by
 * `new URL(path, import.meta.url)` is bundled when it starts a worker, and
 * otherwise loaded as it is.
 * @param {any} program The script's AST.
 * @param {any} module The script's imports and exports, as the parser lists them.
 * @returns {{specifiers: string[], urls: Map<string, boolean>}} The
 * specifiers, without duplicates, and each path named by URL, with whether it
 * starts a worker.
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
  const urls = new Map();
  new Visitor({
    ImportExpression({ source }) {
      const specifier = stringValue(source);
      if (specifier !== undefined) specifiers.add(specifier);
    },
    NewExpression(node) {
      const { callee } = node;
      if (callee.type === "Identifier" && WORKERS.has(callee.name)) {
        const path = moduleUrl(node.arguments[0]);
        if (path !== undefined) urls.set(path, true);
      }
      const path = moduleUrl(node);
      if (path !== undefined && !urls.has(path)) urls.set(path, false);
    },
  }).visit(program);
  return { specifiers: [...specifiers], urls };
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
  const { specifiers, urls } = readImports(program, module);
  const script = {
    references: [
      ...specifiers
        .filter((specifier) => specifier.startsWith("."))
        .flatMap((specifier) => {
          const reference = resolveImport(dirname(file), specifier);
          return reference
            ? [{ file: reference, read: !loadedAsIs(specifier) }]
            : [];
        }),
      // A URL names its file exactly, without the extensions an import may omit.
      ...[...urls]
        .filter(([path]) => path.startsWith("."))
        .map(([path, worker]) => ({
          file: resolve(dirname(file), stripQuery(path)),
          read: worker,
        }))
        .filter(({ file }) => isFile(file)),
    ],
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
 * Find the local files a stylesheet references with `@import` and `url(...)`,
 * and the packages it imports. Absolute paths, URLs, data URIs and fragments
 * are neither. Vite resolves an `@import` from the stylesheet first, so a bare
 * name with no file beside it, such as `normalize.css`, names a package.
 * @param {string} file The stylesheet.
 * @returns {{references: Reference[], imports: string[]}} The files and packages.
 */
const readStylesheet = (file) => {
  const references = [];
  const imports = [];
  const source = readFileSync(file, "utf-8").replace(CSS_COMMENT, "");
  for (const match of source.matchAll(CSS_REFERENCE)) {
    const reference = match[1] ?? match[2] ?? match[3];
    if (/^(?:[/#]|data:)|:\/\//.test(reference)) continue;
    const path = resolve(dirname(file), stripQuery(reference));
    if (isFile(path)) {
      references.push({ file: path, read: true });
    } else if (match[0].startsWith("@import") && !reference.startsWith(".")) {
      imports.push(reference);
    }
  }
  return { references, imports };
};

/**
 * Read a local file.
 * @param {string} file The file.
 * @returns {any} What it references, what a script or stylesheet imports, and
 * what a script exports.
 */
const readFile = (file) => {
  const extension = extname(file);
  if (SCRIPT_EXTENSIONS.has(extension)) return readScript(file);
  if (extension === ".css") return readStylesheet(file);
  return { references: [] };
};

/** @type {Map<string, any>} Each file read, by path. */
const files = new Map();

/**
 * Find a module and every local file it reaches, reading each file once.
 * @param {string} module The module.
 * @returns {string[]} The files, the module first.
 */
const reach = (module) => {
  const read = new Set([module]);
  const reached = new Set([module]);
  for (const file of read) {
    if (!files.has(file)) files.set(file, readFile(file));
    for (const reference of files.get(file).references) {
      if (reference.read) read.add(reference.file);
      reached.add(reference.file);
    }
  }
  return [...reached];
};

const modules = {};
for (const module of process.argv.slice(2)) {
  modules[module] = { files: reach(module), ...files.get(module).exports };
}
const imports = {};
const errors = [];
for (const [file, { imports: specifiers, error }] of files) {
  if (specifiers) imports[file] = specifiers;
  if (error) errors.push(error);
}
process.stdout.write(JSON.stringify({ format: 1, modules, imports, errors }));
