import js from "@eslint/js";
import stylex from "@stylexjs/eslint-plugin";
import globals from "globals";

// `src` holds no React components: the markup of every component comes from
// its Python wrapper. JSX is allowed only where the tests of the behaviour
// hooks mount one.
const NO_JSX = [
  {
    selector: ":matches(JSXElement, JSXFragment)",
    message:
      "No JSX here: the markup of an rx.ui component comes from its Python wrapper. Only tests/behaviors may render JSX.",
  },
];

// A barrel makes every stylesheet behind it part of whatever imports one name
// from it, so a module is imported from the file that defines it.
const NO_BARREL = [
  {
    selector: ":matches(ExportAllDeclaration, ExportNamedDeclaration[source])",
    message:
      "No barrel files: a re-export leaks the CSS of everything it names. Import from the module that defines the name.",
  },
];

// What builds a component without JSX. Hooks are imported by name, so a
// default or namespace import of react has no use here either.
const NO_COMPONENTS = {
  paths: [
    {
      name: "react",
      importNames: [
        "default",
        "createElement",
        "cloneElement",
        "forwardRef",
        "memo",
        "lazy",
        "Component",
        "PureComponent",
      ],
      message:
        "No React components in src: import the hooks you need by name.",
    },
    ...[
      "react-dom",
      "react-dom/client",
      "react/jsx-runtime",
      "react/jsx-dev-runtime",
    ].map((name) => ({
      name,
      message: "No React components in src: nothing here renders.",
    })),
  ],
};

export default [
  js.configs.recommended,
  {
    files: ["**/*.js", "**/*.jsx"],
    languageOptions: {
      // Parsed everywhere, so that JSX is reported by the rule below rather
      // than as a syntax error.
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: globals.node,
    },
    linterOptions: { reportUnusedDisableDirectives: "error" },
    rules: {
      "no-restricted-syntax": ["error", ...NO_JSX],
    },
  },
  {
    // What ships: copied verbatim into an app, where StyleX compiles it.
    files: ["src/**/*.js", "src/**/*.jsx"],
    plugins: { "@stylexjs": stylex },
    languageOptions: { globals: globals.browser },
    // A rule here cannot be switched off from inside the file it rejects.
    linterOptions: { noInlineConfig: true },
    rules: {
      "no-restricted-syntax": ["error", ...NO_JSX, ...NO_BARREL],
      "no-restricted-imports": ["error", NO_COMPONENTS],
      // Left off: `sort-keys` is a style preference, `no-conflicting-props`
      // only reads JSX, which is not allowed here, and
      // `no-lookahead-selectors` is a browser support policy on `:has()`.
      "@stylexjs/enforce-extension": "error",
      "@stylexjs/no-legacy-contextual-styles": "error",
      "@stylexjs/no-nonstandard-styles": "error",
      "@stylexjs/no-unused": "error",
      "@stylexjs/valid-shorthands": "error",
      "@stylexjs/valid-styles": "error",
    },
  },
  {
    // The build files at the top of `src` run in node.
    files: ["src/*.js"],
    languageOptions: { globals: globals.node },
  },
  {
    files: ["tests/behaviors/**"],
    languageOptions: { globals: globals.browser },
    rules: {
      "no-restricted-syntax": "off",
    },
  },
];
