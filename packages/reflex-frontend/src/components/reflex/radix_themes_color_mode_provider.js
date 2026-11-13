import { useTheme } from "$/utils/react-theme";
import { useEffect } from "react";

export default function RadixThemesColorModeProvider({ children }) {
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    const radixRoot = document.querySelector(
      '.radix-themes[data-is-root-theme="true"]',
    );
    if (radixRoot) {
      radixRoot.classList.remove("light", "dark");
      radixRoot.classList.add(resolvedTheme);
    }
  }, [resolvedTheme]);

  return children;
}
