import path from "node:path";
import { transformAsync } from "@babel/core";
import reactCompiler from "babel-plugin-react-compiler";

// Generated components call Emotion's `jsx(type, props, ...children)` instead of
// using JSX syntax. Describe it the way the compiler treats JSX: arguments are
// frozen and the result is an immutable element, so elements cache per input.
const FREEZE_JSX_ARGUMENT = (value) => ({
  kind: "Freeze",
  value,
  reason: "jsx-captured",
});
const EMOTION_JSX_TYPE = {
  kind: "function",
  positionalParams: ["freeze", "freeze"],
  restParam: "freeze",
  calleeEffect: "read",
  returnType: { kind: "type", name: "Any" },
  returnValueKind: "frozen",
  aliasing: {
    receiver: "@receiver",
    params: ["@type", "@props"],
    rest: "@rest",
    returns: "@return",
    temporaries: [],
    effects: [
      FREEZE_JSX_ARGUMENT("@type"),
      FREEZE_JSX_ARGUMENT("@props"),
      FREEZE_JSX_ARGUMENT("@rest"),
      {
        kind: "Create",
        into: "@return",
        value: "frozen",
        reason: "jsx-captured",
      },
    ],
  },
};

/**
 * Describe imported modules whose behavior the compiler cannot infer.
 * @param moduleName The imported module specifier.
 * @returns The module type, or null to use the compiler's defaults.
 */
const moduleTypeProvider = (moduleName) =>
  moduleName === "@emotion/react"
    ? { kind: "object", properties: { jsx: EMOTION_JSX_TYPE } }
    : null;

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
              // Outlining hoists capture-free callbacks such as generated
              // `(...args) => addEvents(...)` handlers, which the compiler
              // cannot lower; keep them inline so their components compile.
              environment: {
                enableFunctionOutlining: false,
                moduleTypeProvider,
              },
            },
          ],
        ],
      });
      return result && { code: result.code, map: result.map };
    },
  };
}
