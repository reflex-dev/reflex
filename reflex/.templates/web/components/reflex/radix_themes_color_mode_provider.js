import { useTheme } from "$/utils/react-theme";
import { createElement, useCallback, useEffect, useMemo } from "react";
import { ColorModeContext, defaultColorMode } from "$/utils/context";

export default function RadixThemesColorModeProvider({ children }) {
  const { theme, resolvedTheme, setTheme } = useTheme();

  const toggleColorMode = useCallback(() => {
    setTheme(resolvedTheme === "light" ? "dark" : "light");
  }, [resolvedTheme, setTheme]);

  const setColorMode = useCallback(
    (mode) => {
      const allowedModes = ["light", "dark", "system"];
      if (!allowedModes.includes(mode)) {
        console.error(
          `Invalid color mode "${mode}". Defaulting to "${defaultColorMode}".`,
        );
        mode = defaultColorMode;
      }
      setTheme(mode);
    },
    [setTheme],
  );

  useEffect(() => {
    const radixRoot = document.querySelector(
      '.radix-themes[data-is-root-theme="true"]',
    );
    if (radixRoot) {
      radixRoot.classList.remove("light", "dark");
      radixRoot.classList.add(resolvedTheme);
    }
  }, [resolvedTheme]);

  return useMemo(
    () =>
      createElement(
        ColorModeContext.Provider,
        {
          value: {
            rawColorMode: theme,
            resolvedColorMode: resolvedTheme,
            toggleColorMode,
            setColorMode,
          },
        },
        children,
      ),
    [theme, resolvedTheme, toggleColorMode, setColorMode, children],
  );
}
