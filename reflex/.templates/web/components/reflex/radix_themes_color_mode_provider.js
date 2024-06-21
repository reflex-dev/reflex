import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { ColorModeContext, defaultColorMode } from "/utils/context.js";

export default function RadixThemesColorModeProvider({ children }) {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [rawColorMode, setRawColorMode] = useState(defaultColorMode);
  const [resolvedColorMode, setResolvedColorMode] = useState("dark");

  useEffect(() => {
    setRawColorMode(theme);
    setResolvedColorMode(resolvedTheme);
  }, [theme, resolvedTheme]);

  const toggleColorMode = () => {
    setTheme(resolvedTheme === "light" ? "dark" : "light");
  };
  const setColorMode = (mode) => {
    const allowedModes = ["light", "dark", "system"];
    if (!allowedModes.includes(mode)) {
      console.error(
        `Invalid color mode "${mode}". Defaulting to "${defaultColorMode}".`
      );
      mode = defaultColorMode;
    }
    setTheme(mode);
  };
  return (
    <ColorModeContext.Provider
      value={{ rawColorMode, resolvedColorMode, toggleColorMode, setColorMode }}
    >
      {children}
    </ColorModeContext.Provider>
  );
}
