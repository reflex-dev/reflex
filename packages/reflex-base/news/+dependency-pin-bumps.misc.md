Bumped bundled frontend dependency pins to their current releases:

- `react` / `react-dom`: 19.2.6 → 19.2.7
- `react-router`, `react-router-dom`, `@react-router/node`, `@react-router/dev`, `@react-router/fs-routes`: 7.15.0 → 7.18.0
- `isbot`: 5.1.40 → 5.1.43
- `universal-cookie`: 7.2.2 → 8.1.2
- `postcss`: 8.5.14 → 8.5.15
- `tailwindcss` / `@tailwindcss/postcss`: 4.3.0 → 4.3.1
- `@tailwindcss/typography`: 0.5.19 → 0.5.20
- Bun: 1.3.13 → 1.3.14

Also raised the `rich` upper bound to `<16` (adopting rich 15), and dropped the now-redundant `cookie` `package.json` override — `universal-cookie` 8 and `react-router` both resolve `cookie` to 1.x on their own.
