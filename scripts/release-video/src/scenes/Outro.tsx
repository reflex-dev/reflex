import React from "react";
import { useCurrentFrame } from "remotion";

import { PixelLogo } from "../components/PixelLogo";
import { Scene } from "../components/Scene";
import { Chip, Eyebrow, Reveal } from "../components/ui";
import { c, font, shadow } from "../theme";

/** Every package that shipped in this release, with its new version. */
const PACKAGES: [string, string][] = [
  ["reflex", "0.9.8"],
  ["reflex-base", "0.9.8"],
  ["reflex-components-core", "0.9.8"],
  ["reflex-components-radix", "0.9.7"],
  ["reflex-components-lucide", "1.0.3"],
  ["reflex-components-recharts", "0.9.2"],
  ["reflex-components-plotly", "0.9.4"],
  ["reflex-components-moment", "0.9.3"],
  ["reflex-components-code", "0.9.3"],
  ["reflex-docgen", "0.9.4"],
];

export const Outro: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();

  return (
    <Scene durationInFrames={durationInFrames} fadeOut={0}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 34 }}>
          <PixelLogo cell={24} frame={frame} duration={26} gap={2} />
          <div
            style={{
              width: 2,
              height: 92,
              background: c.slate6,
              opacity: frame > 30 ? 1 : 0,
            }}
          />
          <div
            style={{
              fontFamily: font.sans,
              fontSize: 82,
              fontWeight: 600,
              letterSpacing: "-0.05em",
              color: c.violet9,
              opacity: frame > 30 ? 1 : 0,
            }}
          >
            0.9.8
          </div>
        </div>

        <Reveal frame={frame} delay={38} y={20} style={{ marginTop: 46 }}>
          <div
            style={{
              fontFamily: font.mono,
              fontSize: 34,
              fontWeight: 500,
              color: c.slate12,
              letterSpacing: "-0.02em",
              background: c.white,
              border: `1px solid ${c.slate5}`,
              borderRadius: 14,
              boxShadow: shadow.card,
              padding: "22px 40px",
            }}
          >
            <span style={{ color: c.violet9, marginRight: 16 }}>$</span>
            pip install reflex==0.9.8
          </div>
        </Reveal>

        <Reveal frame={frame} delay={52} y={16} style={{ marginTop: 44 }}>
          <Eyebrow>10 packages released</Eyebrow>
        </Reveal>

        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            gap: 12,
            marginTop: 24,
            maxWidth: 1380,
          }}
        >
          {PACKAGES.map(([name, version], i) => (
            <Reveal key={name} frame={frame} delay={58 + i * 3} y={12}>
              <Chip variant="slate" size={22} mono>
                {name}
                <span style={{ color: c.violet9 }}>{version}</span>
              </Chip>
            </Reveal>
          ))}
        </div>

        <Reveal frame={frame} delay={92} y={14} style={{ marginTop: 48 }}>
          <div
            style={{
              fontFamily: font.sans,
              fontSize: 30,
              fontWeight: 550,
              letterSpacing: "-0.02em",
              color: c.slate12,
            }}
          >
            reflex.dev
          </div>
        </Reveal>
      </div>
    </Scene>
  );
};
