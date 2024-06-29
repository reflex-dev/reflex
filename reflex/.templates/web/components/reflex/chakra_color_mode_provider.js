import { useColorMode as chakraUseColorMode } from "@chakra-ui/react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { ColorModeContext, defaultColorMode } from "/utils/context.js";

export default function ChakraColorModeProvider({ children }) {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const { colorMode, toggleColorMode } = chakraUseColorMode();
  const [resolvedColorMode, setResolvedColorMode] = useState(colorMode);

  useEffect(() => {
    if (colorMode != resolvedTheme) {
      toggleColorMode();
    }
    setResolvedColorMode(resolvedTheme);
  }, [theme, resolvedTheme]);

  const rawColorMode = colorMode;
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
