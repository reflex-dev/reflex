import path from "node:path";
import { transformAsync } from "@babel/core";
import reactCompiler from "babel-plugin-react-compiler";

/** Compile generated components before React Router applies its transforms. */
export default function reflexReactCompiler() {
  let root;
  return {
    name: "reflex-react-compiler",
    enforce: "pre",
    config() {
      // This import is introduced after Vite scans the uncompiled sources.
      return { optimizeDeps: { include: ["react/compiler-runtime"] } };
    },
    configResolved(config) {
      root = config.root;
    },
    async transform(source, id) {
      if (id.includes("\0")) return null;
      const filename = id.split("?")[0];
      const relative = path.relative(root, filename).split(path.sep).join("/");
      if (
        !/^(?:app|app_components|utils\/components)\/.*\.[cm]?jsx?$/.test(
          relative,
        ) ||
        relative.split("/").includes("node_modules")
      ) {
        return null;
      }
      const result = await transformAsync(source, {
        filename,
        configFile: false,
        babelrc: false,
        sourceMaps: true,
        parserOpts: { plugins: ["jsx"] },
        plugins: [
          [
            reactCompiler,
            {
              target: "19",
              compilationMode: "infer",
              panicThreshold: "none",
            },
          ],
        ],
      });
      return result && { code: result.code, map: result.map };
    },
  };
}
