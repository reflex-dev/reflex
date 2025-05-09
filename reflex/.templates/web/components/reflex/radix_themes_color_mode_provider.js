import { useTheme } from "$/utils/react-theme";
import { useEffect, useState, createElement, useRef } from "react";
import {
  ColorModeContext,
  defaultColorMode,
  isDevMode,
  lastCompiledTimeStamp,
} from "$/utils/context";

export default function RadixThemesColorModeProvider({ children }) {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [rawColorMode, setRawColorMode] = useState(defaultColorMode);
  const [resolvedColorMode, setResolvedColorMode] = useState(
    defaultColorMode === "dark" ? "dark" : "light",
  );

  useEffect(() => {
    setTheme(rawColorMode);
  }, [rawColorMode]);

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
  });

  useEffect(() => {
    setResolvedColorMode(resolvedTheme);
  }, [resolvedTheme]);

  const toggleColorMode = () => {
    setRawColorMode(resolvedTheme === "light" ? "dark" : "light");
  };
  const setColorMode = (mode) => {
    const allowedModes = ["light", "dark", "system"];
    if (!allowedModes.includes(mode)) {
      console.error(
        `Invalid color mode "${mode}". Defaulting to "${defaultColorMode}".`
      );
      mode = defaultColorMode;
    }
    setRawColorMode(mode);
  };
  return createElement(
    ColorModeContext.Provider,
    {
      value: {
        rawColorMode: theme,
        resolvedColorMode,
        toggleColorMode,
        setColorMode,
      },
    },
    children,
  );
}
