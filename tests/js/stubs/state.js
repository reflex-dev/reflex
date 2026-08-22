/**
 * Stand-in for `$/utils/state`, exposing only what the units under test import.
 *
 * The real module reaches for socket.io, react-router, `$/env.json` and the
 * per-app generated `context.js`. `refs` itself is just a bare object there, so
 * a stub is faithful as well as convenient.
 */
export const refs = {};
