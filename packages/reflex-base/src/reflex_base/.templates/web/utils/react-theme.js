import {
  createContext,
  useContext,
  useState,
  useEffect,
  createElement,
  useRef,
  useMemo,
  useCallback,
} from "react";

import { ColorModeContext, app } from "$/utils/context-registry";

const allowedModes = ["light", "dark", "system"];

const ThemeContext = createContext({
  theme: "system",
  resolvedTheme: "light",
  setTheme: () => {},
});
ThemeContext.displayName = "ThemeContext";

export function ThemeProvider({ children, defaultTheme = "system" }) {
  const [theme, setTheme] = useState(defaultTheme);
  const [systemTheme, setSystemTheme] = useState(
    defaultTheme !== "system" ? defaultTheme : "light",
  );
  const [isInitialized, setIsInitialized] = useState(false);

  const setColorMode = useCallback((mode) => {
    if (!allowedModes.includes(mode)) {
      console.error(
        `Invalid color mode "${mode}". Defaulting to "${app.defaultColorMode}".`,
      );
      mode = app.defaultColorMode;
    }
    setTheme(mode);
  }, []);

  const resolvedTheme = useMemo(
    () => (theme === "system" ? systemTheme : theme),
    [theme, systemTheme],
  );

  const toggleColorMode = useCallback(() => {
    setColorMode(resolvedTheme === "light" ? "dark" : "light");
  }, [setColorMode, resolvedTheme]);

  const firstRender = useRef(true);

  useEffect(() => {
    if (!firstRender.current) {
      return;
    }

    firstRender.current = false;

    if (app.isDevMode) {
      const lastCompiledTheme = localStorage.getItem("last_compiled_theme");
      if (lastCompiledTheme !== app.defaultColorMode) {
        // on app startup, make sure the application color mode is persisted correctly.
        setColorMode(app.defaultColorMode);
        localStorage.setItem("last_compiled_theme", app.defaultColorMode);
        localStorage.setItem("theme", app.defaultColorMode);
        setIsInitialized(true);
        return;
      }
    }

    // Load saved theme from localStorage
    const savedTheme = localStorage.getItem("theme") || defaultTheme;
    setColorMode(savedTheme);
    setIsInitialized(true);
  });

  useEffect(() => {
    // Set up media query for system preference detection
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

    // Listen for system preference changes
    const handleChange = () => {
      setSystemTheme(mediaQuery.matches ? "dark" : "light");
    };

    handleChange();

    mediaQuery.addEventListener("change", handleChange);

    return () => {
      mediaQuery.removeEventListener("change", handleChange);
    };
  }, []);

  // Save theme to localStorage whenever it changes
  // Skip saving only if theme key already exists and we haven't initialized yet
  useEffect(() => {
    const existingTheme = localStorage.getItem("theme");
    if (!isInitialized && existingTheme !== null) return;
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    if (!isInitialized) return;
    const root = window.document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(resolvedTheme);
    root.style.colorScheme = resolvedTheme;
  }, [resolvedTheme, isInitialized]);

  const themeContextValue = useMemo(
    () => ({ theme, resolvedTheme, setTheme }),
    [theme, resolvedTheme],
  );

  const colorModeContextValue = useMemo(
    () => ({
      rawColorMode: theme,
      resolvedColorMode: resolvedTheme,
      toggleColorMode,
      setColorMode,
    }),
    [theme, resolvedTheme, toggleColorMode, setColorMode],
  );

  return useMemo(
    () =>
      createElement(
        ThemeContext.Provider,
        { value: themeContextValue },
        createElement(
          ColorModeContext.Provider,
          { value: colorModeContextValue },
          children,
        ),
      ),
    [themeContextValue, colorModeContextValue, children],
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
