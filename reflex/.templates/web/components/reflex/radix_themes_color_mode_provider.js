import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { ColorModeContext, defaultColorMode } from "/utils/context.js";

export default function RadixThemesColorModeProvider({ children }) {
  const { resolvedTheme, setTheme } = useTheme();
  const [colorMode, setColorMode] = useState(defaultColorMode);

  useEffect(() => {
    setColorMode(resolvedTheme);
  }, [resolvedTheme]);

  const toggleColorMode = () => {
    setTheme(resolvedTheme === "light" ? "dark" : "light");
  };
  return (
    <ColorModeContext.Provider value={[colorMode, toggleColorMode]}>
      {children}
    </ColorModeContext.Provider>
  );
}
