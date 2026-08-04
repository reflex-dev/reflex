import React from "react";
import { useCurrentFrame } from "remotion";

import { Scene } from "../components/Scene";
import { Card, Eyebrow, Headline, PixelBullet, Reveal } from "../components/ui";
import { c, font } from "../theme";

const FEATURES = [
  {
    api: "rx.asset(...)",
    text: "Content-hash cache busting baked into asset URLs.",
  },
  {
    api: "async with state",
    text: "Mutable state proxies now work as async context managers.",
  },
  {
    api: "Plugin.register_route",
    text: "Plugins contribute pages atomically, once per app — plus rx.plugins.get_plugin().",
  },
  {
    api: "rx.recharts.layer / .rectangle",
    text: "Wrap Recharts Layer and Rectangle to build custom chart nodes.",
  },
];

export const Features: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();

  return (
    <Scene durationInFrames={durationInFrames}>
      <div style={{ width: 1460 }}>
        <Reveal frame={frame} delay={0} y={14}>
          <Eyebrow color={c.violet11}>Also new</Eyebrow>
        </Reveal>

        <Reveal frame={frame} delay={5} y={20} style={{ marginTop: 16 }}>
          <Headline size={70}>Four more things.</Headline>
        </Reveal>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 20,
            marginTop: 44,
          }}
        >
          {FEATURES.map((f, i) => (
            <Reveal key={f.api} frame={frame} delay={16 + i * 7} y={26}>
              <Card padding={32} style={{ height: "100%" }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    marginBottom: 14,
                  }}
                >
                  <PixelBullet size={13} />
                  <span
                    style={{
                      fontFamily: font.mono,
                      fontSize: 29,
                      fontWeight: 500,
                      color: c.violet9,
                      letterSpacing: "-0.02em",
                    }}
                  >
                    {f.api}
                  </span>
                </div>
                <div
                  style={{
                    fontFamily: font.sans,
                    fontSize: 26,
                    lineHeight: 1.42,
                    color: c.slate11,
                    letterSpacing: "-0.011em",
                  }}
                >
                  {f.text}
                </div>
              </Card>
            </Reveal>
          ))}
        </div>
      </div>
    </Scene>
  );
};
