import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { readFile, rename, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";

const SCHEMA_VERSION = 1;
const SHIKI_VERSION = "3.3.0";
const [manifestPath, cachePath, webDir] = process.argv.slice(2);
if (!manifestPath || !cachePath || !webDir) {
  throw new Error(
    "Expected manifest, cache, and frontend directory arguments.",
  );
}

function sortedValue(value) {
  if (Array.isArray(value)) return value.map(sortedValue);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, sortedValue(value[key])]),
    );
  }
  return value;
}

function requestKey(request) {
  return createHash("sha256")
    .update(JSON.stringify(sortedValue(request)), "utf8")
    .digest("hex");
}

function validateRequest(key, request) {
  if (
    request === null ||
    typeof request !== "object" ||
    Array.isArray(request) ||
    Object.keys(request).sort().join(",") !== "code,language,themes" ||
    typeof request.code !== "string" ||
    typeof request.language !== "string" ||
    request.themes === null ||
    typeof request.themes !== "object" ||
    Array.isArray(request.themes) ||
    Object.keys(request.themes).sort().join(",") !== "dark,light" ||
    typeof request.themes.dark !== "string" ||
    typeof request.themes.light !== "string"
  ) {
    throw new Error(`Static Shiki request ${key} has an invalid shape.`);
  }
  if (requestKey(request) !== key) {
    throw new Error(`Static Shiki request ${key} does not match its hash.`);
  }
}

const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
if (
  manifest === null ||
  typeof manifest !== "object" ||
  Array.isArray(manifest) ||
  manifest.schema_version !== SCHEMA_VERSION ||
  manifest.shiki_version !== SHIKI_VERSION ||
  manifest.requests === null ||
  typeof manifest.requests !== "object" ||
  Array.isArray(manifest.requests)
) {
  throw new Error("Static Shiki manifest schema or version is stale.");
}

const require = createRequire(pathToFileURL(join(webDir, "package.json")));
const shikiEntry = require.resolve("shiki");
const shikiPackage = JSON.parse(
  await readFile(join(dirname(shikiEntry), "..", "package.json"), "utf8"),
);
if (shikiPackage.version !== SHIKI_VERSION) {
  throw new Error(
    `Static Shiki requires shiki ${SHIKI_VERSION}, found ${shikiPackage.version}.`,
  );
}
const { codeToHtml } = await import(pathToFileURL(shikiEntry));

const requestKeys = Object.keys(manifest.requests).sort();
const entries = {};
for (const key of requestKeys) {
  const request = manifest.requests[key];
  validateRequest(key, request);
  const html = await codeToHtml(request.code, {
    lang: request.language,
    themes: request.themes,
  });
  entries[key] = { request, html };
}
if (Object.keys(entries).sort().join(",") !== requestKeys.join(",")) {
  throw new Error("Static Shiki generated an incomplete request key set.");
}

const cache = {
  schema_version: SCHEMA_VERSION,
  shiki_version: shikiPackage.version,
  entries,
};
const temporaryPath = `${cachePath}.tmp`;
await writeFile(temporaryPath, `${JSON.stringify(cache)}\n`, "utf8");
await rename(temporaryPath, cachePath);
