import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import {
  ColorModeContext,
  defaultColorMode,
  isDevMode,
  lastCompiledTimeStamp,
} from "$/utils/context.js";

export default function RadixThemesColorModeProvider({ children }) {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [rawColorMode, setRawColorMode] = useState(defaultColorMode);
  const [resolvedColorMode, setResolvedColorMode] = useState(
    defaultColorMode === "dark" ? "dark" : "light"
  );

  useEffect(() => {
    if (isDevMode) {
      const lastCompiledTimeInLocalStorage =
        localStorage.getItem("last_compiled_time");
      if (lastCompiledTimeInLocalStorage !== lastCompiledTimeStamp) {
        // on app startup, make sure the application color mode is persisted correctly.
        setTheme(defaultColorMode);
        localStorage.setItem("last_compiled_time", lastCompiledTimeStamp);
        return;
      }
    }
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
