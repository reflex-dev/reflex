import React from "react";
import { interpolate, useCurrentFrame } from "remotion";

import { Scene } from "../components/Scene";
import {
  Body,
  Card,
  Cursor,
  Eyebrow,
  Headline,
  Reveal,
  Terminal,
  typed,
} from "../components/ui";
import { c, font, shadow } from "../theme";

const COMMAND = 'reflex deploy --provider gcp --description "checkout revamp"';

const ProviderCard: React.FC<{
  name: string;
  detail: string;
  selected: number;
}> = ({ name, detail, selected }) => (
  <Card
    padding={30}
    style={{
      flex: 1,
      height: "100%",
      borderColor: selected > 0.5 ? c.violet8 : c.slate5,
      background: selected > 0.5 ? c.violet2 : c.white,
      boxShadow:
        selected > 0.5
          ? `${shadow.card}, 0 0 0 4px ${c.violet4}`
          : shadow.medium,
      transform: `translateY(${interpolate(selected, [0, 1], [0, -8])}px)`,
    }}
  >
    <div
      style={{
        fontFamily: font.sans,
        fontSize: 34,
        fontWeight: 600,
        letterSpacing: "-0.025em",
        color: selected > 0.5 ? c.violet11 : c.slate12,
      }}
    >
      {name}
    </div>
    <div
      style={{
        fontFamily: font.sans,
        fontSize: 24,
        color: c.slate11,
        marginTop: 8,
      }}
    >
      {detail}
    </div>
  </Card>
);

export const Deploy: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();

  const typing = interpolate(frame, [24, 64], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // The GCP card lights up the moment the flag finishes typing.
  const picked = interpolate(frame, [66, 78], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <Scene durationInFrames={durationInFrames}>
      <div style={{ width: 1460 }}>
        <Reveal frame={frame} delay={0} y={14}>
          <Eyebrow color={c.violet11}>reflex deploy</Eyebrow>
        </Reveal>

        <Reveal frame={frame} delay={6} y={22} style={{ marginTop: 18 }}>
          <Headline size={76}>Now pick where it ships.</Headline>
        </Reveal>

        <Reveal frame={frame} delay={16} y={26} style={{ marginTop: 40 }}>
          <Terminal label="bash">
            <div
              style={{
                fontFamily: font.mono,
                fontSize: 28,
                color: c.slate12,
                letterSpacing: "-0.015em",
              }}
            >
              <span style={{ color: c.violet9, marginRight: 14 }}>$</span>
              {typed(COMMAND, typing)}
              {typing < 1 ? <Cursor frame={frame} /> : null}
            </div>
          </Terminal>
        </Reveal>

        <div style={{ display: "flex", gap: 20, marginTop: 30 }}>
          <Reveal
            frame={frame}
            delay={30}
            y={20}
            style={{ flex: 1, display: "flex" }}
          >
            <ProviderCard
              name="Reflex Cloud"
              detail="The managed default"
              selected={0}
            />
          </Reveal>
          <Reveal
            frame={frame}
            delay={38}
            y={20}
            style={{ flex: 1, display: "flex" }}
          >
            <ProviderCard
              name="Google Cloud"
              detail="A GCP account connected to your org"
              selected={picked}
            />
          </Reveal>
        </div>

        <Reveal frame={frame} delay={86} y={14} style={{ marginTop: 26 }}>
          <Body size={26} color={c.slate9}>
            <code style={{ fontFamily: font.mono, color: c.slate11 }}>
              --description
            </code>{" "}
            records a changelog note, shown in{" "}
            <code style={{ fontFamily: font.mono, color: c.slate11 }}>
              reflex cloud apps history
            </code>
            .
          </Body>
        </Reveal>
      </div>
    </Scene>
  );
};
