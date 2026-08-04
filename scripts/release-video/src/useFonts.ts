import { useEffect, useState } from "react";
import { continueRender, delayRender } from "remotion";

/**
 * Hold rendering until the brand webfonts are actually rasterised.
 *
 * `document.fonts.ready` alone can resolve before a face has been requested, so
 * every weight/size the video draws with is loaded explicitly first.
 */
const FACES = [
  '400 30px "Instrument Sans Variable"',
  '550 30px "Instrument Sans Variable"',
  '600 72px "Instrument Sans Variable"',
  '400 28px "JetBrains Mono Variable"',
  '500 28px "JetBrains Mono Variable"',
];

export const useFonts = () => {
  const [handle] = useState(() => delayRender("Loading brand fonts"));

  useEffect(() => {
    Promise.all(FACES.map((f) => document.fonts.load(f)))
      .then(() => document.fonts.ready)
      .then(() => continueRender(handle))
      // Never hang the render on a font that failed to resolve.
      .catch(() => continueRender(handle));
  }, [handle]);
};
