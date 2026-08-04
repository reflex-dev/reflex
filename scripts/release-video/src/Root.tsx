import React from "react";
import { Composition } from "remotion";

import "@fontsource-variable/instrument-sans";
import "@fontsource-variable/jetbrains-mono";

import { ReleaseVideo, TOTAL_FRAMES } from "./Video";
import { VIDEO } from "./theme";

export const RemotionRoot: React.FC = () => (
  <Composition
    id="Release"
    component={ReleaseVideo}
    durationInFrames={TOTAL_FRAMES}
    fps={VIDEO.fps}
    width={VIDEO.width}
    height={VIDEO.height}
  />
);
