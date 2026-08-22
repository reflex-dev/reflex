import {
  createContext,
  useContext,
  useState,
  useEffect,
  createElement,
  useRef,
  useMemo,
} from "react";

const allowedModes = ["light", "dark", "system"];

// Shared-identity color mode context: provided by ThemeProvider below and
// consumed by compiled `useContext(ColorModeContext)` hooks. The default only
// applies when no provider is mounted (e.g. isolated tests) — generated app
// roots always mount ThemeProvider with the app's default color mode.
export const ColorModeContext = createContext({
  rawColorMode: "system",
  resolvedColorMode: "light",
  toggleColorMode: () => {},
  setColorMode: () => {},
});

const ThemeContext = createContext({
  theme: "system",
  resolvedTheme: "light",
  setTheme: () => {},
});

export function ThemeProvider({
  children,
  defaultTheme = "system",
  isDevMode = false,
}) {
  const [theme, setTheme] = useState(defaultTheme);
  const [systemTheme, setSystemTheme] = useState(
    defaultTheme !== "system" ? defaultTheme : "light",
  );
  const [isInitialized, setIsInitialized] = useState(false);

  const setColorMode = (mode) => {
    if (!allowedModes.includes(mode)) {
      console.error(
        `Invalid color mode "${mode}". Defaulting to "${defaultTheme}".`,
      );
      mode = defaultTheme;
    }
    setTheme(mode);
  };

  const resolvedTheme = useMemo(
    () => (theme === "system" ? systemTheme : theme),
    [theme, systemTheme],
  );

  const toggleColorMode = () => {
    setColorMode(resolvedTheme === "light" ? "dark" : "light");
  };

  const firstRender = useRef(true);

  useEffect(() => {
    if (!firstRender.current) {
      return;
    }

    firstRender.current = false;

    if (isDevMode) {
      const lastCompiledTheme = localStorage.getItem("last_compiled_theme");
      if (lastCompiledTheme !== defaultTheme) {
        // on app startup, make sure the application color mode is persisted correctly.
        setColorMode(defaultTheme);
        localStorage.setItem("last_compiled_theme", defaultTheme);
        localStorage.setItem("theme", defaultTheme);
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
  });

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

  return createElement(
    ThemeContext.Provider,
    { value: { theme, resolvedTheme, setTheme } },
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
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
