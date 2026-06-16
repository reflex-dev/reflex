const noVendorPrefix = /^(1|true)$/i.test(process.env.REFLEX_NO_AUTOPREFIXER ?? "");

export default {
  plugins: {
    "postcss-import": {},
    autoprefixer: noVendorPrefix ? false : {},
  },
};
