const noVendorPrefix = /^(1|true|y|yes)$/i.test(
  process.env.REFLEX_NO_AUTOPREFIXER ?? "",
);

export default {
  plugins: {
    "postcss-import": {},
    autoprefixer: noVendorPrefix ? false : {},
  },
};
