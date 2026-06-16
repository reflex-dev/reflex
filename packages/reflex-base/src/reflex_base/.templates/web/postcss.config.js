export default {
  plugins: {
    "postcss-import": {},
    autoprefixer: process.env.REFLEX_NO_AUTOPREFIXER ? false : {},
  },
};
