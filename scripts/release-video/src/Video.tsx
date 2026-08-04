import React from "react";
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame } from "remotion";

import { Backdrop } from "./components/Backdrop";
import { Chrome } from "./components/Chrome";
import { Deploy } from "./scenes/Deploy";
import { Deps } from "./scenes/Deps";
import { Features } from "./scenes/Features";
import { Fixes } from "./scenes/Fixes";
import { Intro } from "./scenes/Intro";
import { Outro } from "./scenes/Outro";
import { Preview } from "./scenes/Preview";
import { useFonts } from "./useFonts";

const SCENES = [
  { id: "intro", Component: Intro, duration: 105, glow: [0.5, 0.45] },
  { id: "preview", Component: Preview, duration: 135, glow: [0.28, 0.5] },
  { id: "deploy", Component: Deploy, duration: 115, glow: [0.72, 0.5] },
  { id: "features", Component: Features, duration: 120, glow: [0.5, 0.56] },
  { id: "fixes", Component: Fixes, duration: 110, glow: [0.3, 0.5] },
  { id: "deps", Component: Deps, duration: 120, glow: [0.7, 0.5] },
  { id: "outro", Component: Outro, duration: 110, glow: [0.5, 0.45] },
] as const;

/** Frame each scene starts on. */
const STARTS = SCENES.reduce<number[]>((acc, _, i) => {
  acc.push(i === 0 ? 0 : acc[i - 1] + SCENES[i - 1].duration);
  return acc;
}, []);

export const TOTAL_FRAMES =
  STARTS[STARTS.length - 1] + SCENES[SCENES.length - 1].duration;

/** Scene midpoints, used to drift the backdrop glow from beat to beat. */
const MIDS = STARTS.map((s, i) => s + SCENES[i].duration / 2);

export const ReleaseVideo: React.FC = () => {
  useFonts();
  const frame = useCurrentFrame();

  const glowX = interpolate(
    frame,
    MIDS,
    SCENES.map((s) => s.glow[0]),
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const glowY = interpolate(
    frame,
    MIDS,
    SCENES.map((s) => s.glow[1]),
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill>
      <Backdrop glowX={glowX} glowY={glowY} />

      {SCENES.map(({ id, Component, duration }, i) => (
        <Sequence key={id} from={STARTS[i]} durationInFrames={duration}>
          <Component durationInFrames={duration} />
        </Sequence>
      ))}

      <Chrome
        totalFrames={TOTAL_FRAMES}
        showFrom={STARTS[1]}
        showUntil={STARTS[SCENES.length - 1]}
      />
    </AbsoluteFill>
  );
};
