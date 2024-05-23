import { useTheme } from "next-themes"
import { useEffect, useState } from "react"
import { ColorModeContext, defaultColorMode } from "/utils/context.js"


export default function RadixThemesColorModeProvider({ children }) {
    const {theme, setTheme} = useTheme()
    const [colorMode, setColorMode] = useState(defaultColorMode)
  
    useEffect(() => {
      setColorMode(theme)
    }, [theme])
  
    const toggleColorMode = () => {
      setTheme(theme === "light" ? "dark" : "light")
    }
    return (
      <ColorModeContext.Provider value={[ colorMode, toggleColorMode ]}>
        {children}
      </ColorModeContext.Provider>
    )
  }