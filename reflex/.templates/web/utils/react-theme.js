import {
  createContext,
  useContext,
  useState,
  useEffect,
  createElement,
  useRef,
  useMemo,
} from "react";

import { isDevMode, defaultColorMode } from "$/utils/context";

const ThemeContext = createContext({
  theme: defaultColorMode,
  resolvedTheme: defaultColorMode !== "system" ? defaultColorMode : "light",
  setTheme: () => {},
});

export function ThemeProvider({ children, defaultTheme = "system" }) {
  const [theme, setTheme] = useState(defaultTheme);
  const [systemTheme, setSystemTheme] = useState(
    defaultTheme !== "system" ? defaultTheme : "light",
  );

  const firstRender = useRef(true);

  useEffect(() => {
    if (!firstRender.current) {
      return;
    }

    firstRender.current = false;

    if (isDevMode) {
      const lastCompiledTheme = localStorage.getItem("last_compiled_theme");
      if (lastCompiledTheme !== defaultColorMode) {
        // on app startup, make sure the application color mode is persisted correctly.
        localStorage.setItem("last_compiled_theme", defaultColorMode);
        return;
      }
    }

    // Load saved theme from localStorage
    const savedTheme = localStorage.getItem("theme") || defaultTheme;
    setTheme(savedTheme);
  });

  const resolvedTheme = useMemo(
    () => (theme === "system" ? systemTheme : theme),
    [theme, systemTheme],
  );

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
  useEffect(() => {
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    const root = window.document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(resolvedTheme);
    root.style.colorScheme = resolvedTheme;
  }, [resolvedTheme]);

  return createElement(
    ThemeContext.Provider,
    { value: { theme, resolvedTheme, setTheme } },
    children,
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
