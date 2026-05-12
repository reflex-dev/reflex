import { compressDirectory } from "./vite-plugin-compress.js";

const [directory, formatsArg = "[]"] = process.argv.slice(2);

if (!directory) {
  throw new Error("Missing static output directory for compression.");
}

await compressDirectory(directory, JSON.parse(formatsArg));
